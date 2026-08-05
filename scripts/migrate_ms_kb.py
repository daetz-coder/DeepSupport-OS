"""Clean MS docs wrongly stored under RAGLab kb=huawei, then re-ingest as deepsupport.

Reads doc_ids from data/raw/microsoft/ingest_report.json (prior ingest bodies).

Usage:
  cd backend
  # Dry-run: show what would be deleted / re-ingested
  uv run python ../scripts/migrate_ms_kb.py --dry-run

  # Delete from huawei (admin) + re-upload into deepsupport
  uv run python ../scripts/migrate_ms_kb.py --delete --reingest

  # Only re-ingest (upsert updates kb metadata + vectors; often enough)
  uv run python ../scripts/migrate_ms_kb.py --reingest
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = ROOT / "data" / "raw" / "microsoft" / "ingest_report.json"


def extract_doc_id(item: dict) -> str | None:
    body = item.get("body")
    if isinstance(body, dict):
        return body.get("doc_id")
    if isinstance(body, str) and body.strip().startswith("{"):
        try:
            return json.loads(body).get("doc_id")
        except json.JSONDecodeError:
            return None
    return None


def load_entries(report_path: Path) -> list[dict]:
    data = json.loads(report_path.read_text(encoding="utf-8"))
    results = data.get("results") or []
    out: list[dict] = []
    for item in results:
        if not item.get("ok"):
            continue
        path = item.get("path")
        doc_id = extract_doc_id(item)
        if path or doc_id:
            out.append({"path": path, "doc_id": doc_id, "title": item.get("title")})
    return out


def delete_one(
    client: httpx.Client,
    base_url: str,
    doc_id: str,
    *,
    role: str,
    dry_run: bool,
) -> dict:
    if dry_run:
        return {"doc_id": doc_id, "ok": True, "dry_run": True, "action": "delete"}
    r = client.delete(
        f"{base_url.rstrip('/')}/api/documents/{doc_id}",
        headers={"X-RAGLab-Role": role},
        timeout=60.0,
    )
    return {
        "doc_id": doc_id,
        "ok": r.status_code < 300,
        "status": r.status_code,
        "body": r.text[:300],
        "action": "delete",
    }


def reingest_one(
    client: httpx.Client,
    base_url: str,
    rel: str,
    *,
    kb: str,
    role: str,
    dry_run: bool,
) -> dict:
    path = (ROOT / rel).resolve()
    if not path.is_file():
        return {"path": rel, "ok": False, "error": "missing_file", "action": "reingest"}
    if dry_run:
        return {"path": rel, "ok": True, "dry_run": True, "kb": kb, "action": "reingest"}
    with path.open("rb") as f:
        r = client.post(
            f"{base_url.rstrip('/')}/api/ingest",
            files={"file": (path.name, f, "text/markdown")},
            data={"kb": kb, "title": path.stem[:200], "doc_type": "support", "permission": "public"},
            headers={"X-RAGLab-Role": role},
            timeout=180.0,
        )
    return {
        "path": rel,
        "ok": r.status_code < 300,
        "status": r.status_code,
        "kb": kb,
        "body": r.text[:300],
        "action": "reingest",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT,
        help="Prior ingest_report.json with doc_ids",
    )
    parser.add_argument(
        "--raglab-url",
        default=os.environ.get("RAGLAB_BASE_URL", "http://127.0.0.1:8001"),
    )
    parser.add_argument("--kb", default=os.environ.get("RAGLAB_KB", "deepsupport"))
    parser.add_argument("--delete", action="store_true", help="Soft-delete docs (admin role)")
    parser.add_argument("--reingest", action="store_true", help="Re-upload into --kb")
    parser.add_argument("--role-delete", default="admin")
    parser.add_argument("--role-ingest", default="editor")
    parser.add_argument("--delay", type=float, default=0.3)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.delete and not args.reingest:
        raise SystemExit("Specify --delete and/or --reingest (or --dry-run with both)")

    if not args.report.exists():
        raise SystemExit(f"report not found: {args.report}")

    entries = load_entries(args.report)
    print(
        f"entries={len(entries)} url={args.raglab_url} kb={args.kb} "
        f"delete={args.delete} reingest={args.reingest} dry_run={args.dry_run}"
    )

    results: list[dict] = []
    with httpx.Client() as client:
        if args.delete:
            for i, e in enumerate(entries, start=1):
                doc_id = e.get("doc_id")
                if not doc_id:
                    results.append({"ok": False, "error": "no_doc_id", "path": e.get("path")})
                    continue
                item = delete_one(
                    client,
                    args.raglab_url,
                    doc_id,
                    role=args.role_delete,
                    dry_run=args.dry_run,
                )
                results.append(item)
                mark = "OK" if item.get("ok") else "FAIL"
                print(f"[delete {i}/{len(entries)}] {mark} {doc_id}")
                time.sleep(args.delay)

        if args.reingest:
            for i, e in enumerate(entries, start=1):
                rel = e.get("path")
                if not rel:
                    results.append({"ok": False, "error": "no_path", "doc_id": e.get("doc_id")})
                    continue
                item = reingest_one(
                    client,
                    args.raglab_url,
                    rel,
                    kb=args.kb,
                    role=args.role_ingest,
                    dry_run=args.dry_run,
                )
                results.append(item)
                mark = "OK" if item.get("ok") else "FAIL"
                print(f"[reingest {i}/{len(entries)}] {mark} {rel}")
                time.sleep(args.delay)

    ok = sum(1 for r in results if r.get("ok"))
    print(json.dumps({"actions": len(results), "ok": ok, "failed": len(results) - ok}, ensure_ascii=False))


if __name__ == "__main__":
    main()
