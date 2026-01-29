"""POST /index: publish embeddings from MongoDB to OpenSearch (§4.3)."""

from fastapi import APIRouter, HTTPException

from app.config.indexing.static import resolve_indexing_config
from app.controllers.schema.index import IndexRequest, IndexResponse, IndexInfo
from app.repositories.mongodb.base import RepositoryError
from app.repositories.mongodb.embeddings_repository import list_embedding_ids
from app.services.indexing.publisher import run_index_pipeline

router = APIRouter(prefix="/index", tags=["indexing"])


@router.post("", response_model=IndexResponse)
async def index_embeddings(body: IndexRequest) -> IndexResponse:
    """
    Load embeddings by embedding_ids + tenant_id from MongoDB (or fetch up to `limit` embeddings if embedding_ids not provided);
    create or update OpenSearch index per indexing_strategy; bulk-publish vectors and metadata.
    Idempotent: same embedding + same index → update or skip. Partial failures recorded per §9.2.
    """
    try:
        config = resolve_indexing_config(body.indexing_strategy)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # If embedding_ids not provided, fetch them using limit
    embedding_ids = body.embedding_ids
    if embedding_ids is None:
        if body.limit is None:
            raise HTTPException(status_code=400, detail="Either embedding_ids or limit must be provided")
        try:
            embedding_ids = await list_embedding_ids(body.tenant_id, body.limit)
        except RepositoryError as e:
            raise HTTPException(status_code=503, detail="Storage temporarily unavailable") from e

        if not embedding_ids:
            return IndexResponse(
                index_name=body.index_name,
                vectors_indexed=0,
                vectors_failed=0,
                status="success",
                index_info=IndexInfo(dimension=0, similarity=config.similarity, total_vectors=0),
                errors=[],
            )

    try:
        vectors_indexed, vectors_failed, errors, dimension, similarity, total_vectors = await run_index_pipeline(
            embedding_ids=embedding_ids,
            tenant_id=body.tenant_id,
            index_name=body.index_name,
            config=config,
        )
    except RepositoryError as e:
        raise HTTPException(status_code=503, detail="Storage temporarily unavailable") from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    if vectors_failed and not vectors_indexed:
        status = "failed"
    elif vectors_failed:
        status = "partial"
    else:
        status = "success"

    return IndexResponse(
        index_name=body.index_name,
        vectors_indexed=vectors_indexed,
        vectors_failed=vectors_failed,
        status=status,
        index_info=IndexInfo(
            dimension=dimension,
            similarity=similarity,
            total_vectors=total_vectors,
        ),
        errors=errors,
    )
