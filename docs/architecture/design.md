# Confirmed design — 2026-09-15

## Product and scope

A music video toolkit for AI agents. The user chose both reusable open-source tooling and polished videos, with feedback from the two songs improving the toolkit. The primary entry is a production Skill from the beginning; an embedded agent or generation-service orchestrator is not needed.

| Decision | Contract |
| --- | --- |
| Repository | `music/music-video-toolkit/`, its own Git history; parent remains production workspace |
| License | MIT for original code and Skill |
| First platform | macOS Apple Silicon; Linux/NVIDIA is future work |
| Output acceptance | 1920×1080 landscape, 30fps, H.264 video + AAC audio, MP4 |
| Visual modes | A abstract, B external-media mood scenes, C reusable A+B layers |
| Planning | Whole-song defaults; per-section overrides, not arbitrary shot-editor complexity |
| Lyrics | Off, imported timings, automatic alignment; editable line-level results |
| Materials | Local files from users or harness generation tools; replaceable via manifest |
| Interaction | Sample approval default, autonomous first cut opt-in |
| Samples | Several excerpts totaling about 30–60s: sparse, climax, transition |
| Runtime | Python analysis/tools, TypeScript + Three.js fixed-frame rendering, FFmpeg IO |
| Reproduction | Saved plan + analysis + assets + versions can run without a model |

## Responsibilities

```text
Production Skill / harness
  → creative brief + material requests + review decisions
  → timeline.json + visual-plan.json + assets.json + lyrics.json
  → independent CLI tools → fixed-frame render adapter → FFmpeg
  → previews + render manifest + feedback
```

The Skill interprets lyrics and musical context, chooses scenes, uses available image/video tools and iterates. It should not synthesize executable JavaScript, GLSL or shell into a plan. Rendering accepts registered layers and bounded parameters only. CLI tools neither call LLMs nor orchestrate generation providers.

Python owns protocol validation and music processing. The renderer consumes a resolved, validated frame contract. A and B share layer lifecycle, clock, transform, alpha and composition. C selects both categories; no separate C rendering engine. Static background/title alone is not adequate acceptance for polished full-song A or B modes.

## First technical choices

- FFmpeg decodes each original once into a canonical 48kHz PCM WAV; actual decoded samples are authoritative. Analyzer resampling is derived from that WAV and maps back to its clock.
- `python-audio-separator` is the first separation adapter candidate; start by proving a 4-stem model on this Mac. Models are optional downloaded execution dependencies with explicit identities/hashes.
- librosa is the initial feature backend. Initial signals: mix/stem RMS, drums onset, bass low energy, mix beat/chroma. Beat is not downbeat; do not invent bar phase or semantic section labels.
- Automatic segmentation may propose novelty/energy boundaries. Semantic labels and boundaries can be corrected by the Skill/user and retain provenance.
- Lightweight Three.js host + FFmpeg is the first renderer. First prove frame capture, Chinese text, media loading and export locally. No desktop editor is part of v1.
- Automatic lyric alignment is an isolated optional dependency environment. WhisperX CPU is the first candidate, not a validated singing solution. Align supplied words; do not silently substitute ASR transcriptions. Prove Chinese/English repeated choruses early in S07.
- GPU numerical identity across hardware is not promised. Fixed timeline/event mapping must match exactly; rendered comparison uses a documented tolerance within the same locked environment.

## Production policy

Default: agree direction → generate/import media → several short samples → wait for review → full render. Autonomous mode may complete a first cut without sample approval, within the user's requested scope and budget. A changed plan/material set invalidates the old approval for affected excerpts; preserve feedback and version identifiers. If no generator is available, use supplied media or ask for the missing input, never claim material was generated.

Sample rendering must use global song time. Stateful simulation requires deterministic seek/pre-roll or a pure time-indexed implementation. Starting an excerpt at frame zero must not reset its song position.

## Selected post-S10 direction

Post-S10 development proceeds in three dependency-ordered slices:

1. A renderer-neutral comparison artifact must first prove that variants use the same canonical
   audio, global sample ranges and output profile while binding every differing input. Comparison
   consumes completed previews; it does not hide rendering or creative changes.
2. Output profiles remain a closed compatibility surface. The next profile is 1080x1920 at 30 fps
   alongside the existing 1920x1080 at 30 fps, not arbitrary dimensions. Automatic structure work
   emits provenance-bearing, unlabeled candidates into a separate artifact and requires an explicit
   apply step; it never silently relabels or replaces a timeline.
3. External visual backends return a silent constant-frame-rate visual plus a manifest that binds
   backend, project, plugin, asset, parameter and output identities. MVT retains canonical audio,
   lyrics, comparison and final QA. Astrofox automation is the first full adapter: a pinned
   downstream `astrofox-render` CLI drives its hidden Electron renderer and deterministic export
   bridge without Playwright, AppleScript or UI clicks. Manual editor handoff is a diagnostic
   fallback. In the S13 sequence, projectM received only a locked feasibility proof.
   The separately authorized S14 slice added one hash-approved preset adapter.

The later S15 user review admitted exactly two additional self-authored hash-bound
projectM presets; it did not authorize arbitrary preset packs or automatic style
selection. For `soft-harm`, the selected preference is soft flow; suitability for
other songs remains a per-song review.

Linux + NVIDIA validation, 4K/60fps, arbitrary projectM preset packs, pitch/downbeat analyzers and GUI
editing remain later work. AI service orchestration is outside the core; extend the harness-facing
workflow only when a concrete need appears.

## Delivery separation

This session creates documentation, protocols, command skeleton, rendering contract and local case handoff. It does not deliver rendered songs, model benchmarks or public hosting. Remote GitHub creation/push is not part of the authorized local bootstrap. Development stages and production approval checkpoints are separate workflows.
