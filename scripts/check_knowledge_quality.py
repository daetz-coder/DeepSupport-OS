"""Quality gate for Microsoft / local knowledge Markdown corpus.

Checks:
  - min body length
  - required frontmatter: source_url (or source), product
  - soft flags: marketing/copilot-only pages

Usage:
  cd backend
  uv run python ../scripts/check_knowledge_quality.py
  uv run python ../scripts/check_knowledge_quality.py --dir ../data/knowledge/microsoft --json
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIR = ROOT / "data" / "knowledge" / "microsoft"
REPORT = ROOT / "data" / "raw" / "microsoft" / "quality_report.json"

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.S)


def parse_md(path: Path) -> tuple[dict[str, str], str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    meta: dict[str, str] = {}
    body = text
    m = FRONTMATTER_RE.match(text)
    if m:
        for line in m.group(1).splitlines():
            if ":" not in line:
                continue
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip('"').strip("'")
        body = m.group(2)
    return meta, body


def check_one(path: Path, *, min_chars: int) -> dict:
    meta, body = parse_md(path)
    body_stripped = body.strip()
    issues: list[str] = []
    source = meta.get("source_url") or meta.get("source") or ""
    product = meta.get("product") or ""
    if len(body_stripped) < min_chars:
        issues.append(f"short_body:{len(body_stripped)}")
    if not source:
        issues.append("missing_source_url")
    elif not source.startswith("http"):
        issues.append("invalid_source_url")
    if not product:
        issues.append("missing_product")
    low = body_stripped.lower()
    soft: list[str] = []
    if "copilot" in low and not any(k in body_stripped for k in ("无法", "修复", "错误", "故障")):
        soft.append("copilot_howto")
    if any(k in body_stripped for k in ("立即购买", "免费试用", "限时优惠")):
        soft.append("marketing_tone")
    return {
        "path": str(path.relative_to(ROOT)).replace("\\", "/"),
        "title": meta.get("title") or path.stem,
        "product": product or None,
        "source_url": source or None,
        "chars": len(body_stripped),
        "ok": not issues,
        "issues": issues,
        "soft_flags": soft,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    parser.add_argument("--min-chars", type=int, default=200)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = args.dir.resolve()
    files = sorted(p for p in root.rglob("*.md") if p.name.upper() != "README.MD")
    results = [check_one(p, min_chars=args.min_chars) for p in files]
    failed = [r for r in results if not r["ok"]]
    soft = [r for r in results if r["soft_flags"]]
    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "dir": str(root),
        "total": len(results),
        "ok": len(results) - len(failed),
        "failed": len(failed),
        "soft_flagged": len(soft),
        "min_chars": args.min_chars,
        "failures": failed,
        "soft": soft,
        "results": results,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {k: report[k] for k in ("total", "ok", "failed", "soft_flagged", "min_chars")}
    print(json.dumps(summary, ensure_ascii=False))
    print(f"wrote {REPORT}")
    if args.json:
        print(json.dumps(failed[:20], ensure_ascii=False, indent=2))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
