"""Text cleaners for chunking input. Preserve or normalize whitespace per config."""

import re


def normalize_whitespace(text: str, preserve_whitespace: bool = True) -> str:
    """
    Normalize whitespace. If preserve_whitespace is True, only collapse internal
    runs of space/newline to a single space; otherwise trim and collapse.
    """
    if not text or not isinstance(text, str):
        return ""
    if preserve_whitespace:
        # Collapse runs of whitespace to single space; keep single newlines as space
        return re.sub(r"[ \t\n\r]+", " ", text).strip()
    return " ".join(text.split())


def clean_for_chunking(text: str, preserve_whitespace: bool = True) -> str:
    """Clean raw content before chunking. Uses normalize_whitespace."""
    return normalize_whitespace(text, preserve_whitespace=preserve_whitespace)
