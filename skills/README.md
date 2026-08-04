# Agent Skills

DeepSupport OS uses [Agent Skills](https://agentskills.io) with **progressive disclosure**:

| Level | What | When loaded |
|-------|------|-------------|
| L1 | `name` + `description` in SKILL.md frontmatter | Agent start (SkillsMiddleware) |
| L2 | SKILL.md body | Skill matches the user task |
| L3 | `references/*` (and optional scripts) | Agent `read_file` only when needed |

## Layout

```text
skills/
├── catalog.json              # Public / third-party skill index
├── outlook-troubleshooting/  # Builtin SOP
├── teams-troubleshooting/    # Builtin + references/ (L3)
├── onedrive-sync/
├── office-application/
├── ...
└── imported/                 # Vendored public skills (gitignored content OK)
```

## Continuous onboarding

1. Browse [skills.sh](https://skills.sh/) or entries in `catalog.json`
2. Import into `skills/imported/`:

```bash
# list catalog
uv run --directory backend python ../scripts/import_skill.py --list

# import (proprietary skills need --accept-license after review)
uv run --directory backend python ../scripts/import_skill.py pdf-anthropic --accept-license
```

3. Restart API — `skill_source_paths()` auto-includes `skills/` + `skills/imported/`
4. Inspect: `GET http://127.0.0.1:8000/api/meta/skills`

## Writing a builtin skill

1. Create `skills/<name>/SKILL.md` with YAML `name` + `description` (description = trigger)
2. Keep body short; put long SOP under `references/sop.md`
3. Align tool names with `backend/src/deepsupport_os/mcp/tools.py`
