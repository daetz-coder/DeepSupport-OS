"""Full-tree GitHub skill import: directory traversal, SSRF guard, normalize."""

from __future__ import annotations

import json

import pytest

import deepsupport_os.harness.skills_registry as sr


def test_normalize_repo_path():
    assert sr._normalize_repo_path("skills/docx", "../shared/foo.py") == "skills/shared/foo.py"
    assert sr._normalize_repo_path("skills/docx/scripts", "../lib.py") == "skills/docx/lib.py"
    assert sr._normalize_repo_path("skills/docx", "scripts/make.py") == "skills/docx/scripts/make.py"
    assert sr._normalize_repo_path("skills/docx", "/abs/path/x.py") == "skills/docx/abs/path/x.py"


def test_http_bytes_rejects_untrusted_host():
    with pytest.raises(ValueError):
        sr._http_bytes("http://evil.example/x")
    with pytest.raises(ValueError):
        sr._http_bytes("https://evil.example/x")


def test_download_skill_tree_fetches_files_dirs_and_symlinks(tmp_path, monkeypatch):
    responses: dict[str, bytes] = {
        "https://api.github.com/repos/acme/skills/contents/skills/docx?ref=main": json.dumps(
            [
                {"name": "SKILL.md", "type": "file", "download_url": "https://raw.githubusercontent.com/x/SKILL.md"},
                {"name": "scripts", "type": "dir"},
                {"name": "shared.py", "type": "symlink", "target": "../common/shared.py"},
            ]
        ).encode(),
        "https://api.github.com/repos/acme/skills/contents/skills/docx/scripts?ref=main": json.dumps(
            [
                {"name": "make.py", "type": "file", "download_url": "https://raw.githubusercontent.com/x/scripts/make.py"},
            ]
        ).encode(),
        "https://raw.githubusercontent.com/x/SKILL.md": b"# SKILL",
        "https://raw.githubusercontent.com/x/scripts/make.py": b"print('hi')",
        "https://raw.githubusercontent.com/acme/skills/main/skills/common/shared.py": b"shared = 1",
    }

    def fake_http(url, **kwargs):
        assert url in responses, f"unexpected url: {url}"
        return responses[url]

    monkeypatch.setattr(sr, "_http_bytes", fake_http)

    dest = tmp_path / "skill"
    count = sr._download_skill_tree("acme/skills", "skills/docx", dest)
    assert count == 3
    assert (dest / "SKILL.md").read_bytes() == b"# SKILL"
    assert (dest / "scripts" / "make.py").read_bytes() == b"print('hi')"
    assert (dest / "shared.py").read_bytes() == b"shared = 1"


def test_import_catalog_skill_downloads_full_tree(tmp_path, monkeypatch):
    def fake_skills_root():
        return tmp_path / "skills"

    def fake_load_catalog():
        return {
            "entries": [
                {
                    "id": "docx-anthropic",
                    "name": "docx",
                    "repo": "anthropics/skills",
                    "path": "skills/docx",
                    "license": "Proprietary",
                    "source": "github",
                }
            ]
        }

    def fake_download_tree(repo, base_path, dest, **kwargs):
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "SKILL.md").write_text("---\nname: docx\n---\n# docx\n", encoding="utf-8")
        (dest / "scripts").mkdir(exist_ok=True)
        (dest / "scripts" / "make.py").write_text("print()", encoding="utf-8")
        return 2

    monkeypatch.setattr(sr, "skills_root", fake_skills_root)
    monkeypatch.setattr(sr, "load_catalog", fake_load_catalog)
    monkeypatch.setattr(sr, "_download_skill_tree", fake_download_tree)

    result = sr.import_catalog_skill("docx-anthropic", accept_license=True)
    assert result["ok"] is True
    assert result["files"] == 2
    dest = tmp_path / "skills" / "imported" / "docx"
    assert (dest / "SKILL.md").exists()
    assert (dest / "NOTICE.md").exists()
    assert (dest / "scripts" / "make.py").exists()
    assert "Files: 2" in (dest / "NOTICE.md").read_text(encoding="utf-8")


def test_import_catalog_skill_requires_license(tmp_path, monkeypatch):
    def fake_skills_root():
        return tmp_path / "skills"

    def fake_load_catalog():
        return {
            "entries": [
                {
                    "id": "docx-anthropic",
                    "name": "docx",
                    "repo": "anthropics/skills",
                    "path": "skills/docx",
                    "license": "Proprietary",
                    "source": "github",
                }
            ]
        }

    monkeypatch.setattr(sr, "skills_root", fake_skills_root)
    monkeypatch.setattr(sr, "load_catalog", fake_load_catalog)

    with pytest.raises(PermissionError):
        sr.import_catalog_skill("docx-anthropic", accept_license=False)
