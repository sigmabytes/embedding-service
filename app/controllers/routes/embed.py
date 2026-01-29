"""POST /embed: generate embeddings for chunks and store in MongoDB (§4.2)."""

from fastapi import APIRouter, HTTPException

from app.config.embedding.static import get_active_profile_name, resolve_embedding_config
from app.controllers.schema.embed import EmbedRequest, EmbedResponse
from app.repositories.mongodb.base import RepositoryError
from app.repositories.mongodb.chunks_repository import list_chunk_ids
from app.services.embedder.pipeline import run_embed_pipeline

router = APIRouter(prefix="/embed", tags=["embedding"])


@router.post("", response_model=EmbedResponse)
async def embed_chunks(body: EmbedRequest) -> EmbedResponse:
    """
    Embed up to `limit` chunks for the tenant. Chunk ids are fetched from the DB.
    Strategy and options come from static.json (active profile); only config can be overridden.
    Same chunk + same model + config → skip (idempotent). Partial failures recorded per §9.2.
    """
    strategy_name = get_active_profile_name()
    try:
        config = resolve_embedding_config(strategy_name, body.embedding_config)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    try:
        chunk_ids = await list_chunk_ids(body.tenant_id, limit=body.limit)
    except RepositoryError as e:
        raise HTTPException(status_code=503, detail="Storage temporarily unavailable") from e

    if not chunk_ids:
        return EmbedResponse(
            embeddings_created=0,
            embeddings_skipped=0,
            embeddings_failed=0,
            embedding_ids=[],
            status="success",
            errors=[],
        )

    try:
        created, skipped, failed, embedding_ids, errors = await run_embed_pipeline(
            chunk_ids=chunk_ids,
            tenant_id=body.tenant_id,
            config=config,
        )
    except RepositoryError as e:
        raise HTTPException(status_code=503, detail="Storage temporarily unavailable") from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    if failed and not created and not skipped:
        status = "failed"
    elif failed:
        status = "partial"
    else:
        status = "success"

    return EmbedResponse(
        embeddings_created=created,
        embeddings_skipped=skipped,
        embeddings_failed=failed,
        embedding_ids=embedding_ids,
        status=status,
        errors=errors,
    )
