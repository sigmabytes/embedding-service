"""Fixed-size token chunking (§5.1). Splits text into fixed-size token chunks with optional overlap."""

from app.config.chunking.models import ChunkingConfig
from app.services.chunking.tokenizer import tokenize_with_offsets


def fixed_token_chunks(text: str, config: ChunkingConfig) -> list[str]:
    """
    Split text into fixed-size token chunks. Overlap is applied by stepping
    (chunk_size - overlap) tokens forward each time.
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
