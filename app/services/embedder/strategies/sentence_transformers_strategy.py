"""Sentence Transformers (local) embedding strategy (§6.1)."""

from sentence_transformers import SentenceTransformer

from app.config.embedding.models import EmbeddingConfig
from app.services.embedder.base import BaseEmbeddingStrategy


class SentenceTransformersEmbeddingStrategy(BaseEmbeddingStrategy):
    """
    Local Sentence Transformers. Default model: sentence-transformers/all-MiniLM-L6-v3.
    No API key required.
    """

    def __init__(self) -> None:
        self._model: SentenceTransformer | None = None
        self._model_name: str | None = None

    @property
    def strategy_name(self) -> str:
        return "sentence_transformers"

    def _get_model(self, model_name: str) -> SentenceTransformer:
        if self._model is None or self._model_name != model_name:
            self._model = SentenceTransformer(model_name)
            self._model_name = model_name
        return self._model

    def embed(self, texts: list[str], config: EmbeddingConfig) -> list[list[float]]:
        if not texts:
            return []
        model = self._get_model(config.model)
        batch_size = config.batch_size
        vectors = model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return [v.tolist() for v in vectors]
