"""Indexing configuration models. Read-only; no business logic."""

from typing import Any

from pydantic import BaseModel, Field


class HNSWConfig(BaseModel):
    """HNSW tuning parameters (§7.3)."""

    m: int = Field(default=16, ge=1)
    ef_construction: int = Field(default=200, ge=1)
    ef_search: int | None = Field(default=None, ge=1)


class IndexingConfig(BaseModel):
    """Indexing strategy and parameters (§7.3)."""

    similarity: str = Field(..., description="cosine|l2|dot_product")
    hnsw_config: HNSWConfig = Field(default_factory=HNSWConfig)
    index_settings: dict[str, Any] = Field(
        default_factory=lambda: {"number_of_shards": 1, "number_of_replicas": 1}
    )
    metadata_fields: list[str] = Field(
        default_factory=lambda: ["chunk_text", "document_id", "tenant_id"]
    )
