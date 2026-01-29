"""Async CRUD for the embeddings collection (§3.1.3). Idempotency by (chunk_id, embedding_config_hash). Uses bulk operations."""

from typing import Any

from pymongo.errors import PyMongoError
from pymongo.operations import ReplaceOne

from app.config.logging import get_logger
from app.repositories.mongodb.base import (
    embeddings_collection,
    tenant_filter,
    _translate_pymongo_error,
)
from app.utils.time import utc_now

logger = get_logger(__name__)


async def list_embedding_ids(tenant_id: str, limit: int) -> list[str]:
    """
    Return embedding ids for the tenant, up to `limit`. Only returns embeddings with status 'processed'
    and non-empty embedding_vector. Used by indexing stage to fetch embeddings from DB.
    No maximum limit - accepts any positive integer.
    """
    coll = embeddings_collection()
    try:
        query = {
            **tenant_filter(tenant_id),
            "status": "processed",
            "embedding_vector": {"$exists": True, "$ne": []},
        }
        cursor = coll.find(query, {"embedding_id": 1}).limit(limit)
        out: list[str] = []
        doc_count = 0
        async for doc in cursor:
            doc_count += 1
            embedding_id = doc.get("embedding_id")
            if embedding_id and embedding_id not in out:
                out.append(embedding_id)
        logger.info(
            "list_embedding_ids completed",
            extra={
                "tenant_id": tenant_id,
                "requested_limit": limit,
                "documents_scanned": doc_count,
                "unique_embedding_ids_returned": len(out),
            },
        )
        # Safety check: never return more than limit (shouldn't happen, but safeguard)
        return out[:limit]
    except PyMongoError as e:
        raise _translate_pymongo_error(e, "list embedding ids") from e


async def get_embeddings_by_ids(
    tenant_id: str,
    embedding_ids: list[str],
    *,
    only_processed: bool = True,
) -> list[dict[str, Any]]:
    """
    Load embeddings by embedding_ids and tenant_id. Per §4.3: used by indexing to read
    embeddings from MongoDB. If only_processed is True (default), returns only docs
    with status 'processed' and non-empty embedding_vector; otherwise returns all found.
    """
    if not embedding_ids:
        return []
    coll = embeddings_collection()
    query: dict[str, Any] = {
        **tenant_filter(tenant_id),
        "embedding_id": {"$in": list(embedding_ids)},
    }
    if only_processed:
        query["status"] = "processed"
        query["embedding_vector"] = {"$exists": True, "$ne": []}
    
    logger.debug(
        "Querying embeddings",
        extra={
            "tenant_id": tenant_id,
            "embedding_ids_count": len(embedding_ids),
            "only_processed": only_processed,
            "query": query,
        },
    )
    
    try:
        cursor = coll.find(query)
        results = [doc async for doc in cursor]
        logger.debug(
            "Found embeddings",
            extra={
                "tenant_id": tenant_id,
                "requested_count": len(embedding_ids),
                "found_count": len(results),
            },
        )
        return results
    except PyMongoError as e:
        raise _translate_pymongo_error(e, "get embeddings by ids") from e


async def find_by_chunk_and_config_hash(
    tenant_id: str,
    chunk_id: str,
    embedding_config_hash: str,
) -> dict[str, Any] | None:
    """
    Find an existing embedding by chunk_id and config hash. Per §6.3 and Phase 3:
    same chunk + same model + strategy + config → one embedding. Returns None if not found.
    """
    coll = embeddings_collection()
    try:
        doc = await coll.find_one(
            {
                **tenant_filter(tenant_id),
                "chunk_id": chunk_id,
                "embedding_config_hash": embedding_config_hash,
            }
        )
        return doc
    except PyMongoError as e:
        raise _translate_pymongo_error(e, "find embedding by chunk and config hash") from e


async def upsert_embeddings_bulk(embedding_docs: list[dict[str, Any]]) -> tuple[int, int]:
    """
    Bulk insert or replace embeddings using bulk_write for performance.
    Idempotency: filter by (tenant_id, chunk_id, embedding_config_hash).
    Returns (inserted_count, updated_count).
    """
    if not embedding_docs:
        return 0, 0
    
    coll = embeddings_collection()
    now = utc_now()
    operations: list[ReplaceOne] = []
    
    for doc in embedding_docs:
        storage_doc = dict(doc)
        storage_doc.setdefault("updated_at", now)
        storage_doc.setdefault("created_at", now)
        tenant_id = storage_doc.get("tenant_id")
        chunk_id = storage_doc.get("chunk_id")
        config_hash = storage_doc.get("embedding_config_hash")
        if not all([tenant_id, chunk_id, config_hash]):
            raise ValueError("embedding_doc must include tenant_id, chunk_id, embedding_config_hash")
        filter_ = {
            **tenant_filter(tenant_id),
            "chunk_id": chunk_id,
            "embedding_config_hash": config_hash,
        }
        operations.append(ReplaceOne(filter_, storage_doc, upsert=True))
    
    try:
        result = await coll.bulk_write(operations, ordered=False)
        return result.upserted_count, result.modified_count
    except PyMongoError as e:
        raise _translate_pymongo_error(e, "bulk upsert embeddings") from e


async def upsert_embedding(embedding_doc: dict[str, Any]) -> bool:
    """
    Insert or replace one embedding. Idempotency: filter by (tenant_id, chunk_id, embedding_config_hash).
    If a document exists, replace it (e.g. retry after failure); otherwise insert.
    Returns True if inserted, False if updated.
    Note: For bulk operations, use upsert_embeddings_bulk instead.
    """
    inserted, _ = await upsert_embeddings_bulk([embedding_doc])
    return inserted > 0
