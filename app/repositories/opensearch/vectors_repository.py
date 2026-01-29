"""
Async write vectors and metadata from embedding records into an OpenSearch index (§4.3).
Idempotent: same embedding_id + same index → update or skip. Re-indexing is safe and cheap.
"""

from typing import Any

from opensearchpy import AsyncOpenSearch
from opensearchpy.helpers import async_bulk

from app.config.logging import get_logger
from app.resources.opensearch.client import get_opensearch_client
from app.resources.opensearch.index_manager import VECTOR_FIELD_NAME

logger = get_logger(__name__)


def _embedding_to_index_doc(
    embedding: dict[str, Any],
    chunk_by_chunk_id: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Map one embedding document (from MongoDB) to OpenSearch index document."""
    vector = embedding.get("embedding_vector") or []
    chunk_id = embedding.get("chunk_id") or ""
    chunk_text = (chunk_by_chunk_id or {}).get(chunk_id, "")
    return {
        VECTOR_FIELD_NAME: vector,
        "chunk_text": chunk_text,
        "document_id": embedding.get("document_id") or "",
        "tenant_id": embedding.get("tenant_id") or "",
        "chunk_id": chunk_id,
        "embedding_id": embedding.get("embedding_id") or "",
    }


async def bulk_index_vectors(
    index_name: str,
    embeddings: list[dict[str, Any]],
    *,
    chunk_by_chunk_id: dict[str, str] | None = None,
    client: AsyncOpenSearch | None = None,
) -> tuple[int, list[dict[str, Any]]]:
    """
    Bulk-index vectors and metadata into the given OpenSearch index.
    Uses embedding_id as document _id for idempotent upserts (§4.3: same embedding + same index → update or skip).
    chunk_by_chunk_id: optional map chunk_id -> chunk_text (from chunks collection); if missing, chunk_text is empty.
    Returns (success_count, errors) where errors is a list of {item_id, error, error_code} for failed items.
    """
    if client is None:
        client = get_opensearch_client()
    if not embeddings:
        return 0, []

    chunk_map = chunk_by_chunk_id or {}
    actions: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    valid_embeddings = []  # Track embeddings that will be indexed
    for emb in embeddings:
        eid = emb.get("embedding_id")
        if not eid:
            # Track embeddings without embedding_id as errors
            chunk_id = emb.get("chunk_id", "unknown")
            errors.append({
                "item_id": chunk_id,
                "error": "Embedding missing embedding_id field",
                "error_code": "MISSING_EMBEDDING_ID"
            })
            continue
        doc = _embedding_to_index_doc(emb, chunk_map)
        actions.append({"index": {"_index": index_name, "_id": eid}})
        actions.append(doc)
        valid_embeddings.append(eid)  # Track this embedding for counting

    success_count = 0
    try:
        logger.info(
            "Bulk indexing starting",
            extra={
                "index_name": index_name,
                "embeddings_count": len(embeddings),
                "valid_embeddings_count": len(valid_embeddings),
                "actions_count": len(actions),
                "expected_operations": len(valid_embeddings),  # Should be 1 operation per embedding
            },
        )
        success, failed = await async_bulk(
            client,
            actions,
            index=index_name,
            raise_on_error=False,
            raise_on_exception=False,
            request_timeout=60,
        )
        # The bulk() function returns the count of successful items (operations + documents),
        # but we want the count of successful operations (embeddings indexed).
        # Since each embedding creates 2 items in actions (operation + document),
        # we need to count successful operations by checking which embeddings succeeded.
        # If bulk() returns success count, it's counting items, not operations.
        # So we count successful operations by checking failed items and subtracting from total.
        if failed:
            failed_ids = {item.get("index", {}).get("_id") for item in failed if item.get("index", {}).get("_id")}
            success_count = len(valid_embeddings) - len(failed_ids)
        else:
            # If no failures, all valid embeddings succeeded
            success_count = len(valid_embeddings)
        
        logger.info(
            "Bulk indexing completed",
            extra={
                "index_name": index_name,
                "bulk_success_items": success,  # What bulk() returned (items, not operations)
                "success_count_operations": success_count,  # What we're returning (operations/embeddings)
                "failed_count": len(failed) if failed else 0,
                "valid_embeddings_input": len(valid_embeddings),
            },
        )
        if failed:
            for item in failed:
                idx_op = item.get("index", {})
                err = idx_op.get("error", {})
                # Handle both dict and string error formats
                if isinstance(err, dict):
                    err_type = err.get("type", "unknown")
                    err_reason = err.get("reason", str(err))
                else:
                    # Error is a string or other type
                    err_type = "unknown"
                    err_reason = str(err)
                doc_id = idx_op.get("_id", "unknown")
                errors.append(
                    {
                        "item_id": doc_id,
                        "error": err_reason,
                        "error_code": err_type.upper().replace(" ", "_"),
                    }
                )
            logger.warning(
                "Bulk index had failures",
                extra={"index_name": index_name, "success": success, "failed_count": len(failed)},
            )
    except Exception as e:
        logger.exception("Bulk index failed", extra={"index_name": index_name})
        for emb in embeddings:
            eid = emb.get("embedding_id") or "unknown"
            errors.append({"item_id": eid, "error": str(e), "error_code": "BULK_INDEX_FAILED"})
        return 0, errors

    return success_count, errors
