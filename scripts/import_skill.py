"""Import a catalogued public skill into skills/imported/ for progressive disclosure."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "skills" / "catalog.json"
IMPORTED = ROOT / "skills" / "imported"
RAW = "https://raw.githubusercontent.com/{repo}/main/{path}/{file}"


def load_catalog() -> dict:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def download(url: str) -> str | None:
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:  # noqa: S310
            return resp.read().decode("utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        print(f"  skip {url}: {exc}", file=sys.stderr)
        return None


def import_entry(entry: dict, *, accept_license: bool) -> Path:
    if entry.get("source") == "cli":
        raise SystemExit(
            f"{entry['id']} is CLI-only. Run: {entry.get('install')}\n"
            "Then copy the installed skill folder into skills/imported/."
        )
    license_note = str(entry.get("license") or "")
    if "Proprietary" in license_note and not accept_license:
        raise SystemExit(
            f"{entry['id']} is proprietary. Re-run with --accept-license after review."
        )

    dest = IMPORTED / str(entry["name"])
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)

    repo = entry["repo"]
    base_path = entry["path"].rstrip("/")
    skill_md = download(RAW.format(repo=repo, path=base_path, file="SKILL.md"))
    if not skill_md:
        raise SystemExit(f"Failed to download SKILL.md for {entry['id']}")
    (dest / "SKILL.md").write_text(skill_md, encoding="utf-8")

    notice = (
        f"# Imported skill: {entry['name']}\n\n"
        f"- Source: https://github.com/{repo}/tree/main/{base_path}\n"
        f"- License: {license_note}\n"
        f"- Catalog id: {entry['id']}\n"
        f"- Imported for DeepSupport OS progressive disclosure demo.\n"
        f"- Review upstream LICENSE before production use.\n"
    )
    (dest / "NOTICE.md").write_text(notice, encoding="utf-8")
    print(f"Imported → {dest}")
    return dest


def list_entries() -> None:
    cat = load_catalog()
    for e in cat.get("entries") or []:
        print(f"{e['id']:20} {e.get('install')}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill_id", nargs="?", help="Catalog entry id")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--accept-license", action="store_true")
    args = parser.parse_args()

    if args.list or not args.skill_id:
        list_entries()
        return

    cat = load_catalog()
    entry = next((e for e in cat["entries"] if e["id"] == args.skill_id), None)
    if not entry:
        raise SystemExit(f"Unknown skill id: {args.skill_id}. Use --list.")
    import_entry(entry, accept_license=args.accept_license)


if __name__ == "__main__":
    main()
