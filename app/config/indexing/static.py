"""Static indexing config loader. Read-only; no business logic."""

import json
from pathlib import Path
from typing import Any

from app.config.indexing.models import IndexingConfig

_config_dir = Path(__file__).resolve().parent
_config_path = _config_dir / "static.json"

_cached: dict[str, IndexingConfig] | None = None

# Strategy name → profile name (§7.1). API may send "cosine_knn" or profile "cosine_default".
STRATEGY_TO_PROFILE = {
    "cosine_knn": "cosine_default",
    "l2_knn": "l2_default",
    "dot_product_knn": "dot_product_default",
    "hnsw": "cosine_default",  # HNSW tuning; reuse cosine profile (override hnsw_config inline if needed)
}


def load_indexing_profiles() -> dict[str, IndexingConfig]:
    """Load indexing profiles from static.json. Keys are profile names."""
    global _cached
    if _cached is not None:
        return _cached
    raw = _config_path.read_text(encoding="utf-8")
    data = json.loads(raw)
    profiles = data.get("profiles", {})
    _cached = {k: IndexingConfig.model_validate(v) for k, v in profiles.items()}
    return _cached


def get_indexing_config(profile_name: str) -> IndexingConfig | None:
    """Return indexing config for the given profile, or None if missing."""
    return load_indexing_profiles().get(profile_name)


def resolve_indexing_config(profile_or_inline: str | dict[str, Any]) -> IndexingConfig:
    """
    Resolve indexing config from a profile name (str), strategy name (str), or inline object (dict).
    Strategy names (cosine_knn, l2_knn, dot_product_knn, hnsw) map to profiles per §7.1.
    Raises ValueError if profile/strategy unknown or inline dict invalid.
    """
    if isinstance(profile_or_inline, dict):
        return IndexingConfig.model_validate(profile_or_inline)
    name = profile_or_inline.strip()
    profile_name = STRATEGY_TO_PROFILE.get(name) or name
    config = get_indexing_config(profile_name)
    if config is None:
        raise ValueError(f"Unknown indexing profile or strategy: {profile_or_inline!r}")
    return config
