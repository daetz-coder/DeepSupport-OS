"""HTTP client wrapper for RAGLab — call, don't copy."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from deepsupport_os.core.config import get_settings

logger = logging.getLogger(__name__)


class RAGLabClient:
    """Thin HTTP facade over a running RAGLab instance."""

    def __init__(self, base_url: str | None = None, timeout: float = 120.0):
        settings = get_settings()
        self.base_url = (base_url or settings.raglab_base_url).rstrip("/")
        self.timeout = timeout

    def health(self) -> dict[str, Any]:
        try:
            with httpx.Client(timeout=5.0) as client:
                for path in ("/api/health", "/api/system/health", "/health", "/"):
                    r = client.get(f"{self.base_url}{path}")
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
        # Prefer fast retrieval: skip query-understanding LLM when possible.
        # Only hit /api/query (canonical); avoid overwriting useful errors with /query 404.
        attempts = [
            {"question": question, "top_k": top_k, "use_rerank": use_rerank, "use_query_understanding": False},
            {"question": question, "top_k": top_k, "use_rerank": False, "use_query_understanding": False},
        ]
        seen: set[str] = set()
        for payload in attempts:
            key = f"rr={payload['use_rerank']}"
            if key in seen:
                continue
            seen.add(key)
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    r = client.post(
                        f"{self.base_url}/api/query",
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
