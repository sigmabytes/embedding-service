"""Request/response schemas for POST /index per §4.3."""

from typing import Any

from pydantic import BaseModel, Field, model_validator


class IndexInfo(BaseModel):
    """Index metadata returned in IndexResponse (§4.3)."""

    dimension: int = Field(..., ge=0, description="Vector dimension")
    similarity: str = Field(..., description="cosine|l2|dot_product")
    total_vectors: int = Field(..., ge=0, description="Count of vectors indexed in this request (incremental)")


class IndexRequest(BaseModel):
    """POST /index request body per §4.3."""

    embedding_ids: list[str] | None = Field(
        default=None, max_length=1000, description="Embedding ids to publish to OpenSearch (optional if limit is provided, max 1000)"
    )
    tenant_id: str = Field(..., min_length=1, description="Tenant id (scope: which embeddings to index)")
    index_name: str = Field(..., min_length=1, max_length=255, description="OpenSearch index name (create if not exists, max 255 chars)")
    indexing_strategy: str | dict[str, Any] = Field(
        ...,
        description="Profile name (e.g. cosine_default), strategy name (e.g. cosine_knn), or inline {similarity, hnsw_config}",
    )
    limit: int | None = Field(
        default=None, ge=1, le=1000, description="Number of embeddings to index (optional if embedding_ids is provided, max 1000)"
    )

    @model_validator(mode="after")
    def validate_embedding_ids_or_limit(self):
        """Ensure at least one of embedding_ids or limit is provided."""
        if not self.embedding_ids and self.limit is None:
            raise ValueError("Either embedding_ids or limit must be provided")
        if self.embedding_ids is not None and len(self.embedding_ids) == 0:
            raise ValueError("embedding_ids cannot be an empty list")
        return self


class IndexResponse(BaseModel):
    """POST /index response body per §4.3."""

    index_name: str = Field(..., description="OpenSearch index name")
    vectors_indexed: int = Field(..., ge=0, description="Number of vectors successfully indexed")
    vectors_failed: int = Field(default=0, ge=0, description="Number of vectors that failed to index")
    status: str = Field(..., description="success|partial|failed")
    index_info: IndexInfo = Field(..., description="Dimension, similarity, and total_vectors")
    errors: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Per-item errors when status is partial or failed (§9.4)",
    )
