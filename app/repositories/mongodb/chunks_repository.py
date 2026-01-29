"""Async insert/upsert chunks into the chunks collection (§3.1.2). Idempotency by chunk_hash. Uses bulk operations."""

from typing import Any

from pymongo.errors import PyMongoError
from pymongo.operations import ReplaceOne

from app.repositories.mongodb.base import (
    chunks_collection,
    tenant_document_filter,
    tenant_filter,
    _translate_pymongo_error,
)
from app.utils.time import utc_now


async def list_chunk_ids(tenant_id: str, limit: int) -> list[str]:
    """
    Return chunk ids for the tenant, up to `limit`. Used by embedding stage to fetch chunks from DB.
    No maximum limit - accepts any positive integer.
    """
    coll = chunks_collection()
    try:
        cursor = coll.find(tenant_filter(tenant_id), {"chunk_id": 1}).limit(limit)
        out: list[str] = []
        async for doc in cursor:
            chunk_id = doc.get("chunk_id")
            if chunk_id and chunk_id not in out:
                out.append(chunk_id)
        return out
    except PyMongoError as e:
        raise _translate_pymongo_error(e, "list chunk ids") from e


async def get_chunks_by_ids(tenant_id: str, chunk_ids: list[str]) -> list[dict[str, Any]]:
    """
    Load chunks by chunk_ids scoped by tenant_id. Used by embedding stage.
    Returns list of chunk documents (order not guaranteed).
    """
    if not chunk_ids:
        return []
    coll = chunks_collection()
    try:
        cursor = coll.find(
            {**tenant_filter(tenant_id), "chunk_id": {"$in": list(chunk_ids)}}
        )
        return [doc async for doc in cursor]
    except PyMongoError as e:
        raise _translate_pymongo_error(e, "get chunks by ids") from e


async def upsert_chunks(
    tenant_id: str,
    document_id: str,
    chunk_docs: list[dict[str, Any]],
) -> tuple[int, int]:
    """
    Insert or update chunks using bulk_write for performance. Idempotency: same (document_id, chunk_hash) results in one record.
    Per §3.1.2 and §8.2: same document + strategy + config → skip or update by hash.
    Returns (inserted_count, updated_count).
    """
    if not chunk_docs:
        return 0, 0

    coll = chunks_collection()
    now = utc_now()
    
    # Prepare bulk operations
    operations: list[ReplaceOne] = []
    for doc in chunk_docs:
        storage_doc = dict(doc)
        storage_doc.setdefault("updated_at", now)
        storage_doc.setdefault("created_at", now)
        filter_ = {
            **tenant_document_filter(tenant_id, document_id),
            "chunk_hash": doc["chunk_hash"],
        }
        operations.append(ReplaceOne(filter_, storage_doc, upsert=True))

    try:
        result = await coll.bulk_write(operations, ordered=False)
        inserted = result.upserted_count
        updated = result.modified_count
        return inserted, updated
    except PyMongoError as e:
        raise _translate_pymongo_error(e, "upsert chunks") from e
