import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from deepsupport_os.api import api_router
from deepsupport_os.api.auth import require_admin
from deepsupport_os.api.errors import register_exception_handlers
from deepsupport_os.core.config import get_settings
from deepsupport_os.core.config_validation import validate_configuration
from deepsupport_os.db import init_db
from deepsupport_os.db.seed import seed_database
from deepsupport_os.middleware.metrics import MetricsMiddleware
from deepsupport_os.middleware.rate_limit import RateLimitMiddleware

logger = logging.getLogger(__name__)

# Graceful shutdown handling
shutdown_event = asyncio.Event()


def handle_shutdown(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"收到信号 {signum}，开始优雅关闭...")
    shutdown_event.set()


# Register signal handlers
import signal
signal.signal(signal.SIGTERM, handle_shutdown)
signal.signal(signal.SIGINT, handle_shutdown)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Validate configuration on startup
    try:
        config_result = validate_configuration()
        if config_result["warnings"]:
            for warning in config_result["warnings"]:
                logger.warning(f"配置警告: {warning}")
    except Exception as e:
        logger.error(f"配置验证失败: {e}")
    
    init_db()
    seed_database(force=False)
    
    logger.info("DeepSupport OS 启动完成")
    
    yield
    
    # Graceful shutdown
    logger.info("DeepSupport OS 正在关闭...")
    await shutdown_event.wait()
    logger.info("DeepSupport OS 已关闭")


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
    
    # Register exception handlers
    register_exception_handlers(app)
    
    # Add rate limiting middleware
    if settings.rate_limit_per_minute > 0:
        app.add_middleware(
            RateLimitMiddleware,
            requests_per_minute=settings.rate_limit_per_minute
        )
    
    # Add metrics middleware
    app.add_middleware(MetricsMiddleware)
    
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
            "demo_auth_required": bool((live.demo_access_token or "").strip()),
        }

    @app.get("/api/health/deps")
    def health_deps():
        """External dependency probe (RAGLab + Daytona). Not used by compose healthcheck."""
        from deepsupport_os.harness.daytona_backend import probe_sandbox_status
        from deepsupport_os.rag.client import RAGLabClient

        live = get_settings()
        rag = RAGLabClient().health()
        sandbox = probe_sandbox_status()
        rag_ok = bool(rag.get("ok"))
        hint = (live.raglab_unavailable_hint or "").strip()
        return {
            "raglab": {
                "ok": rag_ok,
                "base_url": live.raglab_base_url,
                "kb": live.raglab_kb,
                "path": rag.get("path"),
                "error": rag.get("error"),
                "hint": None if rag_ok else (hint or None),
            },
            "sandbox": sandbox,
        }

    @app.post("/admin/seed", dependencies=[Depends(require_admin)])
    def admin_seed(force: bool = False):
        return seed_database(force=force)

    return app


app = create_app()
