"""Sliding-window chunking (§5.1). Overlapping chunks with configurable window size."""

from app.config.chunking.models import ChunkingConfig
from app.services.chunking.tokenizer import tokenize_with_offsets


def sliding_window_chunks(text: str, config: ChunkingConfig) -> list[str]:
    """
    Produce overlapping chunks by sliding a window of chunk_size tokens with step (chunk_size - overlap).
    Same as fixed_token for implementation; overlap is the primary behavior.
    """
    if not text or not text.strip():
        return []
    size = config.chunk_size
    overlap = min(config.overlap, size - 1)
    step = max(1, size - overlap)
    tokens_with_offsets = tokenize_with_offsets(text, config.tokenizer)
    chunks: list[str] = []
    i = 0
    while i < len(tokens_with_offsets):
        slice_tokens = tokens_with_offsets[i : i + size]
        chunk_text = text[slice_tokens[0][1] : slice_tokens[-1][2]] if slice_tokens else ""
        if chunk_text.strip():
            chunks.append(chunk_text)
        i += step
    return chunks
