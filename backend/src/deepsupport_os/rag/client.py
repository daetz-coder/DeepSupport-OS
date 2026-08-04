"""HTTP client wrapper for RAGLab — call, don't copy."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from deepsupport_os.core.config import get_settings

logger = logging.getLogger(__name__)


class RAGLabClient:
    """Thin HTTP facade over a running RAGLab instance."""

    def __init__(self, base_url: str | None = None, timeout: float = 60.0):
        settings = get_settings()
        self.base_url = (base_url or settings.raglab_base_url).rstrip("/")
        self.timeout = timeout

    def health(self) -> dict[str, Any]:
        try:
            with httpx.Client(timeout=5.0) as client:
                r = client.get(f"{self.base_url}/health")
                if r.status_code == 404:
                    r = client.get(f"{self.base_url}/")
                r.raise_for_status()
                return {"ok": True, "data": r.json()}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}

    def search_docs(
        self,
        question: str,
        *,
        top_k: int = 5,
        use_rerank: bool = True,
    ) -> dict[str, Any]:
        """Call RAGLab retrieve/query API. Returns normalized chunks."""
        payload = {
            "question": question,
            "top_k": top_k,
            "use_rerank": use_rerank,
        }
        last_err = "unreachable"
        for path in ("/api/query", "/query", "/api/query/retrieve", "/query/retrieve"):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    r = client.post(f"{self.base_url}{path}", json=payload)
                    if r.status_code == 404:
                        last_err = f"404 {path}"
                        continue
                    r.raise_for_status()
                    data = r.json()
                    return {"ok": True, "source": "raglab", "path": path, "data": data}
            except Exception as exc:  # noqa: BLE001
                logger.debug("RAGLab %s failed: %s", path, exc)
                last_err = str(exc)
        return {"ok": False, "error": last_err}

    def get_document(self, doc_id: str) -> dict[str, Any]:
        last_err = "unreachable"
        for path in (f"/documents/{doc_id}", f"/api/documents/{doc_id}"):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    r = client.get(f"{self.base_url}{path}")
                    if r.status_code == 404:
                        last_err = f"404 {path}"
                        continue
                    r.raise_for_status()
                    return {"ok": True, "source": "raglab", "data": r.json()}
            except Exception as exc:  # noqa: BLE001
                last_err = str(exc)
        return {"ok": False, "error": last_err}
