"""FastAPI application entry point."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from app.api.v1.router import api_router
from app.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.db.database import dispose_engines
from app.services.storage_service import get_storage_service

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Ensure both material and certificate buckets exist before accepting uploads.
    await run_in_threadpool(get_storage_service().ensure_buckets)
    yield
    await dispose_engines()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
)
register_exception_handlers(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials="*" not in settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
