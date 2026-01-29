"""Text preprocessing for embedding (§6.4). Applied before calling the embedding strategy."""

import re

from app.config.embedding.models import EmbeddingPreprocessing


def preprocess_text(text: str, opts: EmbeddingPreprocessing) -> str:
    """
    Apply preprocessing to a single text: lowercase, remove_punctuation, truncate by max_length.
    max_length is applied as character length (simple slice).
    """
    if not text:
        return ""
    s = text
    if opts.lowercase:
        s = s.lower()
    if opts.remove_punctuation:
        s = re.sub(r"[^\w\s]", "", s, flags=re.UNICODE)
    if opts.max_length > 0 and len(s) > opts.max_length:
        s = s[: opts.max_length]
    return s


def preprocess_texts(texts: list[str], opts: EmbeddingPreprocessing) -> list[str]:
    """Apply preprocessing to each text."""
    return [preprocess_text(t, opts) for t in texts]
