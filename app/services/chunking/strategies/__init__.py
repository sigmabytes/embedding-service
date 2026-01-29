"""Chunking strategy implementations (§5.1)."""

from typing import Callable

from app.config.chunking.models import ChunkingConfig
from app.services.chunking.strategies.fixed_tokens import fixed_token_chunks
from app.services.chunking.strategies.sliding_window import sliding_window_chunks
from app.services.chunking.strategies.sentence_boundary import sentence_boundary_chunks
from app.services.chunking.strategies.html_structure import html_structure_chunks

STRATEGY_REGISTRY: dict[str, Callable[[str, ChunkingConfig], list[str]]] = {
    "fixed_token": fixed_token_chunks,
    "sliding_window": sliding_window_chunks,
    "sentence_boundary": sentence_boundary_chunks,
    "sentence_based": sentence_boundary_chunks,  # alias per §5.3
    "html_structure": html_structure_chunks,
}


def get_strategy_fn(strategy_name: str):
    """Return the chunking function for the given strategy name, or None."""
    return STRATEGY_REGISTRY.get(strategy_name)
