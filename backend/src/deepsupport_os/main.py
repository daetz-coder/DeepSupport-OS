from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from deepsupport_os.api import api_router
from deepsupport_os.core.config import get_settings
from deepsupport_os.db import init_db
from deepsupport_os.db.seed import seed_database


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    seed_database(force=False)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.project_name,
        version="0.1.0",
        description=(
            "Open-source enterprise IT support agent harness powered by Deep Agents."
        ),
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)

    @app.get("/")
    def root():
        return {
            "project": settings.project_name,
            "docs": "/docs",
            "raglab": settings.raglab_base_url,
            "llm_configured": settings.llm_configured,
        }

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/admin/seed")
    def admin_seed(force: bool = False):
        return seed_database(force=force)

    return app


app = create_app()
