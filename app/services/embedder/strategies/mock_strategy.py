"""Mock embedding strategy for tests. Produces deterministic fake vectors."""

from app.config.embedding.models import EmbeddingConfig
from app.services.embedder.base import BaseEmbeddingStrategy

# Default dimension for mock when model is unknown
MOCK_DEFAULT_DIM = 384


def _mock_dimension_for_model(model: str) -> int:
    if "ada-002" in model or "1536" in model:
        return 1536
    if "3-large" in model:
        return 3072
    if "3-small" in model:
        return 1536
    return MOCK_DEFAULT_DIM


class MockEmbeddingStrategy(BaseEmbeddingStrategy):
    """
    Deterministic fake embeddings: hash of text seeded by index to produce stable vectors.
    Used for tests; dimension inferred from model name or default 384.
    """

    @property
    def strategy_name(self) -> str:
        return "mock"

    def embed(self, texts: list[str], config: EmbeddingConfig) -> list[list[float]]:
        dim = _mock_dimension_for_model(config.model)
        result: list[list[float]] = []
        for i, t in enumerate(texts):
            # Deterministic: same (text, index) -> same vector
            h = hash((t, i)) % (2**32)
            vec = [(float((h + j) % 1000) / 1000.0) for j in range(dim)]
            # Simple L2-like scale so norms are non-zero
            norm = (sum(x * x for x in vec)) ** 0.5 or 1.0
            vec = [x / norm for x in vec]
            result.append(vec)
        return result
