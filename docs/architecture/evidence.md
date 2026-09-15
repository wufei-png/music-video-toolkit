# Technical evidence and open risks

Checked 2026-09-15. Research report remains in the parent production workspace; its recommendations are background, not an executable API contract. This document makes the repository self-contained without redistributing that report.

## Inspected upstream evidence

- [Astrofox source, revision 126403958e5644a6fbb91d6623626474dd199205](https://github.com/astrofox-io/astrofox/tree/126403958e5644a6fbb91d6623626474dd199205): `docs/plugin-authoring.md` specifies frame time/delta/seed; `docs/desktop-capabilities.md` and `src/lib/video/VideoExporter.ts` use Electron FFmpeg bridge. Inspected docs/scripts did not supply a standalone render CLI. We chose an independent small renderer; this is not a claim that integration is impossible.
- [Three.js documentation](https://threejs.org/docs/): rendering library, not an entire deterministic batch video application. Frame host, readiness barriers, resource lifetime and encoding integration remain our work, proven in S02.
- [python-audio-separator](https://github.com/nomadkaraoke/python-audio-separator): S03 locked 0.44.2 with `htdemucs.yaml`. Two local 20-second excerpts completed on Apple Silicon MPS/CoreML in 8.14 s / 7.34 s wall time with about 1.07 GB / 1.13 GB maximum resident set size. Four-file export, hashes, 48kHz alignment and timeline response passed; the user accepted both four-track listening checks on 2026-09-15. The upstream repository does not confirm a license for downloaded weights, so the model is local-only and marked non-redistributable.
- [WhisperX](https://github.com/m-bain/whisperX): README documents CPU/int8 use on macOS and language-specific forced alignment. That supports an integration candidate, not a guarantee for singing. S07 must verify known lyrics and repeated choruses on both cases.
- [stable-ts](https://github.com/jianfch/stable-ts): inspected page reports archive on 2026-05-30 and paused development; do not introduce it as a maintained default without new evidence.

## Risk gates

| Risk | First proof | If proof fails |
| --- | --- | --- |
| macOS frame capture/Chinese font/media/export | S02 short clip passed with pinned Chromium and software SwiftShader; hardware acceleration remains unproven | Prove hardware path when performance requires it; keep exact-frame software path as reference |
| 4-stem model memory/quality | S03 integration/memory passed; user accepted both listening checks | Change model/adapter configuration and record comparison if later song evidence regresses; no fake stems |
| Misleading beat/downbeat or sections | S03/S04 | Preserve unknowns and manual correction |
| External video exact-frame seeking | S05 passed with a 6-frame, 2 fps known-color video | FFmpeg decoded numbered PNGs; sample-clock trim/offset/loop/hold selected expected colors and excluded the video's 880 Hz audio |
| Singing alignment | S07 repeated chorus + sparse vocal spans | Improve/chosen alternate adapter; keep auto requirement open rather than silently downgrade to import-only |
| Excerpt differs from full render | S08 | Global clock and pre-roll/seek state regression |
| Visual quality | S09/S10 reviewed samples | Generalize a demonstrated tool limitation; keep song taste in configurations |

Observed host: Apple Silicon arm64, macOS 15.7.3, 24 GiB memory; uv, Node, pnpm and FFmpeg present. These are observations, not minimum supported versions. S03 downloaded the selected model into the external local workspace and recorded its hashes; no model or generated audio is stored in this repository.
