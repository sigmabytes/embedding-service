"""OpenSearch connection config (read from settings). Read-only; no business logic."""

from app.config.settings import get_settings


def get_opensearch_config() -> dict:
    """Return OpenSearch connection parameters from settings for use by resources."""
    s = get_settings()
    return {
        "host": s.opensearch_host,
        "username": s.opensearch_username,
        "password": s.opensearch_password,
        "use_ssl": s.opensearch_use_ssl,
        "verify_certs": s.opensearch_verify_certs,
        "timeout": s.opensearch_timeout,
    }
