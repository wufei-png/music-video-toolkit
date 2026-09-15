# Contributing

Read [START-HERE](docs/implementation/START-HERE.md) for development and [the production Skill](skills/make-music-video/SKILL.md) for making videos. Keep those entry points separate.

## Local checks

```bash
uv sync --locked --group dev
uv run --locked pytest
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked python scripts/export_schemas.py --check
pnpm --dir renderer install --frozen-lockfile
pnpm --dir renderer check
git diff --check
```

Regenerate schema snapshots with `uv run --locked python scripts/export_schemas.py` after model changes. Semantic Python validation goes beyond JSON Schema; maintain both. Version breaking contract changes and explain how saved production artifacts migrate.

Use synthetic reproducible audio/media in public tests. Verify real Mac rendering/model paths in the stages that introduce them, and record actual evidence separately from mocked or static checks. Never require the original two private production songs to install or test the open-source toolkit.

A change should correspond to one meaningful slice with independent acceptance. Stage explicit files, inspect the staged diff and commit only after relevant checks pass. Local commit permission does not authorize publishing or pushing. External media, generated assets, model weights and raw provider metadata remain in the production workspace.
