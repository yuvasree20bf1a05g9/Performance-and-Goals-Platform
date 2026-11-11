"""Application factory. Run with:  uvicorn backend.app.main:app --reload"""
from __future__ import annotations

import logging
import threading
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from .api.routes import router
from .config import Settings, get_settings
from .db import Base, Database
from .errors import DomainError, domain_error_handler

log = logging.getLogger("pgp")


def create_app(settings: Optional[Settings] = None, database: Optional[Database] = None) -> FastAPI:
    settings = settings or get_settings()
    @asynccontextmanager
    async def lifespan(app_: FastAPI):
        # Build the data-quality findings in the background so the first page view is fast
        def _warm():
            from .models import DatasetInfo
            from .services.analytics import quality_cache
            try:
                with app_.state.db.SessionLocal() as s:
                    if s.get(DatasetInfo, "as_of") is not None:
                        quality_cache.refresh(s)
            except Exception:  # pragma: no cover - warming is best-effort
                log.exception("cache warm-up failed")
        threading.Thread(target=_warm, daemon=True).start()
        yield

    app = FastAPI(lifespan=lifespan, title="Performance & Goals Platform API", version="1.0.0",
                  description="Goals, key results, check-ins, competency feedback, reviews and development plans "
                              "with evidence-based progress tracking. Write endpoints require an `X-Actor-Id` header.")
    app.state.db = database or Database(settings.database_url)
    Base.metadata.create_all(app.state.db.engine)      # idempotent; the loader recreates tables with data

    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"])
    app.add_exception_handler(DomainError, domain_error_handler)

    @app.middleware("http")
    async def timing(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Response-Time-ms"] = f"{(time.perf_counter() - start) * 1000:.1f}"
        return response

    @app.exception_handler(Exception)
    async def unhandled(_: Request, exc: Exception):
        log.exception("unhandled error")
        return JSONResponse(status_code=500, content={"error": {"code": "internal_error", "message": str(exc)}})

    app.include_router(router)


    dist = settings.frontend_dist
    if dist.exists():
        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            # Serve built assets; fall back to index.html for client-side routes
            candidate = (dist / path).resolve()
            if path and candidate.is_file() and dist.resolve() in candidate.parents:
                return FileResponse(candidate)
            return FileResponse(dist / "index.html")
    return app


_app: Optional[FastAPI] = None


def __getattr__(name: str):
    """`uvicorn backend.app.main:app` still works, but the app (and its database connection) is
    only created when first requested - importing this module has no side effects."""
    global _app
    if name == "app":
        if _app is None:
            _app = create_app()
        return _app
    raise AttributeError(name)
