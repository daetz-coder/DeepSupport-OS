from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from deepsupport_os.api import api_router
from deepsupport_os.api.auth import require_admin
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
        """Liveness only — safe for Docker healthcheck and fast UI poll."""
        live = get_settings()
        return {
            "status": "ok",
            "llm_configured": live.llm_configured,
            "admin_auth_required": bool((live.admin_token or "").strip()),
        }

    @app.get("/api/health/deps")
    def health_deps():
        """External dependency probe (RAGLab + Daytona). Not used by compose healthcheck."""
        from deepsupport_os.harness.daytona_backend import probe_sandbox_status
        from deepsupport_os.rag.client import RAGLabClient

        live = get_settings()
        rag = RAGLabClient().health()
        sandbox = probe_sandbox_status()
        return {
            "raglab": {
                "ok": bool(rag.get("ok")),
                "base_url": live.raglab_base_url,
                "path": rag.get("path"),
                "error": rag.get("error"),
            },
            "sandbox": sandbox,
        }

    @app.post("/admin/seed", dependencies=[Depends(require_admin)])
    def admin_seed(force: bool = False):
        return seed_database(force=force)

    return app


app = create_app()
