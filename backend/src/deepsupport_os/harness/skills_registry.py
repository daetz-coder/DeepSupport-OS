"""Resolve multi-source skill directories for Deep Agents progressive disclosure."""

from __future__ import annotations

import json
import shutil
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from deepsupport_os.core.config import get_settings
from deepsupport_os.core.extensions import ext_bool

_SKIP_DIR_NAMES = frozenset({"imported", "references", "__pycache__"})
_RAW = "https://raw.githubusercontent.com/{repo}/main/{path}/{file}"
_ALLOWED_SKILL_HOSTS = frozenset({"raw.githubusercontent.com"})


def skills_root() -> Path:
    return get_settings().resolve("skills")


def _parse_frontmatter(text: str, fallback_name: str) -> tuple[str, str]:
    name = fallback_name
    description = ""
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].splitlines():
                if line.startswith("name:"):
                    name = line.split(":", 1)[1].strip().strip("\"'")
                elif line.startswith("description:"):
                    description = line.split(":", 1)[1].strip().strip("\"'")
    return name, description


def _iter_skill_dirs(*, include_imported: bool) -> list[Path]:
    root = skills_root()
    found: list[Path] = []
    if root.exists():
        for child in sorted(root.iterdir()):
            if not child.is_dir() or child.name in _SKIP_DIR_NAMES:
                continue
            found.append(child)
    imported = root / "imported"
    if include_imported and imported.exists():
        for child in sorted(imported.iterdir()):
            if child.is_dir() and not child.name.startswith("."):
                found.append(child)
    return found


def list_skill_dirs(*, include_imported: bool | None = None, only_enabled: bool = True) -> list[Path]:
    """Skill package dirs. only_enabled=True requires SKILL.md (not .off)."""
    if include_imported is None:
        include_imported = ext_bool("skills_imported_enabled")
    out: list[Path] = []
    for d in _iter_skill_dirs(include_imported=include_imported):
        if only_enabled:
            if (d / "SKILL.md").exists():
                out.append(d)
        else:
            if (d / "SKILL.md").exists() or (d / "SKILL.md.off").exists():
                out.append(d)
    return out


def skill_source_paths(*, include_imported: bool | None = None) -> list[str]:
    """Virtual skill roots for create_deep_agent(skills=...).

    Deep Agents FilesystemBackend (virtual_mode) only accepts POSIX virtual
    paths like ``/skills/…``. Windows absolute paths make ``read_file`` fail with
    "Windows absolute paths are not supported".
    """
    if include_imported is None:
        include_imported = ext_bool("skills_imported_enabled")
    roots: list[str] = []
    builtin = skills_root()
    if builtin.exists():
        roots.append("/skills/")
    imported = builtin / "imported"
    if include_imported and imported.exists() and any(
        p.is_dir() and (p / "SKILL.md").exists() for p in imported.iterdir()
    ):
        roots.append("/skills/imported/")
    return roots


def load_catalog() -> dict[str, Any]:
    path = skills_root() / "catalog.json"
    if not path.exists():
        return {"entries": []}
    return json.loads(path.read_text(encoding="utf-8"))


def skill_index(*, include_disabled: bool = True) -> list[dict[str, Any]]:
    """L1 index including enable state."""
    items: list[dict[str, Any]] = []
    include_imported = True  # list imported even if layer off, mark layer flag separately
    for d in _iter_skill_dirs(include_imported=include_imported):
        enabled = (d / "SKILL.md").exists()
        off = d / "SKILL.md.off"
        if not enabled and not off.exists():
            continue
        if not include_disabled and not enabled:
            continue
        src = d / "SKILL.md" if enabled else off
        text = src.read_text(encoding="utf-8", errors="ignore")
        name, description = _parse_frontmatter(text, d.name)
        layer = "imported" if d.parent.name == "imported" else "builtin"
        items.append(
            {
                "name": name,
                "dir_name": d.name,
                "description": description,
                "path": str(d.relative_to(skills_root())).replace("\\", "/"),
                "layer": layer,
                "enabled": enabled,
                "has_references": (d / "references").is_dir(),
            }
        )
    return items


def find_skill_dir(name: str) -> Path | None:
    root = skills_root()
    candidates = [
        root / name,
        root / "imported" / name,
    ]
    # also match by frontmatter name
    for d in _iter_skill_dirs(include_imported=True):
        for fname in ("SKILL.md", "SKILL.md.off"):
            f = d / fname
            if not f.exists():
                continue
            n, _ = _parse_frontmatter(f.read_text(encoding="utf-8", errors="ignore"), d.name)
            if n == name or d.name == name:
                return d
    for c in candidates:
        if c.is_dir():
            return c
    return None


def set_skill_enabled(name: str, enabled: bool) -> dict[str, Any]:
    d = find_skill_dir(name)
    if d is None:
        raise FileNotFoundError(f"skill not found: {name}")
    on = d / "SKILL.md"
    off = d / "SKILL.md.off"
    if enabled:
        if off.exists() and not on.exists():
            off.rename(on)
        elif not on.exists():
            raise FileNotFoundError(f"no SKILL.md for {name}")
    else:
        if on.exists():
            if off.exists():
                off.unlink()
            on.rename(off)
        elif not off.exists():
            raise FileNotFoundError(f"no SKILL.md for {name}")
    return next(i for i in skill_index() if i["dir_name"] == d.name or i["name"] == name)


def import_catalog_skill(catalog_id: str, *, accept_license: bool = False) -> dict[str, Any]:
    cat = load_catalog()
    entry = next((e for e in cat.get("entries") or [] if e.get("id") == catalog_id), None)
    if not entry:
        raise ValueError(f"unknown catalog id: {catalog_id}")
    if entry.get("source") == "cli":
        raise ValueError(f"CLI-only skill: {entry.get('install')}")
    license_note = str(entry.get("license") or "")
    if "Proprietary" in license_note and not accept_license:
        raise PermissionError("proprietary skill requires accept_license=true")

    dest = skills_root() / "imported" / str(entry["name"])
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)

    repo = str(entry["repo"]).strip()
    if not repo or "/" not in repo or ".." in repo or repo.startswith("/"):
        raise ValueError(f"invalid catalog repo: {repo!r}")
    base_path = str(entry.get("path") or "").strip().strip("/")
    if ".." in base_path.split("/"):
        raise ValueError(f"invalid catalog path: {base_path!r}")
    url = _RAW.format(repo=repo, path=base_path, file="SKILL.md")
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in _ALLOWED_SKILL_HOSTS:
        raise ValueError(f"refusing skill download from untrusted URL host: {parsed.hostname}")
    with urllib.request.urlopen(url, timeout=30) as resp:  # noqa: S310
        skill_md = resp.read().decode("utf-8", errors="replace")
    (dest / "SKILL.md").write_text(skill_md, encoding="utf-8")
    notice = (
        f"# Imported skill: {entry['name']}\n\n"
        f"- Source: https://github.com/{repo}/tree/main/{base_path}\n"
        f"- License: {license_note}\n"
        f"- Catalog id: {entry['id']}\n"
    )
    (dest / "NOTICE.md").write_text(notice, encoding="utf-8")
    return {
        "ok": True,
        "path": str(dest.relative_to(skills_root())).replace("\\", "/"),
        "skill": next(
            (i for i in skill_index() if i["dir_name"] == dest.name),
            {"name": entry["name"], "enabled": True, "layer": "imported"},
        ),
    }
