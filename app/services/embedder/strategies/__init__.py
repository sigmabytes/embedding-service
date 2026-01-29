"""Embedding strategy implementations (§6.1)."""

from app.services.embedder.base import BaseEmbeddingStrategy
from app.services.embedder.strategies.bedrock_strategy import BedrockEmbeddingStrategy
from app.services.embedder.strategies.openai_strategy import OpenAIEmbeddingStrategy
from app.services.embedder.strategies.sentence_transformers_strategy import (
    SentenceTransformersEmbeddingStrategy,
)
from app.services.embedder.strategies.mock_strategy import MockEmbeddingStrategy

STRATEGY_REGISTRY: dict[str, type[BaseEmbeddingStrategy]] = {
    "openai": OpenAIEmbeddingStrategy,
    "sentence_transformers": SentenceTransformersEmbeddingStrategy,
    "bedrock": BedrockEmbeddingStrategy,
    "mock": MockEmbeddingStrategy,
}


def get_embedding_strategy(strategy_name: str) -> BaseEmbeddingStrategy | None:
    """Return an instance of the embedding strategy for the given name, or None."""
    cls = STRATEGY_REGISTRY.get(strategy_name)
    if cls is None:
        return None
    return cls()
