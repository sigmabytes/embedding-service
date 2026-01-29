"""Base embedding strategy and contract (§6.1, §6.2)."""

from abc import ABC, abstractmethod

from app.config.embedding.models import EmbeddingConfig


class BaseEmbeddingStrategy(ABC):
    """
    Abstract embedding strategy. Each strategy produces vectors with consistent dimension
    and does not perform normalization (handled by the embedder service per §6.4).
    """

    @abstractmethod
    def embed(self, texts: list[str], config: EmbeddingConfig) -> list[list[float]]:
        """
        Embed a list of texts. Returns one vector per text in the same order.
        Caller is responsible for preprocessing and normalization.
        """
        ...

    @property
    @abstractmethod
    def strategy_name(self) -> str:
        """Strategy identifier, e.g. 'openai', 'sentence_transformers'."""
        ...
