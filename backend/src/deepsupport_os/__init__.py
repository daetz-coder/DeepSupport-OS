"""DeepSupport OS — enterprise IT support agent harness."""

__version__ = "0.1.0"


def main() -> None:
    import uvicorn

    from deepsupport_os.core.config import get_settings

    settings = get_settings()
    uvicorn.run(
        "deepsupport_os.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )
