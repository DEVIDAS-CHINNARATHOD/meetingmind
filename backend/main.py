"""
main.py — Phase 4 (complete)
FastAPI app: all phases registered.
"""
from __future__ import annotations
from contextlib import asynccontextmanager
from pathlib import Path
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from api.middleware.logging import RequestLoggingMiddleware
from api.middleware.rate_limit import RateLimitMiddleware
from api.routes import auth, meetings, ai, reports
from api.routes import analytics, team, action_items, speakers, search, ai_stream
from api.routes import identities
from api.routes import integrations, websocket
from config.settings import settings
from db.database import check_db_connection, create_tables

log = structlog.get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("starting_up", env=settings.app_env, version=settings.app_version)
    for d in [settings.local_storage_path, settings.chroma_db_path]:
        Path(d).mkdir(parents=True, exist_ok=True)
    ok = await check_db_connection()
    if ok and settings.app_env != "production":
        await create_tables()
    log.info("startup_complete", db_ok=ok, phase=4)
    yield
    log.info("shutting_down")

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name, version=settings.app_version,
        description="MeetingMind AI — Phase 4 complete.",
        docs_url="/api/docs" if not settings.is_production else None,
        redoc_url="/api/redoc" if not settings.is_production else None,
        openapi_url="/api/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )
    app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins,
                       allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RateLimitMiddleware)

    for r in [auth.router, meetings.router, ai.router, reports.router]:
        app.include_router(r, prefix="/api")
    for r in [analytics.router, team.router, action_items.router,
              speakers.router, search.router, ai_stream.router]:
        app.include_router(r, prefix="/api")
    app.include_router(identities.router, prefix="/api")
    app.include_router(integrations.router, prefix="/api")
    app.include_router(websocket.router)

    if settings.storage_backend == "local":
        p = Path(settings.local_storage_path)
        p.mkdir(parents=True, exist_ok=True)
        app.mount("/static", StaticFiles(directory=str(p)), name="static")

    @app.get("/api/health", tags=["health"])
    async def health():
        import redis as rl
        db_ok = await check_db_connection()
        try:
            rl.from_url(settings.redis_url, socket_timeout=2).ping(); redis_ok=True
        except Exception:
            redis_ok=False
        worker_count = 0
        try:
            from workers.celery_app import celery_app as ca
            stats = ca.control.inspect(timeout=2).stats() or {}
            worker_count = len(stats)
        except Exception: pass
        return {"status":"ok" if (db_ok and redis_ok) else "degraded",
                "version":settings.app_version,"env":settings.app_env,
                "db":db_ok,"redis":redis_ok,"storage":settings.storage_backend,
                "celery_workers":worker_count,
                "features":{"diarization":settings.diarization_enabled,
                             "face_recognition":True,"zoom_bot":bool(settings.zoom_client_id),
                             "meet_bot":True,"realtime_ws":True}}
    return app

app = create_app()
