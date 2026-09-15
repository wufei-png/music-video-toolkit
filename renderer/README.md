# Renderer skeleton

Current implementation: exact integer frame/sample mapping, typed Three.js layer/frame interfaces, and the S02 Playwright capture host. The host awaits image/font readiness, captures each global frame from Chromium, and writes PNG frames through a backpressure-aware FFmpeg pipe to 1080p30 H.264/AAC MP4. Production visual layers arrive in S04/S05.

From the toolkit root:

```bash
pnpm --dir renderer install --frozen-lockfile
pnpm --dir renderer exec playwright install chromium
pnpm --dir renderer check
```

Node >=22.12 is required; S02 verified Node 24.15.0, Playwright 1.63.0 and its pinned Chromium 153.0.8010.12. `check` builds the Node host and bundled browser scene, then runs Node tests. The generic rational clock accepts other frame rates for arithmetic verification, but v0.1 plans accept only 1080p30. Do not claim other render profiles are supported.

`sampleAtFrame` floors a frame boundary to the canonical sample index. `firstFrameAtSample` rounds an event forward to its first displayable frame. Always pass the global song frame, including for excerpts. JSON protocol integers are limited to 2^53−1; intermediate arithmetic uses BigInt and detects overflow. Visual seconds are convenience values, not the authoritative clock.

The current browser scene deliberately supports only the `s02.pulse`, `s02.image` and `s02.text` fixture contract. On the verified headless Mac run, Chromium reported ANGLE with SwiftShader software rendering; hardware acceleration is unproven. S04 resolves named signals/events and adds production abstract layers. S05 adds production media behavior. Media and abstract layers continue to share `VisualLayer`; there is no independent hybrid engine.
