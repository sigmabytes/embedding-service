"""
Async create or update OpenSearch indices from an indexing strategy (§7.1–7.3).
Supports cosine, L2, and dot_product similarity and HNSW tuning. Handles dimension changes.
No business logic beyond index definition and mapping.
"""

from typing import Any

from opensearchpy.exceptions import RequestError, OpenSearchException

from app.config.indexing.models import IndexingConfig
from app.config.logging import get_logger
from app.resources.opensearch.client import get_opensearch_client

logger = get_logger(__name__)

# OpenSearch k-NN space_type per similarity (§7.1)
SIMILARITY_TO_SPACE_TYPE = {
    "cosine": "cosinesimil",
    "l2": "l2",
    "dot_product": "innerproduct",
}

VECTOR_FIELD_NAME = "embedding_vector"


def _space_type(similarity: str) -> str:
    """Map PRD similarity to OpenSearch space_type."""
    st = SIMILARITY_TO_SPACE_TYPE.get(similarity)
    if st is None:
        raise ValueError(f"Unsupported similarity: {similarity!r}. Use cosine, l2, or dot_product.")
    return st


def build_index_body(dimension: int, config: IndexingConfig) -> dict[str, Any]:
    """
    Build OpenSearch index settings and mappings for k-NN (§7.1–7.3).
    Uses HNSW with space_type from config.similarity and hnsw_config (m, ef_construction).
    """
    space = _space_type(config.similarity)
    hnsw = config.hnsw_config
    # Note: ef_search is a query-time parameter, not an index-time parameter
    # It should be set at query time, not during index creation
    params: dict[str, Any] = {
        "ef_construction": hnsw.ef_construction,
        "m": hnsw.m,
    }

    # k-NN vector field with HNSW method
    vector_prop: dict[str, Any] = {
        "type": "knn_vector",
        "dimension": dimension,
        "method": {
            "name": "hnsw",
            "space_type": space,
            "engine": "nmslib",
            "parameters": params,
        },
    }

    properties: dict[str, Any] = {
        VECTOR_FIELD_NAME: vector_prop,
        "chunk_text": {"type": "text", "fields": {"keyword": {"type": "keyword", "ignore_above": 512}}},
        "document_id": {"type": "keyword"},
        "tenant_id": {"type": "keyword"},
        "chunk_id": {"type": "keyword"},
        "embedding_id": {"type": "keyword"},
    }

    body: dict[str, Any] = {
        "settings": {
            "index": {
                "knn": True,
                "number_of_shards": config.index_settings.get("number_of_shards", 1),
                "number_of_replicas": config.index_settings.get("number_of_replicas", 1),
            }
        },
        "mappings": {"properties": properties},
    }
    return body


async def create_index_if_not_exists(
    index_name: str,
    dimension: int,
    config: IndexingConfig,
) -> bool:
    """
    Create the OpenSearch index if it does not exist. If it exists, check dimension compatibility.
    If dimension changed, delete and recreate the index (handles dimension changes).
    Returns True if index was created/recreated, False if it already existed with same dimension.
    Raises ValueError if index creation fails (e.g., invalid configuration).
    """
    client = get_opensearch_client()
    exists = await client.indices.exists(index=index_name)
    
    if exists:
        # Check if dimension matches
        try:
            mapping = await client.indices.get_mapping(index=index_name)
            index_mapping = mapping.get(index_name, {}).get("mappings", {}).get("properties", {})
            vector_field = index_mapping.get(VECTOR_FIELD_NAME, {})
            existing_dimension = vector_field.get("dimension")
            
            if existing_dimension is not None and existing_dimension != dimension:
                logger.warning(
                    "Index dimension mismatch detected",
                    extra={
                        "index_name": index_name,
                        "existing_dimension": existing_dimension,
                        "new_dimension": dimension,
                    },
                )
                # Delete and recreate index with new dimension
                await client.indices.delete(index=index_name)
                logger.info(
                    "Deleted index due to dimension change",
                    extra={"index_name": index_name, "old_dimension": existing_dimension, "new_dimension": dimension},
                )
                # Continue to create new index below
            else:
                logger.debug(
                    "Index already exists with compatible dimension",
                    extra={"index_name": index_name, "dimension": dimension},
                )
                return False
        except Exception as e:
            logger.warning(
                "Failed to check index dimension, will recreate",
                extra={"index_name": index_name, "error": str(e)},
            )
            # If we can't check, delete and recreate to be safe
            try:
                await client.indices.delete(index=index_name)
            except Exception:
                pass  # Ignore delete errors
    
    body = build_index_body(dimension, config)
    try:
        await client.indices.create(index=index_name, body=body)
        logger.info(
            "Index created",
            extra={
                "index_name": index_name,
                "dimension": dimension,
                "similarity": config.similarity,
            },
        )
        return True
    except RequestError as e:
        # Extract error message from RequestError
        error_message = str(e)
        if hasattr(e, "info") and isinstance(e.info, dict):
            error_info = e.info.get("error", {})
            if isinstance(error_info, dict) and "reason" in error_info:
                error_message = error_info["reason"]
        logger.error(
            "Failed to create OpenSearch index",
            extra={
                "index_name": index_name,
                "error": error_message,
                "error_type": type(e).__name__,
            },
        )
        raise ValueError(f"Failed to create index '{index_name}': {error_message}") from e
    except OpenSearchException as e:
        logger.error(
            "OpenSearch error during index creation",
            extra={
                "index_name": index_name,
                "error": str(e),
                "error_type": type(e).__name__,
            },
        )
        raise ValueError(f"OpenSearch error while creating index '{index_name}': {str(e)}") from e
