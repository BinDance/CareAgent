from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from eldercare_api.config import get_settings
from eldercare_api.routers import elder, family, internal
from eldercare_api.scheduler import AppScheduler


def create_app(start_scheduler: bool | None = None) -> FastAPI:
    settings = get_settings()
    scheduler = AppScheduler()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings.resolved_upload_dir.mkdir(parents=True, exist_ok=True)
        should_start = start_scheduler if start_scheduler is not None else settings.app_env != 'test'
        if should_start:
            scheduler.start()
        app.state.scheduler = scheduler
        yield
        scheduler.shutdown()

    app = FastAPI(title='Elder Care Agent API', version='0.1.0', lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=['*'],
        allow_credentials=True,
        allow_methods=['*'],
        allow_headers=['*'],
    )
    app.include_router(elder.router)
    app.include_router(family.router)
    app.include_router(internal.router)

    @app.get('/healthz')
    def healthz() -> dict[str, str]:
        return {'status': 'ok'}

    return app


app = create_app()
