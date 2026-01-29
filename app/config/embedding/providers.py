"""Embedding provider/config resolution. Read-only; no business logic."""

import json
from pathlib import Path

from app.config.embedding.models import EmbeddingConfig

_config_dir = Path(__file__).resolve().parent
_config_path = _config_dir / "static.json"

_cached: dict[str, EmbeddingConfig] | None = None


def load_embedding_profiles() -> dict[str, EmbeddingConfig]:
    """Load embedding profiles from static.json. Keys are profile names."""
    global _cached
    if _cached is not None:
        return _cached
    raw = _config_path.read_text(encoding="utf-8")
    data = json.loads(raw)
    profiles = data.get("profiles", {})
    _cached = {k: EmbeddingConfig.model_validate(v) for k, v in profiles.items()}
    return _cached


def get_embedding_config(profile_name: str) -> EmbeddingConfig | None:
    """Return embedding config for the given profile, or None if missing."""
    return load_embedding_profiles().get(profile_name)
