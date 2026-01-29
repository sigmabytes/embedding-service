"""Sentence-boundary chunking (§5.1). Splits on sentence boundaries with min/max chunk size."""

import re

from app.config.chunking.models import ChunkingConfig
from app.services.chunking.tokenizer import count_tokens


def _split_sentences(text: str) -> list[str]:
    """Split on sentence boundaries (period, !, ? followed by space or end)."""
    if not text or not text.strip():
        return []
    # Split on . ! ? when followed by space or end
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def sentence_boundary_chunks(text: str, config: ChunkingConfig) -> list[str]:
    """
    Split on sentence boundaries. Accumulate sentences until chunk_size (in tokens)
    is reached, respecting min_chunk_size and max_chunk_size when set.
    """
    if not text or not text.strip():
        return []
    sentences = _split_sentences(text)
    if not sentences:
        return [text] if text.strip() else []
    min_sz = config.min_chunk_size or 1
    max_sz = config.max_chunk_size or config.chunk_size * 2
    target = config.chunk_size
    chunks: list[str] = []
    buf: list[str] = []
    buf_tokens = 0
    for s in sentences:
        s_tokens = count_tokens(s, config.tokenizer)
        if buf_tokens + s_tokens > max_sz and buf:
            chunk_text = " ".join(buf)
            if buf_tokens >= min_sz:
                chunks.append(chunk_text)
            buf = [s]
            buf_tokens = s_tokens
        else:
            buf.append(s)
            buf_tokens += s_tokens
            if buf_tokens >= target or buf_tokens >= max_sz:
                chunks.append(" ".join(buf))
                buf = []
                buf_tokens = 0
    if buf:
        chunk_text = " ".join(buf)
        if buf_tokens >= min_sz:
            chunks.append(chunk_text)
        elif chunks:
            chunks[-1] = chunks[-1] + " " + chunk_text
        else:
            chunks.append(chunk_text)
    return chunks
