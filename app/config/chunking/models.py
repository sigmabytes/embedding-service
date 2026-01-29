"""Chunking configuration models. Read-only; no business logic."""

from typing import Any

from pydantic import BaseModel, Field


class ChunkingConfig(BaseModel):
    """Chunking strategy and parameters (§5.3)."""

    strategy: str = Field(..., description="fixed_token|sliding_window|sentence_based|html_structure")
    chunk_size: int = Field(default=512, ge=1, description="Target chunk size")
    overlap: int = Field(default=50, ge=0, description="Overlap between chunks")
    tokenizer: str | None = Field(default=None, description="tiktoken|transformers")
    min_chunk_size: int | None = Field(default=None, ge=1)
    max_chunk_size: int | None = Field(default=None, ge=1)
    preserve_whitespace: bool = Field(default=True)
    custom_params: dict[str, Any] = Field(default_factory=dict)
