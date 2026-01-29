"""Indexing strategy implementations (§7.1): cosine_knn, l2_knn, dot_product_knn, hnsw."""

from app.config.indexing.static import resolve_indexing_config


def get_indexing_strategy(strategy_name: str) -> IndexingConfig | None:
    """
    Return IndexingConfig for the given strategy name (e.g. cosine_knn, l2_knn, dot_product_knn, hnsw)
    or profile name (e.g. cosine_default). Returns None if unknown.
    """
    try:
        return resolve_indexing_config(strategy_name)
    except ValueError:
        return None
