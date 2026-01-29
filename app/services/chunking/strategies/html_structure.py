"""HTML-structure chunking (§5.1). Uses HTML tags for chunk boundaries."""

import re

from app.config.chunking.models import ChunkingConfig
from app.services.chunking.tokenizer import count_tokens


def _split_by_html_structure(text: str, config: ChunkingConfig) -> list[str]:
    """
    Split by block-level HTML elements (p, div, h1–h6, li, section, article).
    Each block becomes a candidate segment; we then respect chunk_size by merging.
    """
    if not text or not text.strip():
        return []
    # Strip script/style and split by block tags
    block_pattern = re.compile(
        r"</?(?:p|div|h[1-6]|li|section|article|blockquote)[^>]*>",
        re.IGNORECASE,
    )
    # Split and keep delimiters in separators; we want content between blocks
    parts = block_pattern.split(text)
    segments = [p.strip() for p in parts if p.strip() and not p.strip().startswith("<")]
    if not segments:
        # No block structure: treat whole text as one or fall back to size-based
        if not text.strip():
            return []
        return [text.strip()]
    return segments


def html_structure_chunks(text: str, config: ChunkingConfig) -> list[str]:
    """
    Chunk by HTML structure. Split on block-level tags, then merge segments
    to stay within chunk_size (and min/max when set).
    """
    if not text or not text.strip():
        return []
    segments = _split_by_html_structure(text, config)
    if not segments:
        return [text.strip()] if text.strip() else []
    min_sz = config.min_chunk_size or 1
    max_sz = config.max_chunk_size or config.chunk_size * 2
    target = config.chunk_size
    chunks: list[str] = []
    buf: list[str] = []
    buf_tokens = 0
    for seg in segments:
        s_tokens = count_tokens(seg, config.tokenizer)
        if buf_tokens + s_tokens > max_sz and buf:
            chunk_text = "\n".join(buf)
            if buf_tokens >= min_sz:
                chunks.append(chunk_text)
            buf = [seg]
            buf_tokens = s_tokens
        else:
            buf.append(seg)
            buf_tokens += s_tokens
            if buf_tokens >= target or buf_tokens >= max_sz:
                chunks.append("\n".join(buf))
                buf = []
                buf_tokens = 0
    if buf:
        chunk_text = "\n".join(buf)
        if buf_tokens >= min_sz:
            chunks.append(chunk_text)
        elif chunks:
            chunks[-1] = chunks[-1] + "\n" + chunk_text
        else:
            chunks.append(chunk_text)
    return chunks
