# S13 — Astrofox 自动化外部视觉后端

## Outcome

Deliver a fully automated, pinned Astrofox visual-provider path behind a renderer-neutral external
backend contract. MVT continues to own canonical audio, lyrics, comparison and final QA. Prove only
projectM feasibility; do not claim a complete projectM adapter.

## External-provider contract

- A typed provider request binds canonical source, output profile, global/full range, backend config
  and backend-specific project/material references. A completed provider manifest records backend
  name/version/commit, integration patch hash, project/plugin/asset/parameter hashes, environment,
  exact CFR media properties, output hash and structured failure provenance.
- Provider output is silent constant-frame-rate video. Media probing must reject an audio stream,
  wrong frame count/profile/rate, missing/tampered inputs and stale outputs.
- Setup/download/build is explicit and isolated. Rendering never fetches code, plugins, presets or
  assets. Capabilities and doctor distinguish not installed, installed, ready and proven.

## Astrofox headless contract

- Pin upstream commit `126403958e5644a6fbb91d6623626474dd199205`, its package lock and MIT
  license. Keep a small reviewable downstream patch stack and lock record; do not copy an untracked
  upstream checkout or build products into Git.
- Implement `astrofox-render` in the pinned source. Electron main parses an explicit job, creates a
  hidden renderer, exposes a narrow programmatic preload bridge, loads the JSON project plus local
  audio/assets/hash-pinned plugins, waits for readiness, invokes Astrofox's existing deterministic
  `renderer.renderFrame(frame, fps)`/`VideoExporter` FFmpeg path with audio disabled, emits one JSON
  result and exits cleanly.
- Playwright, AppleScript, accessibility APIs, keyboard/mouse automation and visible-window clicks
  are forbidden. Block network access during jobs. Arbitrary remote plugin URLs are forbidden.
- The CLI validates paths and hashes before render, reports progress separately from machine-readable
  final output, terminates child FFmpeg/plugin workers on failure/cancel, and never installs partial
  output or a completed manifest.
- Manual editor opening is documented only for debugging and recovery. It is not acceptance proof or
  the primary workflow. MCP is deferred until the CLI contract is stable.

## MVT integration contract

- The Python adapter invokes a configured built `astrofox-render`, validates its provider manifest
  and video, and never imports Astrofox application internals in-process.
- Wrap the silent video as a checked media asset and use existing MVT composition to add canonical
  audio, saved lyrics, optional native layers, S11 comparison records and objective final QA.
- External acceptance compares an Astrofox variant with a built-in MVT variant using the same
  `soft-harm` canonical audio, profile and global preview ranges. No private inputs or generated media
  enter Git.

## projectM feasibility boundary

Pin a projectM core/provider revision and one legally usable preset/texture set in an isolated local
environment. Attempt a short canonical-PCM-to-silent-CFR result conforming to the provider manifest;
record build, license, timing, determinism and global-time limitations. A success is feasibility
evidence only. A failure records the exact blocker. `mvt capabilities` must not list projectM as an
available backend in S13.

## Implementation stages

1. **External-provider protocol** — add request/manifest models, schemas, probe rules, a fake-provider
   conformance harness and failure semantics; depends on S12; check focused Python/schema tests.
2. **Pinned Astrofox environment** — add upstream lock/license metadata, explicit prepare/build/check
   scripts and hash-verified downstream patch application; depends on stage 1; check a clean external
   checkout/build without adding it to Git.
3. **Headless job controller** — patch Electron main/preload/renderer with hidden-window job loading,
   local-only project/assets/plugins, readiness and structured lifecycle; depends on stage 2; check
   non-render smoke, invalid input, plugin/hash and network-denial cases.
4. **Deterministic `astrofox-render` export** — call the existing frame/FFmpeg pipeline with audio
   disabled, produce the provider manifest, enforce atomic cleanup and prove exact CFR properties;
   depends on stage 3; check real short synthetic renders, repeat comparison and forced failure.
5. **MVT Astrofox adapter** — add doctor/capability gating and an adapter command that invokes the CLI
   and validates every identity without hidden downloads; depends on stages 1–4; check fake and real
   provider integrations.
6. **Canonical composition** — ingest provider video as a checked media layer and add canonical audio,
   saved lyrics and final QA through existing MVT paths; depends on stage 5; check a real synthetic
   captioned render and saved-artifact rerender.
7. **projectM feasibility report** — pin and exercise the smallest provider-compatible projectM path,
   recording success or the exact blocker without enabling capabilities; depends on stage 1, not on
   Astrofox completion; check lock/hash/license and any produced media evidence.
8. **Same-audio production proof** — compare Astrofox and built-in variants with S11 outside Git,
   update Skill/capabilities/docs/status with exact scope, and run all locked Python/Node/schema plus
   Astrofox integration checks; depends on stages 1–7.

Execution split the original eighth stage at its independently valid dependency boundary: commit
`f6f231c` adds the checked multi-range provider bundle needed for S11; the external same-audio
proof then ran outside Git. The ninth stage updated capability/docs and ran full locked and clean-checkout
validation. The tenth stage fixes independently reviewed output concurrency, render timeout and
ignored-build integrity defects, then repeats the final pinned integration and song comparison.

Each stage is one independently valid local commit. If a sound implementation cannot fit within ten
stages, stop and report the needed split rather than combining unrelated changes. Do not push.

## Acceptance

- A fresh explicit setup at the pinned commit produces a callable `astrofox-render`; rendering itself
  succeeds offline with no UI automation.
- Repeated same-environment jobs preserve exact timing and meet the documented encoded-pixel or hash
  reproducibility gate; the chosen gate and evidence are recorded honestly.
- Manifests bind all upstream, patch, project, plugin, asset, parameter and output identities.
- MVT produces a captioned, canonical-audio result and S11 comparison without treating Astrofox audio
  or UI state as authoritative.
- projectM remains unadvertised until a separately authorized full adapter slice passes equivalent
  production gates.

## Non-goals

No Astrofox GUI automation, remote plugins during render, MCP, full projectM adapter, GUI editor,
publication or remote push.
