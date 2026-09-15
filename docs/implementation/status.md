# Implementation status

## S05 media and hybrid composition complete — 2026-09-15

`mvt assets check` now preflights local images, constant-frame-rate videos and fonts, writes a typed `assets.checked.json`, and binds both manifest and material asset hashes into its cache identity. It records image dimensions; video dimensions, exact decoded frame count, rational frame rate, duration and audio presence; and macOS font families. Missing, remote, hash-mismatched, mislabeled and variable-frame-rate inputs fail explicitly.

The resolver and fixed-frame renderer now execute image/video media layers in B mood plans and reuse those layer implementations with S04 objects in C hybrid plans. Closed parameters cover fit, placement, scale, bounded motion, z, opacity, circle mask and blend mode. Video uses global sample offsets, half-open source-frame trims and explicit `error|loop|hold`; media audio is always excluded. Section transitions preserve the previous and current media configurations and crossfade them on the canonical sample clock.

The S05 acceptance encoded A/B/C from the same one-second timeline without analysis. A six-frame 2 fps known-color video, carrying its own 880 Hz audio, proved source-frame selection and loop/hold behavior while the rendered audio remained canonical silence. Pixel samples at frames 14/18/23 proved red-to-blue section crossfade; the contact sheets also show the circle mask, alpha overlay and A+B hybrid composition. Persistent synthetic outputs and review sheets are outside Git at `/Users/wufei2/github.com/wufei-png/music/projects/synthetic-s05/project/`. Chromium again reported SwiftShader.

## S04 abstract visuals and section routing complete — 2026-09-15

`mvt plan resolve` now validates the bounded orb/ribbon/particles layer registry and linear/threshold/smooth transforms, rejects missing signals and unknown parameters, and produces a hash-bound `resolved-plan.json`. Contiguous half-open spans cover the full canonical duration. Named timeline sections override whole-song defaults, gaps fall back to those defaults, and manual labels/origins survive resolution. With no sections, RMS novelty creates only unlabeled automatic candidates; silence remains one span.

The fixed-frame browser renderer now samples timeline signals linearly, holds the final value, applies explicit attack/release smoothing and interpolates section parameters during declared transitions. Bass, drums and vocals can drive separately identifiable orb, ribbon and particle objects. Every resolved span retains the mode's required enabled layers.

A synthetic three-second stem-isolation project rendered 90 verified frames in the automated test. A real soft-harm S03 timeline rendered an external 20-second / 600-frame abstract sample; inspection of 3 s, 8 s and 15 s frames found the three objects and their foreground/middle/background hierarchy independently recognizable. SwiftShader remains the measured backend.

## S03 stems/features complete — 2026-09-15

`mvt analyze --project DIR --stems four|none` now produces a renderer-neutral `timeline.json`. `none` emits mix RMS, beat estimates and 12 chroma signals only. `four` runs the locked audio-separator 0.44.2 / `htdemucs.yaml` environment, requires actual vocals/drums/bass/other files, normalizes them to canonical 48kHz stereo 24-bit PCM and adds stem RMS, drums onset and bass low-energy signals. Beat events do not claim downbeat or bar phase.

`stems/stems.json` records model/config hashes, source, license status and every alignment operation. `analysis/run.json` records the source/model/config cache key, runtime lock, timings and output hashes. Cache hits revalidate every referenced artifact and media hash. The adapter catches the observed upstream failure mode where audio-separator printed success and exited 0 without exported files.

Both external 60–80 second song excerpts completed real four-stem inference on Apple Silicon MPS/CoreML. soft-harm took 8.14 seconds and 1,067,368,448 bytes maximum resident set size; zhi-mai-yi-ren-fen took 7.34 seconds and 1,128,775,680 bytes. All eight stems have exactly 960000 canonical samples; natural resampling required no padding/trimming. Objective summed-stem reconstruction SNR measured 35.30 dB and 36.05 dB. The user accepted both four-track listening checks on 2026-09-15.

The soft-harm timeline also drove the S02 renderer through its real `beat` events: the 20-second 1080p30 H.264/AAC result has exactly 600 frames, with all 55 beat events mapped to 55 pulse frames. Chromium still used SwiftShader software rendering.

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

Current commands: `mvt --help`, `--version`, `capabilities`, `doctor`, `decode`, `analyze`, `assets check`, `plan resolve`, `render`, `validate`, `schema`. Single-artifact validation includes structure and local semantic invariants. Decode, analyze, asset checking, plan resolution and render perform the project preflight they need. `can_render` is true for the S02 fixture plus S04/S05 A/B/C layer scope.

Current analyzer: isolated locked librosa/audio-separator environment, explicit feature window/padding/normalization policy, real four-file verification and exact canonical sample alignment. Current renderer: integer clock, Playwright/Three.js WebGL host, bounded abstract/media layers, deterministic FFmpeg video-frame extraction, PNG frame pipe and FFmpeg MP4 encoder. Caption layout does not exist yet. Repository JSON examples still contain synthetic hashes and absent media; they are protocol examples rather than render results.

## Verified

- `uv sync --locked --group dev`: succeeded with Python 3.12.13.
- `uv run --locked pytest -q`: **79 passed** (including 9 S04 tests and 8 S05 cases with real browser/FFmpeg renders).
- `uv run --locked pytest tests/stages/test_s01.py -q`: **12 passed** with real FFmpeg/ffprobe 8.1. A generated 11,025-frame mono 44.1kHz WAV was encoded to MP3, decoded from a different cwd through Chinese/space-bearing paths, and verified as 48kHz stereo 24-bit PCM with its actual decoded frame count. Cache reuse, different-input conflict, missing tools, corrupt input, partial output and cleanup paths passed.
- `uv run --locked ruff check .` and `ruff format --check .`: passed.
- `uv run --locked python scripts/export_schemas.py --check`: ten schemas match models; tests also validate JSON Schema structure and examples.
- `pnpm --dir renderer install --frozen-lockfile`: passed.
- `pnpm --dir renderer check`: TypeScript build plus **18 tests passed**; also explicitly verified with Node 24.15.0 on PATH.
- `pnpm --dir renderer install --frozen-lockfile` and `pnpm --dir renderer exec playwright install chromium`: Playwright 1.63.0 / Chromium revision 1243 installed; browser version 153.0.8010.12.
- `uv run --locked pytest tests/stages/test_s02.py -q`: **2 passed** with actual Chromium and FFmpeg; no browser skip.
- `uv sync --project environments/separation --locked`: Python 3.12 environment resolved with audio-separator 0.44.2, librosa 0.10.2.post1, torch 2.14.0 and ONNX Runtime 1.30.0. `audio-separator --env_info` selected MPS/CoreML.
- `uv run --locked pytest tests/stages/test_s03.py -q`: **6 passed**. Synthetic four-track tests cover canonical timing, final-window padding, silence, required signals/events, explicit pad/trim records, cache reuse and false-success rejection.
- `uv run --locked pytest tests/stages/test_s05.py -q`: **8 passed**. Asset identity/type/cache failures, bounded media policies, exact numbered video frames, section crossfade, A/B/C encoding and media-audio exclusion passed.
- Two external 20-second excerpts completed the formal `mvt analyze --stems four` path, artifact/schema validation and a second cached run. Reports and generated media remain outside Git in each case's `s03/` directory.
- `uv build`: wheel and source archive built; isolated wheel-installed `mvt capabilities` worked. Archive inspection found no original songs, local production workspace or generated media.
- skill-creator `quick_validate.py`: passed using PyYAML in the project environment. Markdown local links checked.
- Two external song audio hashes match their supplied metadata; actual ffprobe container durations are in the external case records.

Model installation/inference, browser/WebGL rendering, external media composition and video export have now been exercised on the stated bounded S02–S05 paths. Human stem listening QA was accepted for the two S03 excerpts. Imported/automatic lyrics, production workflow, Skill behavioral forward-test and public release remain open. Automated and objective checks do not establish subjective visual or song quality.

## Future slices

| Slice | State |
| --- | --- |
| S01 canonical audio | Complete — `8f1e4f6`, `77426ca` |
| S02 minimal renderer | Complete — `380b9cf` |
| S03 stems/features | Complete — `7c01627` plus accepted external review |
| S04 abstract/sections | Complete — commit containing this handoff |
| S05 media/hybrid | Complete — commit containing this handoff |
| S06 imported lyrics | Not started — **next** |
| S07 automatic alignment | Not started |
| S08 samples/reproduction | Not started |
| S09 production workflow | Not started |
| S10 songs/release readiness | Not started |

## Exact next action

Read [S06](S06-lyrics-import.md), then implement imported line timing and bilingual text layout against the S05 fixed sample clock and checked font assets.

On the original host the parent workspace has `projects/README.md`, `projects/soft-harm/case.json` and `projects/zhi-mai-yi-ren-fen/case.json`. These are local source inventories, not runtime schemas. Case-specific lyric display mode, visual material/style and exact sample ranges await production decisions. Parent audio/lyrics/raw metadata and case notes are outside this Git history.
