"""OpenAI Embedding API strategy (§6.1)."""

from openai import OpenAI

from app.config.embedding.models import EmbeddingConfig
from app.config.settings import get_settings
from app.services.embedder.base import BaseEmbeddingStrategy


class OpenAIEmbeddingStrategy(BaseEmbeddingStrategy):
    """
    OpenAI Embeddings API. Models: text-embedding-ada-002, text-embedding-3-small, etc.
    API key from config.api_key or settings.openai_api_key.
    """

    @property
    def strategy_name(self) -> str:
        return "openai"

    def embed(self, texts: list[str], config: EmbeddingConfig) -> list[list[float]]:
        if not texts:
            return []
        api_key = config.api_key or get_settings().openai_api_key or None
        if not api_key:
            raise ValueError("OpenAI API key is required (set in config or OPENAI_API_KEY)")
        client = OpenAI(api_key=api_key)
        # Batch in chunks of config.batch_size to respect rate limits
        batch_size = min(config.batch_size, 2048)  # API limit per request
        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            response = client.embeddings.create(model=config.model, input=batch)
            # Preserve order by index
            by_index = {e.index: e.embedding for e in response.data}
            all_embeddings.extend([by_index[j] for j in range(len(batch))])
        return all_embeddings
