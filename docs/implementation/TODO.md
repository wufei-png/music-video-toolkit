# Post-S10 backlog — 2026-09-19

This is the local, evidence-ordered backlog after S01–S10. On 2026-09-19 the user selected P0, P1
and P2 in order; their confirmed implementation contracts are S11, S12 and S13. S11 and S12 are
now complete; selection alone still does not make S13 an implemented capability. Work on only
the first dependency-ready unfinished slice.

## Current baseline

- This audit began from clean `main` at `ea614da`; S01–S12 are complete. `mvt capabilities` reports CLI and
  production stage `s12`, with closed 1920x1080/30 and 1080x1920/30 rendering, completed-preview
  comparison and explicit review/apply structure analysis.
- The two external production finals and their QA evidence exist under
  `../projects/soft-harm/s10/final-v1-bulge/` and
  `../projects/zhi-mai-yi-ren-fen/s10/final-v1-bulge/`. Both have exact expected frame counts,
  H.264 video, AAC 48 kHz stereo audio, and no detected black interval.
- The repository supports A abstract, B mood-media, and C hybrid plans. `mvt compare` now validates
  distinct completed aggregate variants against one canonical audio, exact global ranges, H.264/
  yuv420p + AAC 48 kHz stereo CFR compatibility, frame/audio evidence and hashes, then re-probes
  and installs an auditable manifest, range-major reel and labeled contact sheet without running
  upstream pipeline commands.
- Output contracts, renderer configuration, probing, preview frame alignment, schemas, and tests
  accept only the two S12 30 fps tuples. Portrait remains a separate plan variant rather than an
  automatic artistic reframe.
- Current analysis provides mix/stem RMS, drum onset, bass low energy, beat estimates, chroma and
  deterministic beat-synchronous novelty/repetition candidates. It does not claim downbeats, bars,
  pitch tracks, melody or semantic labels; applying candidates requires an explicit reviewed selection.
- Chromium rendering is ready on this Mac but the measured backend is SwiftShader. The optional
  separation/alignment environments are installed; their model caches are currently absent.
- `../projects/README.md`, both case READMEs, and both `case.json` status blocks were refreshed from
  S10 evidence. External `soft-harm/s11/` and `soft-harm/s12/` records contain the S11 and S12
  acceptance evidence.

## Priority order

### P0 / S11 — complete

1. **Completed: external production ledgers refreshed.** The parent project index, both case status
   records and both READMEs now use completed S10 evidence. Private inputs and generated media remain
   outside Git; this is documentation/state repair, not a toolkit capability.
2. **Completed: controlled same-audio variant comparison workflow.** The comparison record binds
   source identity, ranges, probes, audio, hashes, plan/assets/renderer differences and generated
   review artifacts. Public A/B/C fixtures and the external `soft-harm` proof use distinct preview
   directories and preserve subjective feedback outside the manifest.

Acceptance: two variants of one song use the same canonical audio and preview ranges; neither
overwrites the other; manifests identify all differing inputs; a side-by-side/contact-sheet or
ordered review reel and a feedback record make the comparison auditable.

### P1 / S12 — complete

3. **Completed: generalize output profiles, delivering portrait first.** Added a strictly validated
   1080x1920/30 profile while retaining 1920x1080/30. Make abstract framing, media fit/crop,
   particles, lyric safe areas, font sizing, transitions, preview alignment, output probing, cache
   identity, schemas, migrations, examples, capabilities, and tests profile-aware. Validate on the
   same audio/plan intent as a landscape control; do not claim automatic artistic reframing from a
   mechanical crop.
4. **Completed: improve repeated-section structure before adding heavier models.** Extended the locked
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

S12 is complete. Implement [S13](S13-astrofox-backend.md) next. Each slice has its own acceptance
evidence and commits. GUI, complete projectM integration and MCP remain outside these three sessions.
