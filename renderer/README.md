# Fixed-frame renderer

Current implementation: exact integer frame/sample mapping, typed Three.js abstract/media layers, deterministic media-frame selection, responsive saved imported/aligned/edited lyric layout, global-time multi-range previews, and the S10 deterministic sample-clock 3D bulge lyric surface with pearlescent lighting and transparent entry/exit trails. The Playwright host awaits media/font readiness, captures each global frame from Chromium, and writes PNG frames through a backpressure-aware FFmpeg pipe to either 1920x1080/30 or 1080x1920/30 H.264/AAC MP4.

From the toolkit root:

```bash
pnpm --dir renderer install --frozen-lockfile
pnpm --dir renderer exec playwright install chromium
pnpm --dir renderer check
```

Node >=22.12 is required; S02 verified Node 24.15.0, Playwright 1.63.0 and its pinned Chromium 153.0.8010.12. `check` builds the Node host and bundled browser scene, then runs Node tests. The generic rational clock accepts other frame rates for arithmetic verification, but v0.1 plans accept only the closed landscape and portrait tuples above. Do not claim arbitrary dimensions, 4K or 60 fps are supported.

`sampleAtFrame` floors a frame boundary to the canonical sample index. `firstFrameAtSample` rounds an event forward to its first displayable frame. Always pass the global song frame, including for excerpts. JSON protocol integers are limited to 2^53−1; intermediate arithmetic uses BigInt and detects overflow. Visual seconds are convenience values, not the authoritative clock.

The current browser scene retains the S02 fixture contract and executes S04 abstract, S05 media/hybrid and S06 lyric configurations, including the S10 artistic treatment for saved imported/aligned/edited cues. Camera framing, cover/contain crop, normalized media motion, particles and caption geometry are aspect-aware. Captions use half-open cue ownership, profile-specific bounded safe areas and a pinned embedded font. On the verified headless Mac run, Chromium reported ANGLE with SwiftShader software rendering; hardware acceleration remains unproven. Media and abstract layers share `VisualLayer`; hybrid mode has no separate engine. Landscape and portrait plans may share intent but remain independent variants; the renderer does not claim artistic reframing.
