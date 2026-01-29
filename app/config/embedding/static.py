"""Static embedding config loader. Read-only; no business logic."""

import json
from pathlib import Path
from typing import Any

from app.config.embedding.models import EmbeddingConfig
from app.config.embedding.providers import get_embedding_config

_config_dir = Path(__file__).resolve().parent
_config_path = _config_dir / "static.json"

_active_profile: str | None = None


def _load_raw_data() -> dict[str, Any]:
    """Load raw JSON for active profile and profiles."""
    raw = _config_path.read_text(encoding="utf-8")
    return json.loads(raw)


def get_active_profile_name() -> str:
    """Return the profile name marked as active in static.json. Defaults to 'openai_default' if missing."""
    global _active_profile
    if _active_profile is not None:
        return _active_profile
    data = _load_raw_data()
    _active_profile = data.get("active", "openai_default")
    return _active_profile


_STRATEGY_TO_PROFILE: dict[str, str] = {
    "openai": "openai_default",
    "sentence_transformers": "sentence_default",
    "bedrock": "bedrock_default",
}


def resolve_embedding_config(
    profile_name: str,
    inline_config: dict[str, Any] | None = None,
) -> EmbeddingConfig:
    """
    Resolve embedding config by profile name and optional inline overrides.
    If inline_config is provided and non-empty, it is merged over the profile config.
    If profile_name is 'active', use the profile marked as active in static.json.
    Strategy names 'openai' and 'sentence_transformers' map to openai_default / sentence_default.
    Raises ValueError if profile is missing when no inline_config given.
    """
    if profile_name == "active":
        name = get_active_profile_name()
    else:
        name = _STRATEGY_TO_PROFILE.get(profile_name, profile_name)
    base = get_embedding_config(name)
    if base is None:
        raise ValueError(f"Unknown embedding profile: {name!r}")
    if not inline_config or len(inline_config) == 0:
        return base
    merged = {**base.model_dump(), **inline_config}
    return EmbeddingConfig.model_validate(merged)
