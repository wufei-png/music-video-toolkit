# Implementation status

## S01 canonical audio complete — 2026-09-15

`mvt decode INPUT --project DIR` now decodes the explicit first audio stream to `source/canonical.wav` as 48kHz stereo 24-bit `pcm_s24le`. It writes `source/source.json` with original/canonical hashes, actual decoded PCM frame count, fixed parameters and FFmpeg version. Writes use same-directory temporary files and atomic replacement after decode/probe success. A matching input hash reuses a preflighted result; incomplete, invalid or different existing sources fail without overwrite.

Project source preflight resolves paths from the record location rather than cwd. It verifies the fixed canonical path, file/hash identity, WAV rate/channels/sample width and frame count. The original input is required when confirming a new decode and optional for later canonical-only work.

Commits: `8f1e4f6` (source contract/preflight), `77426ca` (decode/CLI/integration tests), plus the commit containing this status handoff.

## Bootstrap complete — 2026-09-15

| Batch | Actual delivery | Commit |
| --- | --- | --- |
| Design and handoff | Confirmed decisions, 10 slice documents, production Skill and separate developer entry | `8cd61d4` |
| Python skeleton | Installable CLI, five strict file contracts, schema exporter, synthetic examples, 41 tests | `be08bd7` |
| Renderer and final handoff | Typed Three.js layer/frame interfaces, exact frame/sample mapping, cross-language vectors, final local-case handoff | Commit containing this status update |

Current commands: `mvt --help`, `--version`, `capabilities`, `doctor`, `decode`, `validate`, `schema`. Single-artifact validation includes structure and local semantic invariants. Decode performs canonical source project preflight. `can_render` is **false**.

Current renderer: arithmetic and interfaces only. No WebGL host, visual layer implementation, media loading, caption rendering, audio analyzer, model adapter or MP4 pipeline exists. JSON examples contain explicitly synthetic hashes and absent media; they are not render results.

## Verified

- `uv sync --locked --group dev`: succeeded with Python 3.12.13.
- `uv run --locked pytest -q`: **54 passed** (including 12 S01 tests and the rational clock vectors).
- `uv run --locked pytest tests/stages/test_s01.py -q`: **12 passed** with real FFmpeg/ffprobe 8.1. A generated 11,025-frame mono 44.1kHz WAV was encoded to MP3, decoded from a different cwd through Chinese/space-bearing paths, and verified as 48kHz stereo 24-bit PCM with its actual decoded frame count. Cache reuse, different-input conflict, missing tools, corrupt input, partial output and cleanup paths passed.
- `uv run --locked ruff check .` and `ruff format --check .`: passed.
- `uv run --locked python scripts/export_schemas.py --check`: six schemas match models; tests also validate JSON Schema structure and examples.
- `pnpm --dir renderer install --frozen-lockfile`: passed.
- `pnpm --dir renderer check`: TypeScript build plus **13 tests passed**; also explicitly verified with Node 24.15.0 on PATH.
- `uv build`: wheel and source archive built; isolated wheel-installed `mvt capabilities` worked. Archive inspection found no original songs, local production workspace or generated media.
- skill-creator `quick_validate.py`: passed using PyYAML in the project environment. Markdown local links checked.
- Two external song audio hashes match their supplied metadata; actual ffprobe container durations are in the external case records.

No listening QA, model installation/inference, automatic lyric alignment, browser/WebGL rendering, video export, Skill behavioral forward-test or public release was performed. These remain future acceptance gates; static tests do not establish them.

## Future slices

| Slice | State |
| --- | --- |
| S01 canonical audio | Complete — `8f1e4f6`, `77426ca` |
| S02 minimal renderer | Not started — **next** |
| S03 stems/features | Not started |
| S04 abstract/sections | Not started |
| S05 media/hybrid | Not started |
| S06 imported lyrics | Not started |
| S07 automatic alignment | Not started |
| S08 samples/reproduction | Not started |
| S09 production workflow | Not started |
| S10 songs/release readiness | Not started |

## Exact next action

Read [S02](S02-minimal-render.md), inspect the canonical source/preflight code and current renderer clock/interfaces, then prove the smallest unattended fixed-frame MP4 path on this Mac. Preserve S01 and bootstrap regressions, create `tests/stages/test_s02.py`, and use the portable implement-in-stages contract in [START-HERE](START-HERE.md).

On the original host the parent workspace has `projects/README.md`, `projects/soft-harm/case.json` and `projects/zhi-mai-yi-ren-fen/case.json`. These are local source inventories, not runtime schemas. Case-specific lyric display mode, visual material/style and exact sample ranges await production decisions. Parent audio/lyrics/raw metadata and case notes are outside this Git history.
