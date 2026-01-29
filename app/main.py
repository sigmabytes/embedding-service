"""FastAPI app entry: config, logging, health, and graceful shutdown."""

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config.logging import configure_logging, get_logger
from app.config.settings import get_settings
from app.controllers.routes.chunk import router as chunk_router
from app.controllers.routes.embed import router as embed_router
from app.controllers.routes.index import router as index_router
from app.resources.mongo.client import close_mongo_client, get_database
from app.resources.mongo.indexes import create_indexes
from app.resources.mongo.session import ping_mongo
from app.resources.opensearch.client import close_opensearch_client
from app.resources.opensearch.health import ping_opensearch

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: config, logging, and indexes. Shutdown: close MongoDB and OpenSearch clients."""
    settings = get_settings()
    configure_logging()
    logger.info("Application starting", extra={"app_name": settings.app_name, "environment": settings.environment})
    # Create MongoDB indexes on startup
    try:
        db = get_database()
        await create_indexes(db)
    except Exception as e:
        logger.error("Failed to create MongoDB indexes on startup", extra={"error": str(e)})
        # Don't fail startup, but log the error
    yield
    logger.info("Application shutting down")
    close_mongo_client()
    close_opensearch_client()
    logger.info("Shutdown complete")


app = FastAPI(
    title="Embedding Service",
    description="Prepare and publish knowledge for a RAG system",
    version="1.0.0",
    lifespan=lifespan,
)
app.include_router(chunk_router)
app.include_router(embed_router)
app.include_router(index_router)


def _health_response(ok: bool, mongo: dict[str, Any], opensearch: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "ok" if ok else "degraded",
        "mongo": {"ok": mongo.get("ok", False), "error": mongo.get("error")},
        "opensearch": {"ok": opensearch.get("ok", False), "error": opensearch.get("error")},
    }


@app.get("/health")
async def health() -> dict[str, Any]:
    """Liveness: service is up. Does not check dependencies."""
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> dict[str, Any]:
    """Readiness: service can serve traffic. Verifies MongoDB and OpenSearch connectivity."""
    mongo = await ping_mongo()
    opensearch = await ping_opensearch()
    ok = mongo.get("ok", False) and opensearch.get("ok", False)
    body = _health_response(ok, mongo, opensearch)
    status_code = 200 if ok else 503
    return JSONResponse(content=body, status_code=status_code)


@app.exception_handler(Exception)
async def global_exception_handler(_request: Request, exc: Exception):
    """Centralized error handling: connection failures and timeouts get clear, non-leaking messages."""
    exc_name = type(exc).__name__
    # Do not leak stack traces or internal details to the client
    if "Connection" in exc_name or "Timeout" in exc_name or "connection" in str(type(exc).__module__).lower():
        logger.warning("Connection or timeout error", extra={"error": exc_name})
        return JSONResponse(
            content={"detail": "A dependency is temporarily unavailable. Please retry later."},
            status_code=503,
        )
    logger.exception("Unhandled error")
    return JSONResponse(
        content={"detail": "An internal error occurred."},
        status_code=500,
    )
