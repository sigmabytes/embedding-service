"""Request/response schemas for POST /chunk per §4.1."""

from pydantic import BaseModel, Field


class ChunkRequest(BaseModel):
    """POST /chunk request body. Count of documents to chunk; doc/tenant ids fetched from DB. Strategy from static.json."""

    tenant_id: str = Field(..., min_length=1, description="Tenant id (scope: which documents to chunk)")
    limit: int = Field(..., ge=1, le=1000, description="How many documents to chunk (max 1000)")
    chunk_size: int | None = Field(default=None, ge=1, le=10000, description="Optional override for chunk size (max 10000)")
    overlap: int | None = Field(default=None, ge=0, le=5000, description="Optional override for overlap between chunks (max 5000)")


class ChunkResponse(BaseModel):
    """POST /chunk response body. Batch result: N documents chunked, total chunks."""

    documents_chunked: int = Field(..., ge=0, description="Number of documents chunked")
    documents_failed: int = Field(default=0, ge=0)
    total_chunks_created: int = Field(..., ge=0, description="Total chunks created/updated across all docs")
    chunk_ids: list[str] = Field(default_factory=list)
    status: str = Field(..., description="success|partial|failed")
