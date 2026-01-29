"""POST /chunk: chunk up to N documents for a tenant. Doc ids fetched from DB; strategy from static.json."""

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException

from app.config.chunking.static import get_active_profile_name, resolve_chunking_config
from app.controllers.schema.chunk import ChunkRequest, ChunkResponse
from app.repositories.mongodb.base import RepositoryError
from app.repositories.mongodb.documents_repository import list_document_ids
from app.services.chunking.chunker import run_chunk_pipeline

router = APIRouter(prefix="/chunk", tags=["chunking"])


async def _process_document(
    tenant_id: str,
    document_id: str,
    strategy_name: str,
    inline_config: dict[str, Any] | None,
) -> tuple[list[str], bool]:
    """
    Process a single document and return (chunk_ids, success).
    Returns empty list and False on failure.
    """
    try:
        chunk_ids, _, _ = await run_chunk_pipeline(
            tenant_id=tenant_id,
            document_id=document_id,
            chunking_strategy=strategy_name,
            chunking_config_inline=inline_config,
        )
        return chunk_ids, True
    except ValueError:
        return [], False
    except RepositoryError:
        # Re-raise RepositoryError to be handled at route level
        raise


@router.post("", response_model=ChunkResponse)
async def chunk_documents(body: ChunkRequest) -> ChunkResponse:
    """
    Chunk up to `limit` documents for the tenant. Document ids are fetched from the DB.
    Strategy and options come from static.json (active profile); only chunk_size/overlap can be overridden.
    Processes documents in parallel for better performance.
    """
    strategy_name = get_active_profile_name()
    base = resolve_chunking_config(strategy_name)
    overrides = {}
    if body.chunk_size is not None:
        overrides["chunk_size"] = body.chunk_size
    if body.overlap is not None:
        overrides["overlap"] = body.overlap
    inline_config = {**base.model_dump(), **overrides} if overrides else None

    try:
        doc_ids = await list_document_ids(body.tenant_id, limit=body.limit)
    except RepositoryError as e:
        raise HTTPException(status_code=503, detail="Storage temporarily unavailable") from e

    if not doc_ids:
        return ChunkResponse(
            documents_chunked=0,
            documents_failed=0,
            total_chunks_created=0,
            chunk_ids=[],
            status="success",
        )

    # Process documents in parallel using asyncio.gather
    # Each task processes one document independently
    tasks = [
        _process_document(
            tenant_id=body.tenant_id,
            document_id=document_id,
            strategy_name=strategy_name,
            inline_config=inline_config,
        )
        for document_id in doc_ids
    ]

    try:
        results = await asyncio.gather(*tasks, return_exceptions=True)
    except RepositoryError as e:
        raise HTTPException(status_code=503, detail="Storage temporarily unavailable") from e

    # Process results: collect chunk_ids and count successes/failures
    all_chunk_ids: list[str] = []
    chunked = 0
    failed = 0

    for result in results:
        if isinstance(result, Exception):
            # Handle unexpected exceptions
            failed += 1
            continue
        chunk_ids, success = result
        if success:
            all_chunk_ids.extend(chunk_ids)
            chunked += 1
        else:
            failed += 1

    total_chunks = len(all_chunk_ids)
    status = "success" if chunked else "failed"
    if failed and chunked:
        status = "partial"
    return ChunkResponse(
        documents_chunked=chunked,
        documents_failed=failed,
        total_chunks_created=total_chunks,
        chunk_ids=all_chunk_ids,
        status=status,
    )
