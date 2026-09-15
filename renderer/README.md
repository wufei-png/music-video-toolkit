# Renderer skeleton

Current implementation: exact integer frame/sample mapping and typed Three.js layer/frame interfaces. **No WebGL host, visual layer implementation, capture loop or encoder exists yet.** See S02 and S04/S05 in the implementation plan.

From the toolkit root:

```bash
pnpm --dir renderer install --frozen-lockfile
pnpm --dir renderer check
```

Node >=22.12 is required; bootstrap verified on Node 24.15.0. `check` builds TypeScript and runs Node tests. The generic rational clock accepts other frame rates for arithmetic verification, but v0.1 production plans accept only 1080p30. Do not claim other render profiles are supported.

`sampleAtFrame` floors a frame boundary to the canonical sample index. `firstFrameAtSample` rounds an event forward to its first displayable frame. Always pass the global song frame, including for excerpts. JSON protocol integers are limited to 2^53−1; intermediate arithmetic uses BigInt and detects overflow. Visual seconds are convenience values, not the authoritative clock.

S02 implements the frame host and rendering adapter; S04 resolves named signals/events into `RoutedFrame` and applies registered layer parameters. Media and abstract layers share `VisualLayer`; no independent hybrid engine. `FrameRenderer.render` will return raw RGBA bytes with fixed size supplied by the future host contract, and must await media/font readiness.
