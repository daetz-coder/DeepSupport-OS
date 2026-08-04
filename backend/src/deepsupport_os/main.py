from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from deepsupport_os.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.project_name,
        version="0.1.0",
        description=(
            "Open-source enterprise IT support agent harness powered by Deep Agents."
        ),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

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

    return app


app = create_app()
