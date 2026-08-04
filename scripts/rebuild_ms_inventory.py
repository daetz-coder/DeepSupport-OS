"""Rebuild inventory.json from crawled microsoft markdown files."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MD_DIR = ROOT / "data" / "knowledge" / "microsoft"
OUT = ROOT / "data" / "raw" / "microsoft" / "inventory.json"


def main() -> None:
    items = []
    for path in sorted(MD_DIR.glob("*.md")):
        if path.name.upper() == "README.MD":
            continue
        text = path.read_text(encoding="utf-8")
        meta: dict[str, str] = {}
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                for line in parts[1].splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        meta[k.strip()] = v.strip().strip('"')
        items.append(
            {
                "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                "title": meta.get("title", path.stem),
                "product": meta.get("product", "?"),
                "source_url": meta.get("source_url", ""),
                "chars": len(text),
            }
        )
    summary = {
        "ok": len(items),
        "products": dict(Counter(i["product"] for i in items)),
        "docs": items,
        "note": "Inventory rebuilt from markdown files after crawl retries.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": summary["ok"], "products": summary["products"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
