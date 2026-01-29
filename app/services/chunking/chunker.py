"""
Chunker: takes raw document + strategy + config and returns chunk records with chunk_hash.
Deterministic and idempotent per §5.2. Orchestration: load doc → chunk → persist.
"""

import hashlib
import json
from typing import Any

from app.config.chunking.models import ChunkingConfig
from app.config.chunking.static import resolve_chunking_config
from app.repositories.mongodb.documents_repository import get_raw_document
from app.repositories.mongodb.chunks_repository import upsert_chunks
from app.services.chunking.cleaners import clean_for_chunking
from app.services.chunking.strategies import get_strategy_fn
from app.services.chunking.tokenizer import count_tokens
from app.utils.ids import generate_chunk_id
from app.utils.time import utc_now


def compute_chunk_hash(chunk_text: str, strategy: str, config: ChunkingConfig) -> str:
    """Chunk hash = SHA-256(chunk_text + strategy + config) per §5.2."""
    config_canonical = json.dumps(config.model_dump(mode="json"), sort_keys=True)
    payload = f"{chunk_text}|{strategy}|{config_canonical}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def chunk_document(
    full_content: str,
    document_id: str,
    tenant_id: str,
    strategy_name: str,
    config: ChunkingConfig,
) -> list[dict[str, Any]]:
    """
    Chunk a document: clean text, run strategy, build chunk records with chunk_id,
    chunk_hash, and full §3.1.2 schema fields. Deterministic for same input + config.
    """
    strategy_fn = get_strategy_fn(strategy_name)
    if strategy_fn is None:
        raise ValueError(f"Unknown chunking strategy: {strategy_name!r}")
    cleaned = clean_for_chunking(full_content, preserve_whitespace=config.preserve_whitespace)
    chunk_texts = strategy_fn(cleaned, config)
    config_dict = config.model_dump(mode="json")
    now = utc_now()
    records: list[dict[str, Any]] = []
    for i, chunk_text in enumerate(chunk_texts):
        chunk_hash = compute_chunk_hash(chunk_text, strategy_name, config)
        chunk_id = generate_chunk_id(document_id, i, chunk_hash)
        # Actual token count for this chunk (from tokenizer); config values are target/requested
        chunk_token_count = count_tokens(chunk_text, config.tokenizer)
        records.append({
            "chunk_id": chunk_id,
            "document_id": document_id,
            "tenant_id": tenant_id,
            "chunk_text": chunk_text,
            "chunk_index": i,
            "chunking_strategy": strategy_name,
            "chunking_config": config_dict,
            "chunk_token_size": config.chunk_size,
            "chunk_token_count": chunk_token_count,
            "overlap_size": config.overlap,
            "chunk_hash": chunk_hash,
            "status": "pending",
            "created_at": now,
            "updated_at": now,
        })
    return records


async def run_chunk_pipeline(
    tenant_id: str,
    document_id: str,
    chunking_strategy: str,
    chunking_config_inline: dict[str, Any] | None = None,
) -> tuple[list[str], int, int]:
    """
    Orchestrate async chunking: load raw document → chunk → persist. Idempotent by chunk_hash.
    Returns (chunk_ids, inserted_count, updated_count).
    Raises ValueError if document not found or strategy/config invalid.
    """
    config = resolve_chunking_config(chunking_strategy, chunking_config_inline)
    strategy_name = config.strategy
    raw = await get_raw_document(tenant_id, document_id)
    if raw is None:
        raise ValueError(f"Document not found: tenant_id={tenant_id!r}, document_id={document_id!r}")
    full_content = raw.get("full_content") or raw.get("content") or ""
    records = chunk_document(
        full_content=full_content,
        document_id=document_id,
        tenant_id=tenant_id,
        strategy_name=strategy_name,
        config=config,
    )
    inserted, updated = await upsert_chunks(tenant_id, document_id, records)
    chunk_ids = [r["chunk_id"] for r in records]
    return chunk_ids, inserted, updated
