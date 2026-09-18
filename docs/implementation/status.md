# Implementation status

## S11 same-audio variant comparison complete — 2026-09-19

`mvt compare --request FILE --output DIR` now consumes two or more completed preview manifests and
never invokes analysis, alignment, plan resolution, preview rendering or rendering. The typed
request preserves stable variant IDs, labels and order. The completed comparison manifest binds the
request, canonical and original source identities, exact global ranges, actual media probes,
decoded per-range audio hashes, each variant's input/environment/seed evidence, tool versions and
generated artifact hashes. Python models remain authoritative and generated schemas plus synthetic
examples cover both new artifacts.

Preflight verifies every referenced preview clip and optional per-preview reel hash, requires exact
frame counts from the probed rational fps, and rejects source, range, profile, audio and hash
mismatches before output installation. The comparison directory is installed atomically and
contains `comparison.json`, an FFmpeg stream-copy reel in range-major then variant-major order, and
a deterministic labeled contact sheet sampled at each clip's midpoint. Intact identical work hits
the cache only after all input/output hashes and media probes are revalidated; stale, partial,
tampered or differently keyed directories fail without overwrite. Reordering variants changes the
comparison identity and reel order.

The public S11 fixture generator creates actual A/B/C H.264/AAC clips with shared source,
timeline/lyrics/renderer identities and differing plan/assets hashes. Its integration decoded all
90 reel frames to prove A/B/C then A/B/C ordering, inspected all six label bands and midpoint cells,
and passed while every upstream pipeline entry point was replaced with a hard failure. Focused S11
tests report 5 passed. Commits are `5fad921` (contracts/schemas/examples), `827f629` (atomic command
and strict preflight), `2f7f667` (real review-artifact proof), plus the commit containing this
handoff and the final optional-reel hash-validation fix.

External acceptance is under `../projects/soft-harm/s11/`. A abstract and B mood-media were resolved
and rendered from the same S10 canonical audio, production timeline, reviewed edited lyrics,
checked assets and 10–22 s / 39–51 s / 190–202 s ranges. C reuses the byte-identical approved S10
`preview-v6-bulge` clips. The comparison cache key is
`37f7b53b78f7b33234ca51ed2673e89643405043df45c1d320dfa367b8a807f3`; manifest SHA-256 is
`46c79214322c208807f3c7d4d916e3d6dfcffe6f84a821efd118026ce7bdd785`, reel SHA-256 is
`6172e2d85030f4002cc4175f5014fdecf021582d5bb9d55f2e2add5b25eba4d8`, and contact-sheet SHA-256
is `e327165c8cc04da56e4d5b610f09dc75abc7880538298dfd70a0345e75899875`. The reel probes as H.264
1920x1080/30 fps with 3240 frames and AAC 48 kHz stereo; the contact sheet is 1440x900. Cache replay
and standalone schema validation passed. Visual inspection confirmed the 3x3 labels and expected
A/B/C compositions only; no subjective winner or new user approval is claimed.

The parent project index, both production-case READMEs, both canonical sample counts and both
`case.json` status blocks now reflect actual S10 evidence. These external ledgers and all S11 song
plans/media remain outside this Git repository. Comparison remains limited to compatible completed
preview streams; fixed landscape output and SwiftShader production rendering remain current
constraints, and subjective review stays external.

## S10 songs and release readiness complete — 2026-09-18

Two external C-mode production projects use the reviewed S07 lyric artifacts, manual neutral
sections and generated local backgrounds. Review iterations first corrected global route pre-roll
and hard-edged abstract layers, then replaced the flat caption treatment with a deterministic 3D
bulge shader, pearlescent lighting and restrained transparent entry/exit trails. The implementation
adapts the MIT-licensed [Codrops bulge-text technique](https://github.com/romanjeanelie/bulge-text-effect-codrops)
to the fixed sample clock. The user approved
the thin artistic typography direction on 2026-09-17. English uses local Snell Roundhand; Chinese
uses a local SIL OFL LXGW WenKai Light copy. macOS font preflight now falls back to `mdimport` when a
valid local font is outside the Spotlight index.

Both 36-second approval reels are H.264 1920x1080 at 30 fps with exactly 1080 frames and AAC 48 kHz
stereo audio. The configured scan found no black interval; measured peaks are -1.06 dBFS and -2.47
dBFS. Their manifests, probes, black scans, audio statistics, contact sheets and approval records
remain outside Git under `../projects/soft-harm/s10/` and
`../projects/zhi-mai-yi-ren-fen/s10/`. Superseded flat, heavy and invalid-pre-roll versions remain
evidence only.

The Chinese final is 6611/6611 frames with a 6.500 ms endpoint delta, no detected black interval and
a -2.36 dBFS peak. Its MP4 SHA-256 is
`581051a3a344719b451b2113fca135c79ab392d00b722a9af366c0f06c0ea3ec`; its manifest SHA-256 is
`b79a27b402d6cc36a1748fc9b9e4e59e547d653ff4de845df2a61e40089c4f47`. The English final is
6833/6833 frames with a 5.688 ms endpoint delta, no detected black interval and a -0.64 dBFS peak.
Its MP4 SHA-256 is `7b52ec92959017e4f935bfdec2ae9335ba5bae47f9306442b53cd4eedf147e51`;
its manifest SHA-256 is `4615f044aa29a322295f5b299cefa53d06c92819e2155228d2f38b35ffd30bff`.
Both are H.264 1920x1080 at 30 fps with AAC 48 kHz stereo audio. Contact-sheet inspection covered
opening gaps, sparse and transition passages, bright climaxes, repeated lyric lines and tails; text
remained legible and inside the safe area. The first parallel English attempt failed with an FFmpeg
pipe `EPIPE` before installing output. After reinstalling pinned Playwright Chromium revision 1243
and confirming renderer readiness, its retry completed with Node 24.15.0 and SwiftShader.

An isolated source copy with environments, build output and caches excluded completed locked Python
and Node installation, Playwright Chromium discovery, distribution build and the autonomous public
demo. With analysis, alignment and model paths deliberately unavailable, its saved-artifact full
rerender was byte-identical. Evidence is outside Git at
`../projects/synthetic-s10-clean-install/`. Production inputs, lyrics, fonts and rendered media have
not entered Git. Push, remote publication and distribution remain separate user-authorized actions.

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

Current commands: `mvt --help`, `--version`, `capabilities`, `doctor`, `decode`, `analyze`, `assets check`, `lyrics import`, `lyrics align`, `lyrics apply-edits`, `plan resolve`, `preview`, `compare`, `render`, `validate`, `schema`. Single-artifact validation includes structure and local semantic invariants. Decode, analyze, asset/lyric checking, plan resolution, preview, compare and render perform the cross-file/media preflight they need. `can_render` is true for the S02 fixture plus S04–S10 A/B/C, saved-lyric, multi-range preview and public production-demo scope; compare is available for completed same-audio previews.

Current analyzer: isolated locked librosa/audio-separator environment, explicit feature window/padding/normalization policy, real four-file verification and exact canonical sample alignment. Current renderer: integer clock, Playwright/Three.js WebGL host, bounded abstract/media layers, deterministic FFmpeg video-frame extraction, embedded checked fonts, sample-clock lyric motion with a subdivided 3D bulge surface, PNG frame pipe and FFmpeg MP4 encoder. Repository JSON examples still contain synthetic hashes and absent media; they are protocol examples rather than render results.

## Verified

- `uv sync --locked --group dev`: succeeded with Python 3.12.13.
- `uv run --locked pytest -q`: **114 passed in 226.46s** (including actual browser/FFmpeg production rehearsals through S10 and real FFmpeg S11 A/B/C comparison artifacts).
- `uv run --locked pytest tests/stages/test_s01.py -q`: **12 passed** with real FFmpeg/ffprobe 8.1. A generated 11,025-frame mono 44.1kHz WAV was encoded to MP3, decoded from a different cwd through Chinese/space-bearing paths, and verified as 48kHz stereo 24-bit PCM with its actual decoded frame count. Cache reuse, different-input conflict, missing tools, corrupt input, partial output and cleanup paths passed.
- `uv run --locked ruff check .` and `ruff format --check .`: passed.
- `uv run --locked python scripts/export_schemas.py --check`: fourteen schemas match models; tests also validate JSON Schema structure and examples.
- `pnpm --dir renderer install --frozen-lockfile`: passed.
- `pnpm --dir renderer check`: TypeScript build plus **21 tests passed**; also explicitly verified with Node 24.15.0 on PATH.
- `pnpm --dir renderer install --frozen-lockfile` and `pnpm --dir renderer exec playwright install chromium`: Playwright 1.63.0 / Chromium revision 1243 installed; browser version 153.0.8010.12.
- `uv run --locked pytest tests/stages/test_s02.py -q`: **2 passed** with actual Chromium and FFmpeg; no browser skip.
- `uv sync --project environments/separation --locked`: Python 3.12 environment resolved with audio-separator 0.44.2, librosa 0.10.2.post1, torch 2.14.0 and ONNX Runtime 1.30.0. `audio-separator --env_info` selected MPS/CoreML.
- `uv run --locked pytest tests/stages/test_s03.py -q`: **6 passed**. Synthetic four-track tests cover canonical timing, final-window padding, silence, required signals/events, explicit pad/trim records, cache reuse and false-success rejection.
- `uv run --locked pytest tests/stages/test_s05.py -q`: **9 passed**. Asset identity/type/cache failures, bounded media policies, exact numbered video frames, section crossfade, A/B/C encoding, media-audio exclusion and valid unindexed macOS font fallback passed.
- `uv run --locked pytest tests/stages/test_s06.py -q`: **6 passed**. LRC/SRT semantics, CLI output, edit preservation, off mode, cross-file identity and a real 75-frame bilingual caption render passed.
- `uv run --locked pytest tests/stages/test_s07.py -q`: **5 passed**. Known-text mapping, repeated lyrics, unmatched lines, fixed reference metrics, complete edit application, cache/conflict handling, missing runtime and CLI output passed.
- `uv run --locked pytest tests/stages/test_s08.py -q`: **5 passed in 29.26s**. Actual full/excerpt rendering, global frame equivalence, start-audio alignment, independent reproduction, cache reuse and stale/missing-output rejection passed.
- `uv run --locked pytest tests/stages/test_s09.py -q`: **2 passed in 84.37s**. Capability/doctor preflight, sample feedback gating, autonomous first cut, complete artifact bundles, mode-specific scripts, no-model rerenders and byte-identical full reproduction passed.
- `uv run --locked pytest tests/stages/test_s11.py -q`: **5 passed**. Contract/preflight/cache/tamper/conflict paths, optional preview-reel hash validation, actual FFmpeg A/B/C order, labeled midpoint contact sheet and upstream-pipeline isolation passed.
- Two external 20-second excerpts completed the formal `mvt analyze --stems four` path, artifact/schema validation and a second cached run. Reports and generated media remain outside Git in each case's `s03/` directory.
- `uv build`: wheel and source archive built; isolated wheel-installed `mvt capabilities` worked. Archive inspection found no original songs, local production workspace or generated media.
- skill-creator `quick_validate.py`: passed using PyYAML in the project environment. Markdown local links checked.
- Two external song audio hashes match their supplied metadata; actual ffprobe container durations are in the external case records.

Model installation/inference, browser/WebGL rendering, external media composition, imported/automatic/edited lyrics, video export, saved-artifact preview reproduction and both production review modes have now been exercised on the stated bounded S02–S10 paths. Human stem listening QA, two-song lyric timing review and the final typography direction were accepted. Full-song objective media QA passed. Public release remains open and requires separate authorization.

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
| S10 songs/release readiness | Complete — final full-song renders and objective QA recorded |
| S11 same-audio variant comparison | Complete — `5fad921`, `827f629`, `2f7f667` plus handoff |
| S12 portrait and repeated structure | Designed and authorized — depends on S11, not implemented |
| S13 Astrofox automated backend | Designed and authorized — depends on S12, not implemented |

## Exact next action

S11 is complete. The exact next development action is S12
([portrait output and repeated structure](S12-portrait-structure.md)); S13 must wait for S12's
committed acceptance evidence. User viewing or separately authorized publication of local final or
comparison media remains optional and is not required to validate the repository.

On the original host the parent workspace has `projects/README.md`, `projects/soft-harm/case.json`
and `projects/zhi-mai-yi-ren-fen/case.json`. These are updated local source inventories, not runtime
schemas. Parent audio, lyrics, generated material, raw metadata, reviews, comparisons and case notes
stay outside this Git history.
