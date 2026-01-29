"""Vector normalization per §6.4 (L2, L1, none)."""

from __future__ import annotations

import math
from typing import Literal

NormType = Literal["L2", "L1", "none"]


def _l2_norm(vec: list[float]) -> float:
    return math.sqrt(sum(x * x for x in vec)) or 1.0


def _l1_norm(vec: list[float]) -> float:
    return sum(abs(x) for x in vec) or 1.0


def normalize_vector(vec: list[float], norm_type: NormType) -> tuple[list[float], float]:
    """
    Normalize a vector in-place semantics (returns new list).
    Returns (normalized_vector, original_norm).
    For 'none', returns (vec copy, 0.0).
    """
    if norm_type == "none" or norm_type not in ("L2", "L1"):
        return list(vec), 0.0
    if norm_type == "L2":
        n = _l2_norm(vec)
    else:
        n = _l1_norm(vec)
    return [x / n for x in vec], n


def apply_normalization(
    vectors: list[list[float]], norm_type: NormType
) -> list[tuple[list[float], float]]:
    """
    Normalize each vector. Returns list of (normalized_vector, original_norm).
    """
    return [normalize_vector(v, norm_type) for v in vectors]
