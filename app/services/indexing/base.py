"""Base indexing strategy (§7.1). Defines how the index is built and which similarity/mapping to use."""

from abc import ABC, abstractmethod

from app.config.indexing.models import IndexingConfig


class BaseIndexingStrategy(ABC):
    """
    Indexing strategy: defines similarity, HNSW params, and metadata fields for the index.
    Strategy implementations (cosine_knn, l2_knn, dot_product_knn, hnsw) resolve to an IndexingConfig.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Strategy name for registration and API."""
        ...

    def get_config(self) -> IndexingConfig:
        """Return the IndexingConfig for this strategy (from static profile or defaults)."""
        from app.config.indexing.static import get_indexing_config

        cfg = get_indexing_config(self.name)
        if cfg is None:
            raise ValueError(f"Unknown indexing strategy profile: {self.name!r}")
        return cfg
