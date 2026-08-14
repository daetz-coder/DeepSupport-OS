"""HTTP client wrapper for RAGLab — call, don't copy."""

from __future__ import annotations

import logging
from typing import Any

from deepsupport_os.core.config import get_settings
from deepsupport_os.core.http_retry import request_with_retries

logger = logging.getLogger(__name__)


class RAGLabClient:
    """Thin HTTP facade over a running RAGLab instance."""

    def __init__(
        self,
        base_url: str | None = None,
        kb: str | None = None,
        timeout: float = 30.0,
    ):
        settings = get_settings()
        self.base_url = (base_url or settings.raglab_base_url).rstrip("/")
        self.kb = kb or settings.raglab_kb
        self.timeout = timeout

    def health(self) -> dict[str, Any]:
        try:
            for path in ("/api/health", "/api/system/health", "/health", "/"):
                r = request_with_retries(
                    "GET",
                    f"{self.base_url}{path}",
                    timeout=5.0,
                    retries=1,
                )
                if r.status_code == 404:
                    continue
                r.raise_for_status()
                try:
                    data = r.json()
                except Exception:  # noqa: BLE001
                    data = {"raw": r.text[:200]}
                return {"ok": True, "path": path, "data": data}
            return {"ok": False, "error": "no_health_endpoint"}
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
        headers = {"X-RAGLab-Role": "viewer"}
        last_err = "unreachable"
        attempts = [
            {
                "question": question,
                "top_k": top_k,
                "kb": self.kb,
                "use_rerank": use_rerank,
                "use_query_understanding": False,
            },
            {
                "question": question,
                "top_k": top_k,
                "kb": self.kb,
                "use_rerank": False,
                "use_query_understanding": False,
            },
        ]
        seen: set[str] = set()
        for payload in attempts:
            key = f"rr={payload['use_rerank']}"
            if key in seen:
                continue
            seen.add(key)
            try:
                r = request_with_retries(
                    "POST",
                    f"{self.base_url}/api/query",
                    timeout=self.timeout,
                    retries=2,
                    json=payload,
                    headers=headers,
                )
                if r.status_code == 404:
                    last_err = "404 /api/query"
                    continue
                r.raise_for_status()
                data = r.json()
                return {
                    "ok": True,
                    "source": "raglab",
                    "path": "/api/query",
                    "payload": payload,
                    "data": data,
                }
            except Exception as exc:  # noqa: BLE001
                logger.debug("RAGLab query failed (%s): %s", key, exc)
                last_err = str(exc)
        return {"ok": False, "error": last_err}

    def get_document(self, doc_id: str) -> dict[str, Any]:
        last_err = "unreachable"
        for path in (f"/documents/{doc_id}", f"/api/documents/{doc_id}"):
            try:
                r = request_with_retries(
                    "GET",
                    f"{self.base_url}{path}",
                    timeout=self.timeout,
                    retries=1,
                )
                if r.status_code == 404:
                    last_err = f"404 {path}"
                    continue
                r.raise_for_status()
                return {"ok": True, "source": "raglab", "data": r.json()}
            except Exception as exc:  # noqa: BLE001
                last_err = str(exc)
        return {"ok": False, "error": last_err}

    def list_documents(
        self,
        *,
        kb: str | None = None,
        status: str = "active",
        limit: int = 200,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List documents in a KB (GET /api/documents?kb=...)."""
        headers = {"X-RAGLab-Role": "viewer"}
        params = {
            "kb": kb or self.kb,
            "status": status,
            "limit": limit,
            "offset": offset,
        }
        last_err = "unreachable"
        for path in ("/api/documents", "/documents"):
            try:
                r = request_with_retries(
                    "GET",
                    f"{self.base_url}{path}",
                    timeout=self.timeout,
                    retries=1,
                    params=params,
                    headers=headers,
                )
                if r.status_code == 404:
                    last_err = f"404 {path}"
                    continue
                r.raise_for_status()
                return {"ok": True, "source": "raglab", "path": path, "data": r.json()}
            except Exception as exc:  # noqa: BLE001
                last_err = str(exc)
        return {"ok": False, "error": last_err}
