"""DeepSupport OS — enterprise IT support agent harness."""

__version__ = "0.1.0"


def main() -> None:
    import uvicorn

    uvicorn.run(
        "deepsupport_os.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
