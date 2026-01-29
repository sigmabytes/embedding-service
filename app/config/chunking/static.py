"""Static chunking config loader. Read-only; no business logic."""

import json
from pathlib import Path

from app.config.chunking.models import ChunkingConfig

_config_dir = Path(__file__).resolve().parent
_config_path = _config_dir / "static.json"

_cached: dict[str, ChunkingConfig] | None = None
_active_profile: str | None = None


def _load_raw_data() -> dict:
    """Load raw JSON; used to read both profiles and active."""
    raw = _config_path.read_text(encoding="utf-8")
    return json.loads(raw)


def load_chunking_profiles() -> dict[str, ChunkingConfig]:
    """Load chunking profiles from static.json. Keys are profile names."""
    global _cached
    if _cached is not None:
        return _cached
    data = _load_raw_data()
    profiles = data.get("profiles", {})
    _cached = {k: ChunkingConfig.model_validate(v) for k, v in profiles.items()}
    return _cached


def get_chunking_config(profile_name: str) -> ChunkingConfig | None:
    """Return chunking config for the given profile, or None if missing."""
    return load_chunking_profiles().get(profile_name)


def get_active_profile_name() -> str:
    """Return the profile name marked as active in static.json. Defaults to 'default' if missing."""
    global _active_profile
    if _active_profile is not None:
        return _active_profile
    data = _load_raw_data()
    _active_profile = data.get("active", "default")
    return _active_profile


def get_active_chunking_config() -> ChunkingConfig:
    """Return the chunking config for the active profile. Uses get_active_profile_name()."""
    name = get_active_profile_name()
    cfg = get_chunking_config(name)
    if cfg is None:
        raise ValueError(f"Active profile {name!r} not found in profiles")
    return cfg


def resolve_chunking_config(profile_name: str, inline_config: dict | None = None) -> ChunkingConfig:
    """
    Resolve chunking config by profile name or inline config.
    If inline_config is provided and non-empty, validate and return it.
    If profile_name is "active", use the profile marked as active in static.json.
    Otherwise load by profile_name. Raises ValueError if profile is missing when no inline_config given.
    """
    if inline_config:
        return ChunkingConfig.model_validate(inline_config)
    if profile_name == "active":
        return get_active_chunking_config()
    cfg = get_chunking_config(profile_name)
    if cfg is None:
        raise ValueError(f"Unknown chunking profile or strategy: {profile_name!r}")
    return cfg
