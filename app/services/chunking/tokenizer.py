"""Tokenizer and token counting for chunking. Supports tiktoken; transformers optional."""

from app.config.logging import get_logger

logger = get_logger(__name__)

_tiktoken_encoding = None


def _get_tiktoken_encoding():
    """Lazy-load tiktoken encoding (cl100k_base used by OpenAI)."""
    global _tiktoken_encoding
    if _tiktoken_encoding is None:
        try:
            import tiktoken
            _tiktoken_encoding = tiktoken.get_encoding("cl100k_base")
        except Exception as e:
            logger.warning(
                "tiktoken not available, tokenizer will use character fallback",
                extra={"error": str(e)},
            )
            # leave _tiktoken_encoding as None
    return _tiktoken_encoding


def count_tokens(text: str, tokenizer_name: str | None = "tiktoken") -> int:
    """Return token count for text. Uses tiktoken when tokenizer_name is 'tiktoken'."""
    if not text:
        return 0
    enc = _get_tiktoken_encoding()
    if enc is not None:
        return len(enc.encode(text))
    # Fallback: rough approx 4 chars per token
    return max(1, len(text) // 4)


def tokenize_with_offsets(text: str, tokenizer_name: str | None = "tiktoken") -> list[tuple[str, int, int]]:
    """
    Return list of (token, start, end) for the text. Used by fixed-size strategies.
    If tiktoken unavailable, splits on whitespace and keeps char spans.
    """
    if not text:
        return []
    enc = _get_tiktoken_encoding()
    if enc is not None:
        tokens = enc.encode(text)
        # Decode back to get approximate spans by decoding ranges
        out: list[tuple[str, int, int]] = []
        offset = 0
        for t in tokens:
            piece = enc.decode([t])
            start = text.find(piece, offset)
            if start < 0:
                start = offset
            end = start + len(piece)
            offset = end
            out.append((piece, start, end))
        return out
    # Fallback: split on whitespace
    import re
    out = []
    for m in re.finditer(r"\S+", text):
        out.append((m.group(), m.start(), m.end()))
    return out
