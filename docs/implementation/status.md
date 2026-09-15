# Implementation status

## S02 fixed-frame render complete — 2026-09-15

`mvt render --project DIR --plan FILE --output FILE` now supports the bounded S02 fixture plan (`s02.pulse`, `s02.image`, `s02.text`). A pinned Playwright Chromium waits for local PNG and font readiness, captures 1920×1080 frames at global song time, and streams them with backpressure into FFmpeg H.264/AAC encoding. Output and render manifest are installed atomically after ffprobe verifies codecs, size, rate and exact frame count.

The 5-second synthetic acceptance placed audio clicks at 1/2/3 seconds and visual pulses at frames 30/60/90. Decoding the MP4 confirmed sync within one frame. Two complete renders produced identical MP4 SHA-256 values. Chinese glyph ink and local image readiness were checked. Chromium 153.0.8010.12 reported ANGLE SwiftShader software rendering, so hardware acceleration remains unproven.

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

Current commands: `mvt --help`, `--version`, `capabilities`, `doctor`, `decode`, `render`, `validate`, `schema`. Single-artifact validation includes structure and local semantic invariants. Decode and render perform the project preflight they need. `can_render` is **true for the explicit S02 fixture scope only**.

Current renderer: integer clock, Playwright/Three.js WebGL host, deterministic fixture scene, PNG frame pipe and FFmpeg MP4 encoder. No production visual layer set, general media behavior, caption layout, audio analyzer or model adapter exists. Repository JSON examples still contain synthetic hashes and absent media; they are not render results and their layer kinds are not yet executable.

## Verified

- `uv sync --locked --group dev`: succeeded with Python 3.12.13.
- `uv run --locked pytest -q`: **56 passed** (including 12 S01 tests, 2 real S02 browser tests and the rational clock vectors).
- `uv run --locked pytest tests/stages/test_s01.py -q`: **12 passed** with real FFmpeg/ffprobe 8.1. A generated 11,025-frame mono 44.1kHz WAV was encoded to MP3, decoded from a different cwd through Chinese/space-bearing paths, and verified as 48kHz stereo 24-bit PCM with its actual decoded frame count. Cache reuse, different-input conflict, missing tools, corrupt input, partial output and cleanup paths passed.
- `uv run --locked ruff check .` and `ruff format --check .`: passed.
- `uv run --locked python scripts/export_schemas.py --check`: six schemas match models; tests also validate JSON Schema structure and examples.
- `pnpm --dir renderer install --frozen-lockfile`: passed.
- `pnpm --dir renderer check`: TypeScript build plus **13 tests passed**; also explicitly verified with Node 24.15.0 on PATH.
- `pnpm --dir renderer install --frozen-lockfile` and `pnpm --dir renderer exec playwright install chromium`: Playwright 1.63.0 / Chromium revision 1243 installed; browser version 153.0.8010.12.
- `uv run --locked pytest tests/stages/test_s02.py -q`: **2 passed** with actual Chromium and FFmpeg; no browser skip.
- `uv build`: wheel and source archive built; isolated wheel-installed `mvt capabilities` worked. Archive inspection found no original songs, local production workspace or generated media.
- skill-creator `quick_validate.py`: passed using PyYAML in the project environment. Markdown local links checked.
- Two external song audio hashes match their supplied metadata; actual ffprobe container durations are in the external case records.

No listening QA, model installation/inference, automatic lyric alignment, browser/WebGL rendering, video export, Skill behavioral forward-test or public release was performed. These remain future acceptance gates; static tests do not establish them.

## Future slices

| Slice | State |
| --- | --- |
| S01 canonical audio | Complete — `8f1e4f6`, `77426ca` |
| S02 minimal renderer | Complete — commit containing this handoff |
| S03 stems/features | Not started — **next** |
| S04 abstract/sections | Not started |
| S05 media/hybrid | Not started |
| S06 imported lyrics | Not started |
| S07 automatic alignment | Not started |
| S08 samples/reproduction | Not started |
| S09 production workflow | Not started |
| S10 songs/release readiness | Not started |

## Exact next action

Read [S03](S03-stems-features.md), inspect the canonical source/preflight and S02 adapter, then establish the isolated separation/analyzer environments before adding timeline analysis. Prove the real four-stem adapter and both local ≥20-second song excerpts before marking S03 complete; mocks or synthetic stems cannot satisfy that gate.

On the original host the parent workspace has `projects/README.md`, `projects/soft-harm/case.json` and `projects/zhi-mai-yi-ren-fen/case.json`. These are local source inventories, not runtime schemas. Case-specific lyric display mode, visual material/style and exact sample ranges await production decisions. Parent audio/lyrics/raw metadata and case notes are outside this Git history.
