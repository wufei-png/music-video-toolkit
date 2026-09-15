# Technical evidence and open risks

Checked 2026-09-15. Research report remains in the parent production workspace; its recommendations are background, not an executable API contract. This document makes the repository self-contained without redistributing that report.

## Inspected upstream evidence

- [Astrofox source, revision 126403958e5644a6fbb91d6623626474dd199205](https://github.com/astrofox-io/astrofox/tree/126403958e5644a6fbb91d6623626474dd199205): `docs/plugin-authoring.md` specifies frame time/delta/seed; `docs/desktop-capabilities.md` and `src/lib/video/VideoExporter.ts` use Electron FFmpeg bridge. Inspected docs/scripts did not supply a standalone render CLI. We chose an independent small renderer; this is not a claim that integration is impossible.
- [Three.js documentation](https://threejs.org/docs/): rendering library, not an entire deterministic batch video application. Frame host, readiness barriers, resource lifetime and encoding integration remain our work, proven in S02.
- [python-audio-separator](https://github.com/nomadkaraoke/python-audio-separator): candidate adapter for 4-stem separation. Actual macOS model/device speed, installation and stem quality are untested here.
- [WhisperX](https://github.com/m-bain/whisperX): README documents CPU/int8 use on macOS and language-specific forced alignment. That supports an integration candidate, not a guarantee for singing. S07 must verify known lyrics and repeated choruses on both cases.
- [stable-ts](https://github.com/jianfch/stable-ts): inspected page reports archive on 2026-05-30 and paused development; do not introduce it as a maintained default without new evidence.

## Risk gates

| Risk | First proof | If proof fails |
| --- | --- | --- |
| macOS frame capture/Chinese font/media/export | S02 short clip | Fix host/capture boundary before scene investment |
| 4-stem model memory/quality | S03 excerpts from both songs | Change model/adapter configuration and record comparison; no fake stems |
| Misleading beat/downbeat or sections | S03/S04 | Preserve unknowns and manual correction |
| External video exact-frame seeking | S05 short known-frame video | Decode deterministic frames through FFmpeg, not wall-clock playback |
| Singing alignment | S07 repeated chorus + sparse vocal spans | Improve/chosen alternate adapter; keep auto requirement open rather than silently downgrade to import-only |
| Excerpt differs from full render | S08 | Global clock and pre-roll/seek state regression |
| Visual quality | S09/S10 reviewed samples | Generalize a demonstrated tool limitation; keep song taste in configurations |

Observed bootstrap host: Apple Silicon arm64, macOS 15.7.3, 24 GiB memory; uv, Node, pnpm and FFmpeg present. These are observations, not minimum supported versions or integration results. Lock dependency versions in each implementing stage and report actual resource/time measurements. No model weights downloaded during planning.
