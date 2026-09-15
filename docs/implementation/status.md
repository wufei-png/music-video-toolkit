# Implementation status

## S09 production workflow complete — 2026-09-16

The production Skill now routes to current capabilities, `mvt doctor`, exact saved-artifact commands and a rights-safe public production demo. It records the review mode before rendering, keeps full-render commands out of sample-approval runs until feedback accepts the shown plan/material version, and labels autonomous self-review accurately. It also documents the 1600-sample preview frame grid, cache/output-directory behavior and current decode → analyze → assets/lyrics → plan → preview → render sequence.

`examples/production-demo/create_fixture.py` generates a three-second synthetic song and image outside the checkout, plus a C visual plan, brief, preview ranges, feedback record, mode-specific workflow script and independent no-model rerender scripts. The sample-approval integration stopped after three clips/review reel; only an explicit synthetic reviewer approval added by the test preceded its full render. The autonomous integration produced a 90-frame first cut immediately. With all analysis/alignment/model paths deliberately unavailable, saved-artifact preview/full rerenders succeeded; the autonomous first cut was byte-identical.

Persistent rehearsals are outside Git at `../projects/synthetic-s09-sample/`, `../projects/synthetic-s09-autonomous/` and `../projects/synthetic-s09-generated/`, with command logs, manifests and feedback. The last case replaced the deterministic fixture image with a built-in imagegen result and passed asset preflight, C preview and full render. Contact-sheet review found all layers present and a bright climax that is a plan-level taste adjustment. No third-party or generated media entered the repository. Skill structure/link validation passed. Independent model behavioral forward-testing was not authorized and remains unverified; direct CLI behavior was exercised instead.

## S08 reproducible multi-range previews complete — 2026-09-16

`mvt preview --project DIR --plan FILE --ranges FILE --output DIR [--review-reel]` now renders uniquely named, ordered and non-overlapping global sample ranges. Range endpoints must be inside the canonical song and align to the 30 fps frame grid. Each clip starts its container at zero while visual, media and lyric evaluation retains the whole-song frame clock; FFmpeg seeks the canonical audio to the same global sample. The optional review reel concatenates clips in request order.

Every render manifest now has a deterministic cache key and binds the source record, timeline/analysis, plan, asset manifests and material files including fonts, Python/TypeScript renderer sources, dependency lock, seed, fps and selected range. The aggregate preview manifest additionally binds the range request and review-reel choice. Cache reuse verifies the exact key, inputs, ranges and every output hash. Existing stale, incomplete or damaged output directories fail without overwrite, and failed temporary jobs cannot leave a completed aggregate manifest.

The real S08 test rendered one five-second 1080p30 synthetic full video and two independent 0.5-second clips twice. All 30 preview frames matched their corresponding global full-render frames within the encoded-pixel tolerance; clicks at both clip starts remained within 50 ms of local audio zero. The two independent preview runs shared the same cache identity, an intact repeated request hit the cache, and changed plan/seed plus missing output evidence were rejected. The preview execution path consumes saved artifacts and invokes neither analysis nor alignment/model runtimes.

## S07 automatic lyric alignment complete — 2026-09-16

`mvt lyrics align --text FILE --project DIR --language en|zh` now runs an isolated locked WhisperX 3.8.6 CPU/int8 adapter, preferring a hash-verified vocals stem and otherwise using canonical audio with an explicit zero offset. Pyannote VAD and pinned English/Chinese alignment models provide timing evidence. A global monotonic exact-character mapping returns the user's supplied text in source order, preserves repeated choruses and reports low-coverage lines as unmatched instead of substituting ASR text. Cache identity includes source text, selected audio, language, references, adapter configuration, runner and runtime lock.

Optional independent reference points record fixed median 250 ms and nearest-rank P90 500 ms gates. `mvt lyrics apply-edits` consumes a complete reviewed onset set and writes a separate origin `edited` artifact, filling previously unmatched lines and deriving each cue end from the next reviewed start or song end without rerunning the model. Different or invalid existing automatic and edited outputs are preserved.

Both full local songs completed real model runs on vocals. soft-harm aligned 48/48 lines in 33.06 seconds and passed 12 reviewed points with 120 ms median / 236 ms P90; its corrected artifact has 48 lines. 只买一人份 aligned 34/39 lines in 45.55 seconds, explicitly reported five unmatched lines, and passed 12 reviewed points with 118.5 ms median / 301 ms P90; the reviewed artifact fills all 39 lines. Evidence and corrected lyrics remain outside Git under each case's `s07/mvt-project/` directory. The user completed both listening/timing reviews on 2026-09-16.

## S06 imported lyrics and bilingual layout complete — 2026-09-15

`mvt lyrics import FILE --project DIR --language TAG` now converts strict UTF-8 LRC/SRT into canonical sample-clock cues. LRC preserves source order and repeated lines, derives each end from the next retained timestamp or song end, and records that policy, offset and skipped stage headings. SRT preserves explicit multiline text and endpoints; overlaps, malformed/empty/overlong cues and out-of-bounds times fail. The artifact binds source text and canonical audio hashes plus importer provenance. Identical imports reuse the result, while different, edited or invalid existing output is never overwritten.

Enabled lyrics now require a checked font asset. Resolved plans rebase the lyric path and bind its hash; render verifies lyric/audio/font identity without running alignment. The browser embeds the pinned font, uses half-open cue ownership and a 100 ms sample-clock fade, wraps up to five centered lines inside a fixed safe-area panel, and leaves lyric gaps clear. Off mode carries no lyric path, font or hash and does not open the default lyric file.

The 2.5-second acceptance encoded 75 frames with Chinese/English multiline text, punctuation, a long sentence and an empty interlude. Frame 10 showed the first bilingual cue, frame 30 had no caption, and frame 50 showed the wrapped long cue; automated lower-frame comparisons and visual inspection confirmed timing and margins. Persistent output is outside Git at `/Users/wufei2/github.com/wufei-png/music/projects/synthetic-s06/project/`. The local Arial Unicode system font proves this host only and is neither copied nor claimed as distributable.

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

Current commands: `mvt --help`, `--version`, `capabilities`, `doctor`, `decode`, `analyze`, `assets check`, `lyrics import`, `lyrics align`, `lyrics apply-edits`, `plan resolve`, `preview`, `render`, `validate`, `schema`. Single-artifact validation includes structure and local semantic invariants. Decode, analyze, asset/lyric checking, plan resolution, preview and render perform the project preflight they need. `can_render` is true for the S02 fixture plus S04–S09 A/B/C, saved-lyric, multi-range preview and public production-demo scope.

Current analyzer: isolated locked librosa/audio-separator environment, explicit feature window/padding/normalization policy, real four-file verification and exact canonical sample alignment. Current renderer: integer clock, Playwright/Three.js WebGL host, bounded abstract/media layers, deterministic FFmpeg video-frame extraction, embedded checked fonts, line-level caption layout, PNG frame pipe and FFmpeg MP4 encoder. Repository JSON examples still contain synthetic hashes and absent media; they are protocol examples rather than render results.

## Verified

- `uv sync --locked --group dev`: succeeded with Python 3.12.13.
- `uv run --locked pytest -q`: **98 passed in 211.85s** (including actual browser/FFmpeg production rehearsals through S09).
- `uv run --locked pytest tests/stages/test_s01.py -q`: **12 passed** with real FFmpeg/ffprobe 8.1. A generated 11,025-frame mono 44.1kHz WAV was encoded to MP3, decoded from a different cwd through Chinese/space-bearing paths, and verified as 48kHz stereo 24-bit PCM with its actual decoded frame count. Cache reuse, different-input conflict, missing tools, corrupt input, partial output and cleanup paths passed.
- `uv run --locked ruff check .` and `ruff format --check .`: passed.
- `uv run --locked python scripts/export_schemas.py --check`: twelve schemas match models; tests also validate JSON Schema structure and examples.
- `pnpm --dir renderer install --frozen-lockfile`: passed.
- `pnpm --dir renderer check`: TypeScript build plus **20 tests passed**; also explicitly verified with Node 24.15.0 on PATH.
- `pnpm --dir renderer install --frozen-lockfile` and `pnpm --dir renderer exec playwright install chromium`: Playwright 1.63.0 / Chromium revision 1243 installed; browser version 153.0.8010.12.
- `uv run --locked pytest tests/stages/test_s02.py -q`: **2 passed** with actual Chromium and FFmpeg; no browser skip.
- `uv sync --project environments/separation --locked`: Python 3.12 environment resolved with audio-separator 0.44.2, librosa 0.10.2.post1, torch 2.14.0 and ONNX Runtime 1.30.0. `audio-separator --env_info` selected MPS/CoreML.
- `uv run --locked pytest tests/stages/test_s03.py -q`: **6 passed**. Synthetic four-track tests cover canonical timing, final-window padding, silence, required signals/events, explicit pad/trim records, cache reuse and false-success rejection.
- `uv run --locked pytest tests/stages/test_s05.py -q`: **8 passed**. Asset identity/type/cache failures, bounded media policies, exact numbered video frames, section crossfade, A/B/C encoding and media-audio exclusion passed.
- `uv run --locked pytest tests/stages/test_s06.py -q`: **6 passed**. LRC/SRT semantics, CLI output, edit preservation, off mode, cross-file identity and a real 75-frame bilingual caption render passed.
- `uv run --locked pytest tests/stages/test_s07.py -q`: **5 passed**. Known-text mapping, repeated lyrics, unmatched lines, fixed reference metrics, complete edit application, cache/conflict handling, missing runtime and CLI output passed.
- `uv run --locked pytest tests/stages/test_s08.py -q`: **5 passed in 29.26s**. Actual full/excerpt rendering, global frame equivalence, start-audio alignment, independent reproduction, cache reuse and stale/missing-output rejection passed.
- `uv run --locked pytest tests/stages/test_s09.py -q`: **2 passed in 84.37s**. Capability/doctor preflight, sample feedback gating, autonomous first cut, complete artifact bundles, mode-specific scripts, no-model rerenders and byte-identical full reproduction passed.
- Two external 20-second excerpts completed the formal `mvt analyze --stems four` path, artifact/schema validation and a second cached run. Reports and generated media remain outside Git in each case's `s03/` directory.
- `uv build`: wheel and source archive built; isolated wheel-installed `mvt capabilities` worked. Archive inspection found no original songs, local production workspace or generated media.
- skill-creator `quick_validate.py`: passed using PyYAML in the project environment. Markdown local links checked.
- Two external song audio hashes match their supplied metadata; actual ffprobe container durations are in the external case records.

Model installation/inference, browser/WebGL rendering, external media composition, imported/automatic/edited lyrics, video export, saved-artifact preview reproduction and both production review modes have now been exercised on the stated bounded S02–S09 paths. Human stem listening QA and two-song lyric timing review were accepted. Independent Skill behavioral forward-testing, two-song visual approval and public release remain open. Automated and objective checks do not establish subjective visual or song quality.

## Future slices

| Slice | State |
| --- | --- |
| S01 canonical audio | Complete — `8f1e4f6`, `77426ca` |
| S02 minimal renderer | Complete — `380b9cf` |
| S03 stems/features | Complete — `7c01627` plus accepted external review |
| S04 abstract/sections | Complete — commit containing this handoff |
| S05 media/hybrid | Complete — commit containing this handoff |
| S06 imported lyrics | Complete — commit containing this handoff |
| S07 automatic alignment | Complete — commit containing this handoff |
| S08 samples/reproduction | Complete — commit containing this handoff |
| S09 production workflow | Complete — commit containing this handoff |
| S10 songs/release readiness | Not started — **next** |

## Exact next action

Read [S10](S10-songs-quality.md), then prepare C-mode samples for both external songs, collect visual feedback, render full versions and finish clean-install/release checks.

On the original host the parent workspace has `projects/README.md`, `projects/soft-harm/case.json` and `projects/zhi-mai-yi-ren-fen/case.json`. These are local source inventories, not runtime schemas. Case-specific lyric display mode, visual material/style and exact sample ranges await production decisions. Parent audio/lyrics/raw metadata and case notes are outside this Git history.
