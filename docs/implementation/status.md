# Implementation status

## Bootstrap complete — 2026-09-15

| Batch | Actual delivery | Commit |
| --- | --- | --- |
| Design and handoff | Confirmed decisions, 10 slice documents, production Skill and separate developer entry | `8cd61d4` |
| Python skeleton | Installable CLI, five strict file contracts, schema exporter, synthetic examples, 41 tests | `be08bd7` |
| Renderer and final handoff | Typed Three.js layer/frame interfaces, exact frame/sample mapping, cross-language vectors, final local-case handoff | Commit containing this status update |

Current commands: `mvt --help`, `--version`, `capabilities`, `doctor`, `validate`, `schema`. Single-artifact validation includes structure and local semantic invariants; it does not inspect media or cross-file references. `can_render` is **false**.

Current renderer: arithmetic and interfaces only. No WebGL host, visual layer implementation, media loading, caption rendering, audio analyzer, model adapter or MP4 pipeline exists. JSON examples contain explicitly synthetic hashes and absent media; they are not render results.

## Verified

- `uv sync --locked --group dev`: succeeded with Python 3.12.13.
- `uv run --locked pytest -q`: **42 passed** (41 contract/CLI tests plus rational clock vector verification).
- `uv run --locked ruff check .` and `ruff format --check .`: passed.
- `uv run --locked python scripts/export_schemas.py --check`: five schemas match models; tests also validate JSON Schema structure and examples.
- `pnpm --dir renderer install --frozen-lockfile`: passed.
- `pnpm --dir renderer check`: TypeScript build plus **13 tests passed**; also explicitly verified with Node 24.15.0 on PATH.
- `uv build`: wheel and source archive built; isolated wheel-installed `mvt capabilities` worked. Archive inspection found no original songs, local production workspace or generated media.
- skill-creator `quick_validate.py`: passed using PyYAML in the project environment. Markdown local links checked.
- Two external song audio hashes match their supplied metadata; actual ffprobe container durations are in the external case records.

No listening QA, model installation/inference, automatic lyric alignment, browser/WebGL rendering, video export, Skill behavioral forward-test or public release was performed. These remain future acceptance gates; static tests do not establish them.

## Future slices

| Slice | State |
| --- | --- |
| S01 canonical audio | Not started — **next** |
| S02 minimal renderer | Not started |
| S03 stems/features | Not started |
| S04 abstract/sections | Not started |
| S05 media/hybrid | Not started |
| S06 imported lyrics | Not started |
| S07 automatic alignment | Not started |
| S08 samples/reproduction | Not started |
| S09 production workflow | Not started |
| S10 songs/release readiness | Not started |

## Exact next action

Read [S01](S01-canonical-audio.md), inspect `src/music_video_toolkit/contracts.py` and CLI, then implement canonical decode + project preflight with real synthetic FFmpeg integration tests. S01 commands and `tests/stages/test_s01.py` do not exist yet. Preserve bootstrap tests and use the portable implement-in-stages contract in [START-HERE](START-HERE.md).

On the original host the parent workspace has `projects/README.md`, `projects/soft-harm/case.json` and `projects/zhi-mai-yi-ren-fen/case.json`. These are local source inventories, not runtime schemas. Case-specific lyric display mode, visual material/style and exact sample ranges await production decisions. Parent audio/lyrics/raw metadata and case notes are outside this Git history.
