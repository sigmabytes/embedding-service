"""Async read raw documents by document_id and tenant_id from raw_documents (§3.1.1). No writes."""

from typing import Any

from pymongo.errors import PyMongoError

from app.repositories.mongodb.base import (
    RepositoryError,
    raw_documents_collection,
    tenant_document_filter,
    tenant_filter,
    _translate_pymongo_error,
)


async def get_raw_document(tenant_id: str, document_id: str) -> dict[str, Any] | None:
    """
    Return the raw document for the given tenant_id and document_id, or None if not found.
    Per §3.1.1; raw_documents are assumed to exist from a crawler (this service does not write them).
    Supports both PRD-shaped docs (document_id) and crawler-shaped docs (source_id): if lookup by
    (tenant_id, document_id) fails, tries (tenant_id, source_id=document_id) so callers can pass
    source_id as document_id for crawler-imported docs.
    """
    coll = raw_documents_collection()
    try:
        doc = await coll.find_one(tenant_document_filter(tenant_id, document_id))
        if doc is not None:
            return doc
        doc = await coll.find_one({"tenant_id": tenant_id, "source_id": document_id})
        return doc
    except PyMongoError as e:
        raise _translate_pymongo_error(e, "read raw document") from e


async def list_document_ids(tenant_id: str, limit: int = 100) -> list[str]:
    """
    Return document ids for the tenant, up to `limit`. Uses document_id or source_id from raw_documents.
    """
    coll = raw_documents_collection()
    try:
        cursor = coll.find(tenant_filter(tenant_id), {"document_id": 1, "source_id": 1}).limit(limit)
        out: list[str] = []
        async for doc in cursor:
            doc_id = doc.get("document_id") or doc.get("source_id")
            if doc_id and doc_id not in out:
                out.append(doc_id)
        return out
    except PyMongoError as e:
        raise _translate_pymongo_error(e, "list document ids") from e
