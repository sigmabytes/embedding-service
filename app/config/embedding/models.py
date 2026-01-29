"""Embedding configuration models. Read-only; no business logic."""

from typing import Any

from pydantic import BaseModel, Field


class EmbeddingPreprocessing(BaseModel):
    """Preprocessing options (§6.4)."""

    lowercase: bool = Field(default=False)
    remove_punctuation: bool = Field(default=False)
    max_length: int = Field(default=8192, ge=1)


class EmbeddingConfig(BaseModel):
    """Embedding strategy and parameters (§6.4)."""

    strategy: str = Field(..., description="openai|sentence_transformers|bedrock")
    model: str = Field(..., description="Model identifier")
    normalize: bool = Field(default=True)
    normalization_type: str = Field(default="L2", description="L2|L1|none")
    preprocessing: EmbeddingPreprocessing = Field(default_factory=EmbeddingPreprocessing)
    batch_size: int = Field(default=100, ge=1)
    api_key: str | None = Field(default=None, description="OpenAI API key when strategy is openai")
    region: str | None = Field(default=None, description="AWS region when strategy is bedrock")
