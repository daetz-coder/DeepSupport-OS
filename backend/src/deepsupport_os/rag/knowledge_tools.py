"""Knowledge tools: RAGLab HTTP first, local sample docs + cases as fallback."""

from __future__ import annotations

import re
from pathlib import Path

from langchain_core.tools import tool

from deepsupport_os.core.config import get_settings
from deepsupport_os.db.repositories import CaseRepo, write_audit
from deepsupport_os.rag.client import RAGLabClient

_case = CaseRepo()


def _local_knowledge_dir() -> Path:
    return get_settings().resolve("data/knowledge")


def _search_local_markdown(query: str, limit: int = 5) -> list[dict]:
    root = _local_knowledge_dir()
    if not root.exists():
        return []
    tokens = [t.lower() for t in re.split(r"\s+|，|。|、", query) if len(t) >= 2]
    scored: list[tuple[int, dict]] = []
    for path in root.rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        lower = text.lower()
        score = sum(1 for t in tokens if t in lower)
        if score <= 0:
            continue
        title = path.stem
        for line in text.splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                break
        scored.append(
            (
                score,
                {
                    "document_id": path.stem,
                    "title": title,
                    "source": str(path.relative_to(root)),
                    "snippet": text[:500],
                    "score": score,
                    "source_type": "local_sample",
                },
            )
        )
    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[:limit]]


@tool
def search_docs(query: str, top_k: int = 5) -> dict:
    """检索 Microsoft 365 / 企业支持文档。优先调用 RAGLab；不可用时回退本地示例知识。"""
    client = RAGLabClient()
    # Default without rerank for latency; client still retries if needed.
    remote = client.search_docs(query, top_k=top_k, use_rerank=False)
    if remote.get("ok"):
        result = {"ok": True, "backend": "raglab", "results": remote.get("data")}
    else:
        local = _search_local_markdown(query, limit=top_k)
        result = {
            "ok": True,
            "backend": "local_fallback",
            "raglab_error": remote.get("error"),
            "results": local,
        }
    write_audit("adhoc", "search_docs", {"query": query, "top_k": top_k}, result)
    return result


@tool
def get_document(document_id: str) -> dict:
    """按文档 ID 获取完整文档内容。"""
    client = RAGLabClient()
    remote = client.get_document(document_id)
    if remote.get("ok"):
        result = {"ok": True, "backend": "raglab", "document": remote.get("data")}
    else:
        root = _local_knowledge_dir()
        path = root / f"{document_id}.md"
        matches = list(root.rglob(f"{document_id}.md")) if not path.exists() else [path]
        if matches:
            p = matches[0]
            result = {
                "ok": True,
                "backend": "local_fallback",
                "document": {
                    "document_id": document_id,
                    "path": str(p),
                    "content": p.read_text(encoding="utf-8"),
                },
            }
        else:
            result = {"ok": False, "error": "not_found", "raglab_error": remote.get("error")}
    write_audit("adhoc", "get_document", {"document_id": document_id}, result)
    return result


@tool
def search_cases(query: str, limit: int = 5) -> list:
    """检索历史故障案例（Mock Case 库）。"""
    result = _case.search_similar_cases(query, limit=limit)
    write_audit("adhoc", "search_cases", {"query": query, "limit": limit}, result)
    return result


KNOWLEDGE_TOOLS = [search_docs, get_document, search_cases]
