# S12 — 竖屏输出与重复结构分析

## Outcome

Add one closed portrait profile and an optional, reviewable repeated-structure analysis path. Both
must use S11 comparison evidence and preserve the existing landscape and manual-section behavior.

## Confirmed output-profile contract

- Supported tuples are exactly 1920x1080/30 and 1080x1920/30. Keep the rational frame clock at
  30/1; arbitrary sizes, 4K and 60 fps remain unsupported.
- Widening the accepted tuple is backward-compatible for existing v0.1 plans. Regenerate schemas and
  document the change; do not add a required field solely to rename existing profiles.
- Remove renderer-side hard-coded dimensions. Plan resolution, render configuration, probing,
  cache identity, manifests, preview validation and review artifacts use the plan's validated output
  tuple.
- Abstract composition, media cover/contain, motion, transition buffers, particles and lyric layout
  are aspect-aware. Portrait lyrics use explicit responsive safe areas and remain legible at opening,
  dense, repeated, transition and tail passages.
- Landscape and portrait are separate plan variants sharing semantic intent and audio artifacts.
  Mechanical crop/scale is not claimed as automatic artistic reframing.

## Confirmed structure contract

- Add a separate typed `structure.json`; do not mutate `timeline.json` during analysis. The first
  backend uses locked librosa and existing mix RMS/chroma/beat evidence—no downloaded model.
- Beat-synchronize chroma and energy, compute self-similarity/novelty and expose ordered boundary
  candidates plus repeated-span group IDs, confidence and full parameter/provenance identity.
  Results remain unlabeled; do not infer verse, chorus, bar phase, downbeat or melody.
- `mvt structure analyze` creates or reuses the analysis artifact. `mvt structure apply` requires an
  explicit reviewed selection and writes a separate enriched timeline path. It never overwrites the
  base timeline or silently changes a plan.
- Automatic selected boundaries retain automatic provenance. User-adjusted samples or labels are
  manual provenance. Applying to a timeline that already has sections requires an explicit replace
  policy and preserves the original file.
- Compare original RMS-novelty candidates, new repetition candidates and the existing manual S10
  boundaries on the same `soft-harm` audio/ranges. Boundary proximity is evidence, not semantic
  correctness or user approval.

## Implementation stages

1. **Closed portrait profile** — widen `OutputProfile`, generated schemas and compatibility tests to
   the two exact tuples; depends on S11; check schema generation plus rejection of every unsupported
   tuple.
2. **Profile-driven renderer** — carry dimensions through Python/Node configuration, FFmpeg, probe,
   manifests, cache and previews while preserving landscape output; depends on stage 1; check with
   real synthetic landscape regression and portrait encode.
3. **Aspect-aware composition** — adapt abstract/media/lyric layout and add portrait visual/safe-area
   acceptance; depends on stage 2; check frame samples, contact sheets and renderer tests.
4. **Structure artifact and analysis** — add authoritative models/schema plus deterministic
   beat-synchronous repetition analysis and cache/provenance; depends on S11 only; check synthetic
   repeated-form, silence, sparse-beat and cache/tamper tests.
5. **Explicit structure application** — add reviewed selection and non-overwriting enriched-timeline
   output with provenance rules; depends on stage 4; check apply/reapply/conflict/existing-section
   cases and plan resolution from the new timeline.
6. **Same-audio acceptance** — use S11 to compare landscape/portrait intent and old/new structure
   routing outside Git, inspect the required lyric passages, then update capabilities/docs/status and
   run all locked Python/Node/schema checks; depends on stages 1–5.

Each stage is one independently valid local commit. Do not push.

## Acceptance

- Existing 1920x1080 plans and tests remain valid without migration edits.
- A 1080x1920 full/preview render has correct codecs, exact frame count, global-time equivalence,
  non-black composition and legible safe-area lyrics.
- Structure analysis is reproducible, hash-bound and honest about unknown semantics.
- No structure result affects rendering until an explicit selection is applied and a plan references
  the resulting timeline.

## Non-goals

No arbitrary resolution/fps, auto-reframing promise, downbeat/bar/pitch model, learned semantic
labels, GUI, external visual backend, publication or remote push.
