"""Id generation for documents, chunks, and embeddings. Deterministic where required."""

import hashlib
import uuid


def generate_chunk_id(document_id: str, chunk_index: int, chunk_hash: str) -> str:
    """Generate a deterministic chunk_id from document, index, and hash. Stable for idempotency."""
    payload = f"{document_id}:{chunk_index}:{chunk_hash}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
    return f"chunk_{digest}"


def generate_uuid_prefix(prefix: str) -> str:
    """Generate a unique id with prefix, e.g. emb_<uuid>."""
    return f"{prefix}_{uuid.uuid4().hex[:24]}"


def generate_embedding_id() -> str:
    """Generate a unique embedding_id per §3.1.3."""
    return generate_uuid_prefix("emb")
