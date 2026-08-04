"""Batch-ingest DeepSupport knowledge Markdown into a running RAGLab instance.

Does not copy RAGLab code — only HTTP multipart upload to /api/ingest.

Prereq:
  RAGLab API on RAGLAB_BASE_URL (default http://127.0.0.1:8001)
  Role header with write permission (editor/admin)

Usage:
  cd backend
  uv run python ../scripts/ingest_to_raglab.py
  uv run python ../scripts/ingest_to_raglab.py --dir ../data/knowledge/microsoft --limit 20
"""

from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIRS = [
    ROOT / "data" / "knowledge" / "microsoft",
    ROOT / "data" / "knowledge",
]
REPORT = ROOT / "data" / "raw" / "microsoft" / "ingest_report.json"


def parse_frontmatter(text: str) -> dict[str, str]:
    meta: dict[str, str] = {}
    if not text.startswith("---"):
        return meta
    parts = text.split("---", 2)
    if len(parts) < 3:
        return meta
    for line in parts[1].splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        meta[k.strip()] = v.strip().strip('"')
    return meta


def collect_mds(dirs: list[Path], *, min_chars: int) -> list[Path]:
    files: list[Path] = []
    seen: set[Path] = set()
    for d in dirs:
        if not d.exists():
            continue
        for p in sorted(d.rglob("*.md")):
            if p.name.upper() == "README.MD":
                continue
            rp = p.resolve()
            if rp in seen:
                continue
            text = p.read_text(encoding="utf-8", errors="ignore")
            if len(text) < min_chars:
                continue
            # Prefer troubleshooting / support pages
            low = text.lower()
            if "copilot" in low and "修复" not in text and "无法" not in text and "fix" not in low:
                # soft skip pure copilot howto unless short corpus
                pass
            seen.add(rp)
            files.append(p)
    return files


def rel_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(resolved).replace("\\", "/")


def ingest_one(
    client: httpx.Client,
    base_url: str,
    path: Path,
    *,
    role: str,
) -> dict:
    path = path.resolve()
    text = path.read_text(encoding="utf-8", errors="ignore")
    meta = parse_frontmatter(text)
    title = meta.get("title") or path.stem
    doc_type = meta.get("category") or meta.get("content_type") or "support"
    product = meta.get("product") or "Microsoft365"
    with path.open("rb") as f:
        files = {"file": (path.name, f, "text/markdown")}
        data = {
            "kb": "huawei",
            "title": title[:200],
            "doc_type": str(doc_type)[:64],
            "dept": str(product)[:64],
            "permission": "public",
        }
        headers = {"X-RAGLab-Role": role}
        r = client.post(
            f"{base_url.rstrip('/')}/api/ingest",
            files=files,
            data=data,
            headers=headers,
            timeout=180.0,
        )
    ok = r.status_code < 300
    body = r.text[:500]
    return {
        "path": rel_path(path),
        "title": title,
        "ok": ok,
        "status": r.status_code,
        "body": body,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raglab-url", default="http://127.0.0.1:8001")
    parser.add_argument("--dir", action="append", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--min-chars", type=int, default=300)
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--role", default="editor")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    dirs = [d.resolve() for d in (args.dir or DEFAULT_DIRS)]
    files = collect_mds(dirs, min_chars=args.min_chars)
    if args.limit:
        files = files[: args.limit]

    print(f"candidates={len(files)} raglab={args.raglab_url} dry_run={args.dry_run}")

    # Health probe
    try:
        h = httpx.get(f"{args.raglab_url.rstrip('/')}/api/health", timeout=10.0)
        print(f"raglab health status={h.status_code} body={h.text[:160]}")
    except Exception as exc:  # noqa: BLE001
        print(f"RAGLab unreachable: {exc}")
        if not args.dry_run:
            raise SystemExit(2) from exc

    results = []
    if args.dry_run:
        for p in files:
            meta = parse_frontmatter(p.read_text(encoding="utf-8", errors="ignore"))
            results.append(
                {
                    "path": rel_path(p),
                    "title": meta.get("title") or p.stem,
                    "product": meta.get("product"),
                    "ok": True,
                    "dry_run": True,
                }
            )
    else:
        with httpx.Client() as client:
            for i, p in enumerate(files, start=1):
                try:
                    item = ingest_one(client, args.raglab_url, p, role=args.role)
                except Exception as exc:  # noqa: BLE001
                    item = {
                        "path": rel_path(p),
                        "ok": False,
                        "error": str(exc),
                    }
                results.append(item)
                mark = "OK" if item.get("ok") else "FAIL"
                print(f"[{i}/{len(files)}] {mark} {item.get('title') or item.get('path')}")
                time.sleep(args.delay)

    ok = sum(1 for r in results if r.get("ok"))
    report = {
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "raglab_url": args.raglab_url,
        "total": len(results),
        "ok": ok,
        "failed": len(results) - ok,
        "dry_run": args.dry_run,
        "results": results,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("total", "ok", "failed", "dry_run")}, ensure_ascii=False))
    print(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
