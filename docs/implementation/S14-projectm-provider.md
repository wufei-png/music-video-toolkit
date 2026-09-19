# S14 — bounded projectM production provider

## Outcome and dependency

Depends on S13. Deliver an offline projectM adapter for a small, hash-checked set of
self-authored or explicitly licensed presets. Each provider job locks one preset. MVT
continues to own canonical audio, captions, comparison and final QA. The S13 six-frame
probe is feasibility evidence only: its repeated videos differed, and it did not test
nonzero global time.

The retained S13 results each contain six decoded frames. `ffmpeg -f framemd5`
found a different decoded hash at every corresponding frame, and decoded-video
PSNR averaged 48.15 dB. The two manifest video SHA-256 values are recorded in
[`integrations/projectm/README.md`](../../integrations/projectm/README.md).
At the pinned revision, `projectm_set_frame_time` accepts explicit seconds, but
`PresetState` seeds hue offsets from `std::random_device` and `MilkdropNoise`
uses the system clock. These are candidate causes, not yet an isolated diagnosis.

## Execution contract

- Retain the pinned libprojectM 4.2.0 revision, evaluation submodule and LGPL license.
  Build and patch the library in an explicit external checkout. Record patch, source,
  preset, texture, build and runtime hashes; never fetch material during rendering.
- Diagnose repeat differences at decoded-frame level. Seed or remove randomness on the
  supported path with a reviewable downstream patch. Lock the current preset so an
  unattended job never changes style. Do not advertise arbitrary `.milk` support.
- Read the checked canonical 48 kHz stereo PCM and advance projectM from frame zero to
  the requested end frame, feeding the corresponding 1600 samples per 30 fps frame.
  Capture only the requested half-open, frame-aligned global range. No independent
  excerpt clock or approximate seek is allowed. Measure the cost of pre-roll.
- Accept only the two existing output profiles. Produce an atomic, silent H.264/yuv420p
  CFR video and the existing provider manifest. Fail on incorrect frame count, profile,
  timing, hashes, unapproved preset/texture, stale output or partial job.
- Run projectM behind an external process boundary. The MVT adapter verifies the result;
  existing `provider compose`, `provider bundle` and `compare` paths then add canonical
  audio and optional saved lyrics and compare the completed variant with built-in MVT.
- Keep external song audio, plans, provider data, media and feedback outside Git.

## Dependency-ordered stages

1. **Contract and diagnostic baseline** — record this selected scope, decoded repeat
   differences and the local source/API evidence; check docs and diagnostic commands.
2. **Pinned deterministic runtime** — add a reviewable seeded patch and explicit external
   prepare/build/check flow; check pinned source, build identity and repeated raw frames.
3. **Offline provider CLI** — implement one-preset jobs, bounded profiles, global pre-roll,
   silent CFR export, manifest and atomic failure behavior; check real synthetic jobs.
4. **MVT process adapter** — add doctor and a request/manifest-validating command while
   leaving projectM unavailable in production capabilities; check fake/real failure paths.
5. **Reproduction and composition** — prove repeat output, full-versus-excerpt frame
   identity, nonzero global time, both profiles, canonical audio, captions and S11
   compatibility on synthetic inputs; check the focused and locked suites.
6. **External same-audio proof and handoff** — compare a projectM variant with a built-in
   variant on the same `soft-harm` canonical audio and ranges outside Git. Record objective
   QA and runtime, update capability/Skill/status only for the proven scope, and run all
   final locked checks.

Each stage leaves a valid repository and is one local commit. If a reproduction gate
fails, retain projectM as unavailable and document the blocker. Do not push.

## Acceptance boundary

Repeated jobs in the same locked environment have identical video bytes for the
approved preset. Pre-encode raw RGBA excerpt frames equal the corresponding frames
of a full run. Separately encoded H.264 clips may differ at the decoded-pixel level
because their prediction context differs; the synthetic full/excerpt check requires
at least 48 dB PSNR. The provider result passes the shared silent-CFR contract;
composed previews pass canonical audio, caption and S11 comparison checks.
Cross-host pixel identity, arbitrary preset packs, automated preset transitions,
GUI and publication are outside this slice.
