"""
Async indexing pipeline: embedding_ids + tenant_id + index_name + indexing_strategy →
load embeddings from MongoDB → ensure index exists → bulk-publish vectors + metadata to OpenSearch.
Idempotent per §4.3. Partial failures recorded per §9.2.
"""

from typing import Any

from app.config.indexing.models import IndexingConfig
from app.config.logging import get_logger
from app.repositories.mongodb.chunks_repository import get_chunks_by_ids
from app.repositories.mongodb.embeddings_repository import get_embeddings_by_ids
from app.repositories.opensearch.vectors_repository import bulk_index_vectors
from app.resources.opensearch.index_manager import create_index_if_not_exists

logger = get_logger(__name__)

# Re-export for controller
__all__ = ["run_index_pipeline"]


async def run_index_pipeline(
    embedding_ids: list[str],
    tenant_id: str,
    index_name: str,
    config: IndexingConfig,
) -> tuple[int, int, list[dict[str, Any]], int, str, int]:
    """
    Load embeddings by embedding_ids + tenant_id from MongoDB; ensure OpenSearch index exists;
    bulk-publish vectors and metadata to OpenSearch with idempotent semantics (§4.3).
    Returns (vectors_indexed, vectors_failed, errors, dimension, similarity, total_vectors).
    total_vectors = count of docs in index after (we don't refresh and count; use vectors_indexed for response).
    For index_info.total_vectors we use vectors_indexed as the incremental count; optional full count via OpenSearch.
    """
    if not embedding_ids:
        return 0, 0, [], 0, config.similarity, 0

    logger.info(
        "Starting index pipeline",
        extra={
            "tenant_id": tenant_id,
            "index_name": index_name,
            "embedding_ids_count": len(embedding_ids),
            "indexing_strategy": config.similarity,
        },
    )

    embeddings = await get_embeddings_by_ids(tenant_id, embedding_ids, only_processed=True)
    logger.info(
        "Fetched embeddings from MongoDB",
        extra={
            "requested_count": len(embedding_ids),
            "found_count": len(embeddings),
            "tenant_id": tenant_id,
        },
    )

    found_ids = {e.get("embedding_id") for e in embeddings if e.get("embedding_id")}
    # Track embeddings that were returned but don't have embedding_id (data integrity issue)
    embeddings_without_id = [e for e in embeddings if not e.get("embedding_id")]
    missing_ids = [eid for eid in embedding_ids if eid not in found_ids]
    
    if missing_ids:
        logger.warning(
            "Some embedding_ids were not found or not processed",
            extra={
                "missing_count": len(missing_ids),
                "missing_ids": missing_ids[:10],  # Log first 10 to avoid huge logs
                "tenant_id": tenant_id,
            },
        )
    
    errors_so_far: list[dict[str, Any]] = [
        {"item_id": eid, "error": "Embedding not found or not processed", "error_code": "EMBEDDING_NOT_FOUND"}
        for eid in missing_ids
    ]
    # Add errors for embeddings without embedding_id (shouldn't happen, but handle gracefully)
    for emb in embeddings_without_id:
        chunk_id = emb.get("chunk_id", "unknown")
        errors_so_far.append({
            "item_id": chunk_id,
            "error": "Embedding document missing embedding_id field",
            "error_code": "MISSING_EMBEDDING_ID"
        })

    if not embeddings:
        return 0, len(embedding_ids), errors_so_far, 0, config.similarity, 0

    dimension = 0
    for emb in embeddings:
        vec = emb.get("embedding_vector") or []
        if vec:
            dimension = len(vec)
            break
    if dimension == 0:
        for emb in embeddings:
            errors_so_far.append(
                {"item_id": emb.get("embedding_id", "?"), "error": "No vector", "error_code": "NO_VECTOR"}
            )
        return 0, len(embedding_ids), errors_so_far, 0, config.similarity, 0

    await create_index_if_not_exists(index_name, dimension, config)

    chunk_ids = list({e.get("chunk_id") for e in embeddings if e.get("chunk_id")})
    chunks = await get_chunks_by_ids(tenant_id, chunk_ids)
    chunk_by_id = {c["chunk_id"]: (c.get("chunk_text") or "") for c in chunks}

    success_count, bulk_errors = await bulk_index_vectors(
        index_name,
        embeddings,
        chunk_by_chunk_id=chunk_by_id,
    )
    errors_so_far.extend(bulk_errors)
    failed_count = len(errors_so_far)

    total_vectors = success_count  # incremental count; full index count would require a separate OpenSearch count
    return success_count, failed_count, errors_so_far, dimension, config.similarity, total_vectors
