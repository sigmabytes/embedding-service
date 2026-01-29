"""Request/response schemas for POST /embed per §4.2."""

from typing import Any

from pydantic import BaseModel, Field


class EmbedRequest(BaseModel):
    """POST /embed request body. Chunk ids fetched from DB; strategy from static.json (active profile)."""

    tenant_id: str = Field(..., min_length=1, description="Tenant id (scope: which chunks to embed)")
    limit: int = Field(..., ge=1, le=1000, description="Number of chunks to embed (max 1000)")
    embedding_config: dict[str, Any] | None = Field(
        default=None,
        description="Optional overrides for model, normalize, preprocessing, etc.",
    )


class EmbedResponse(BaseModel):
    """POST /embed response body per §4.2."""

    embeddings_created: int = Field(..., ge=0, description="Number of embeddings created")
    embeddings_skipped: int = Field(default=0, ge=0, description="Skipped (already existed)")
    embeddings_failed: int = Field(default=0, ge=0, description="Number of failures")
    embedding_ids: list[str] = Field(default_factory=list, description="Ids for created + skipped")
    status: str = Field(..., description="success|partial|failed")
    errors: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Per-item errors when status is partial or failed (§9.4)",
    )
