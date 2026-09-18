# Post-S10 backlog — 2026-09-19

This is the local, evidence-ordered backlog after S01–S10. On 2026-09-19 the user selected P0, P1
and P2 in order; their confirmed implementation contracts are S11, S12 and S13. Selection does not
make any item an implemented capability. Work on only the first dependency-ready unfinished slice.

## Current baseline

- This audit began from clean `main` at `ea614da`; S01–S10 are complete. `mvt capabilities` reports CLI stage `s09`,
  production stage `s10`, and a fixed 1920x1080/30 fps render scope.
- The two external production finals and their QA evidence exist under
  `../projects/soft-harm/s10/final-v1-bulge/` and
  `../projects/zhi-mai-yi-ren-fen/s10/final-v1-bulge/`. Both have exact expected frame counts,
  H.264 video, AAC 48 kHz stereo audio, and no detected black interval.
- The repository already supports A abstract, B mood-media, and C hybrid plans. One canonical
  audio/timeline/lyrics set can be reused by multiple source plans; `plan resolve --output`,
  `preview --output`, and `render --output` allow distinct resolved plans and outputs. The project
  does not yet provide a first-class variant-comparison record or comparison command.
- Output contracts, renderer configuration, probing, preview frame alignment, schemas, and tests
  are fixed to 1920x1080 at 30 fps. Portrait is not a parameter switch today.
- Current analysis provides mix/stem RMS, drum onset, bass low energy, beat estimates, and chroma.
  It does not claim downbeats, bars, pitch tracks, semantic labels, or robust repeated-section
  structure.
- Chromium rendering is ready on this Mac but the measured backend is SwiftShader. The optional
  separation/alignment environments are installed; their model caches are currently absent.
- `../projects/README.md`, both case READMEs, and both `case.json` status blocks still describe the
  cases as not started. They are stale local-workspace ledgers and must not be treated as current
  production truth.

## Priority order

### P0 / S11 — restore a trustworthy baseline before feature work

1. **Refresh the external production ledgers.** Update the parent project index, both case status
   records, and their READMEs from the completed S10 evidence. Preserve private inputs and generated
   media outside Git. This is documentation/state repair, not a toolkit capability.
2. **Add a controlled same-audio variant comparison workflow.** Define a small comparison record
   and local template that bind the source hash, shared timeline/lyrics, each plan/assets/resolved
   plan, identical global preview ranges, renderer/environment identity, objective QA, and human
   feedback. Prove it first with existing A/B/C support and distinct output directories. Do not add
   another visual backend until this baseline can distinguish a backend improvement from a changed
   song, range, asset set, or typography treatment.

Acceptance: two variants of one song use the same canonical audio and preview ranges; neither
overwrites the other; manifests identify all differing inputs; a side-by-side/contact-sheet or
ordered review reel and a feedback record make the comparison auditable.

### P1 / S12 — highest-value core extensions

3. **Generalize output profiles, delivering portrait first.** Add a strictly validated
   1080x1920/30 profile while retaining 1920x1080/30. Make abstract framing, media fit/crop,
   particles, lyric safe areas, font sizing, transitions, preview alignment, output probing, cache
   identity, schemas, migrations, examples, capabilities, and tests profile-aware. Validate on the
   same audio/plan intent as a landscape control; do not claim automatic artistic reframing from a
   mechanical crop.
4. **Improve repeated-section structure before adding heavier models.** Extend the existing locked
   librosa path with beat-synchronous chroma/energy self-similarity and unlabeled repeated-section or
   boundary candidates, retaining confidence/provenance and manual overrides. Compare current
   energy-novelty routing with the new candidates on the same song and ranges. Only pursue downbeat,
   bar phase, melody/pitch, or learned semantic labels after this lower-dependency slice shows a
   concrete planning benefit.

Why these precede GUI work: they change authoritative artifacts and renderer behavior. A GUI built
first would either encode the old fixed profile or need immediate migration.

### P2 / S13 — automated Astrofox backend first

5. **Implement Astrofox as the first automated external visual provider.** Pin Astrofox commit
   `126403958e5644a6fbb91d6623626474dd199205` and add a tested downstream `astrofox-render`
   headless CLI. A hidden Electron renderer and programmatic bridge load the project, audio, assets
   and local hash-pinned plugins, then call Astrofox's deterministic per-frame renderer and FFmpeg
   pipe directly. Playwright, AppleScript and UI clicking are forbidden. The result is a silent CFR
   video plus a manifest binding the upstream/patch, project, plugin, assets, render parameters and
   output. The MVT adapter then adds canonical audio, lyrics, comparison records and final QA.
   Manual editor handoff remains a debugging/failure fallback; MCP waits until the CLI is stable.
6. **Limit projectM to a locked feasibility proof in S13.** Pin the core/provider/preset identities,
   feed canonical PCM and attempt a short silent-CFR result against the same provider contract.
   Record licensing, determinism and environment evidence. Do not advertise projectM as available;
   complete production integration is a separately authorized later slice.

Upstream evidence to refresh when either slice is selected:

- <https://github.com/projectM-visualizer/projectm>
- <https://github.com/projectM-visualizer/gst-projectm>
- <https://github.com/astrofox-io/astrofox>

### P3 — product surface and broader validation

7. **GUI/editor.** Build only after the artifact/profile/backend contracts it must edit are stable.
   Begin with project inspection, plan/section editing, preview launch, comparison review, and saved
   feedback; keep CLI artifacts authoritative. Do not start with a general nonlinear video editor.
8. **Linux/NVIDIA and hardware-render validation.** Add a locked host matrix and distinguish
   protocol equivalence from pixel tolerance. Keep the current software path as the reference.
9. **4K/60 profiles.** Reuse the generalized profile contract after portrait; measure memory,
   encoding time, typography, media decode, and WebGL limits before advertising support.
10. **Public release/publishing.** Release readiness is technically complete, but any push,
    packaging publication, or distribution of external presets/materials remains separately
    authorized.

## Confirmed sequence

Implement [S11](S11-variant-comparison.md), then [S12](S12-portrait-structure.md), then
[S13](S13-astrofox-backend.md). Each slice has its own acceptance evidence and commits. GUI,
complete projectM integration and MCP remain outside these three sessions.
