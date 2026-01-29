"""
Async embedding pipeline: chunk_ids + tenant_id + strategy/config → load chunks → batch embed → persist.
Idempotent by embedding_config_hash (chunk_hash + model + strategy + config). Per §6.3 and §9.2.
Batches embedding API calls for performance.
"""

import hashlib
import json
from typing import Any

from app.config.embedding.models import EmbeddingConfig
from app.repositories.mongodb.chunks_repository import get_chunks_by_ids
from app.repositories.mongodb.embeddings_repository import (
    find_by_chunk_and_config_hash,
    upsert_embeddings_bulk,
)
from app.services.embedder.normalization import apply_normalization
from app.services.embedder.preprocessing import preprocess_texts
from app.services.embedder.strategies import get_embedding_strategy
from app.utils.ids import generate_embedding_id
from app.utils.time import utc_now


def compute_embedding_config_hash(chunk_hash: str, config: EmbeddingConfig) -> str:
    """Per §6.3: Embedding hash = SHA-256(chunk_hash + model + strategy + config). api_key excluded for idempotency."""
    d = config.model_dump(mode="json", exclude={"api_key"})
    config_canonical = json.dumps(d, sort_keys=True)
    payload = f"{chunk_hash}|{config.model}|{config.strategy}|{config_canonical}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def run_embed_pipeline(
    chunk_ids: list[str],
    tenant_id: str,
    config: EmbeddingConfig,
) -> tuple[int, int, int, list[str], list[dict[str, Any]]]:
    """
    Orchestrate async embedding: load chunks by chunk_ids + tenant_id; batch check existing embeddings;
    batch preprocess → batch embed → normalize → bulk persist. Record status and error_message per §9.2.
    Returns (created_count, skipped_count, failed_count, embedding_ids, errors).
    embedding_ids includes both created and skipped (existing) so the client has full list.
    errors = list of {item_id, error, error_code} for failed chunks.
    """
    if not chunk_ids:
        return 0, 0, 0, [], []

    chunks = await get_chunks_by_ids(tenant_id, chunk_ids)
    chunk_by_id = {c["chunk_id"]: c for c in chunks}
    strategy = get_embedding_strategy(config.strategy)
    if strategy is None:
        raise ValueError(f"Unknown embedding strategy: {config.strategy!r}")

    created = 0
    skipped = 0
    failed = 0
    embedding_ids: list[str] = []
    errors: list[dict[str, Any]] = []
    
    # Separate chunks into those that need embedding and those that already exist
    chunks_to_embed: list[tuple[str, dict[str, Any], str]] = []  # (chunk_id, chunk, config_hash)
    existing_embeddings: dict[str, dict[str, Any]] = {}  # chunk_id -> embedding doc
    
    # Check existing embeddings in batch
    for cid in chunk_ids:
        chunk = chunk_by_id.get(cid)
        if chunk is None:
            failed += 1
            errors.append({"item_id": cid, "error": "Chunk not found", "error_code": "CHUNK_NOT_FOUND"})
            continue

        chunk_hash = chunk.get("chunk_hash") or ""
        document_id = chunk.get("document_id") or ""
        config_hash = compute_embedding_config_hash(chunk_hash, config)

        existing = await find_by_chunk_and_config_hash(tenant_id, cid, config_hash)
        if existing is not None:
            skipped += 1
            embedding_ids.append(existing["embedding_id"])
            existing_embeddings[cid] = existing
        else:
            chunks_to_embed.append((cid, chunk, config_hash))
    
    if not chunks_to_embed:
        return created, skipped, failed, embedding_ids, errors
    
    # Batch process chunks that need embedding
    texts_to_embed: list[str] = []
    chunk_metadata: list[tuple[str, str, str]] = []  # (chunk_id, document_id, config_hash)
    
    for cid, chunk, config_hash in chunks_to_embed:
        text = chunk.get("chunk_text") or ""
        document_id = chunk.get("document_id") or ""
        texts_to_embed.append(text)
        chunk_metadata.append((cid, document_id, config_hash))
    
    # Batch preprocess
    preprocessed_texts = preprocess_texts(texts_to_embed, config.preprocessing)
    
    # Batch embed (strategy handles batching internally)
    try:
        vectors = strategy.embed(preprocessed_texts, config)
        if len(vectors) != len(preprocessed_texts):
            raise ValueError(f"Strategy returned {len(vectors)} vectors but expected {len(preprocessed_texts)}")
        
        # Normalize vectors
        norm_type = "none"
        if config.normalize:
            norm_type = config.normalization_type if config.normalization_type in ("L2", "L1") else "L2"
        normalized_pairs = apply_normalization(vectors, norm_type)
        
        # Prepare documents for bulk insert
        now = utc_now()
        embedding_docs: list[dict[str, Any]] = []
        
        for i, (cid, document_id, config_hash) in enumerate(chunk_metadata):
            normalized_vec, original_norm = normalized_pairs[i]
            embedding_id = generate_embedding_id()
            doc = {
                "embedding_id": embedding_id,
                "chunk_id": cid,
                "document_id": document_id,
                "tenant_id": tenant_id,
                "embedding_model": config.model,
                "embedding_strategy": config.strategy,
                "embedding_config_hash": config_hash,
                "vector_dimension": len(normalized_vec),
                "embedding_vector": normalized_vec,
                "normalization_info": {
                    "normalized": config.normalize,
                    "norm_type": norm_type,
                    "original_norm": original_norm,
                },
                "status": "processed",
                "error_message": None,
                "created_at": now,
                "updated_at": now,
            }
            embedding_docs.append(doc)
            embedding_ids.append(embedding_id)
        
        # Bulk insert embeddings
        inserted_count, _ = await upsert_embeddings_bulk(embedding_docs)
        created = inserted_count
        
    except Exception as e:
        # If batch embedding fails, mark all as failed
        err_msg = str(e)
        failed_docs: list[dict[str, Any]] = []
        now = utc_now()
        
        for cid, document_id, config_hash in chunk_metadata:
            failed += 1
            errors.append({"item_id": cid, "error": err_msg, "error_code": "EMBEDDING_FAILED"})
            failed_doc = {
                "embedding_id": generate_embedding_id(),
                "chunk_id": cid,
                "document_id": document_id,
                "tenant_id": tenant_id,
                "embedding_model": config.model,
                "embedding_strategy": config.strategy,
                "embedding_config_hash": config_hash,
                "vector_dimension": 0,
                "embedding_vector": [],
                "normalization_info": {"normalized": False, "norm_type": "none", "original_norm": 0.0},
                "status": "failed",
                "error_message": err_msg,
                "created_at": now,
                "updated_at": now,
            }
            failed_docs.append(failed_doc)
        
        # Best-effort bulk insert of failed records
        try:
            await upsert_embeddings_bulk(failed_docs)
        except Exception:
            pass  # best-effort record failure

    return created, skipped, failed, embedding_ids, errors
