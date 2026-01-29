"""MongoDB connection config (read from settings). Read-only; no business logic."""

from app.config.settings import Settings, get_settings


def get_mongo_config() -> dict:
    """Return MongoDB connection parameters from settings for use by resources."""
    s = get_settings()
    return {
        "uri": s.mongo_uri,
        "database": s.mongo_database,
        "connect_timeout_ms": s.mongo_connect_timeout_ms,
        "server_selection_timeout_ms": s.mongo_server_selection_timeout_ms,
        "max_pool_size": s.mongo_max_pool_size,
    }
