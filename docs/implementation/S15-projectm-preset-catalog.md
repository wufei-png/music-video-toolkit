# S15 — approved projectM preset catalog

## Decision and dependency

Depends on completed S14 and the 2026-09-21 two-visual study. The user accepted
both original candidate visuals for this toolkit and prefers soft flow for
`soft-harm`; beat petals may suit a different song. The checked petals catalog
file drops its low-opacity outline because line smoothing made synthetic repeated
exports differ; the filled shape remains. Keep the existing `mvt-wave`
entry for compatibility, while retaining its `soft-harm` rejection in the
external song record. This slice adds exactly two approved hashes, not arbitrary
Milkdrop preset loading or automatic style selection.

## Implementation boundary

- Make the pinned projectM lock carry one authoritative ID-to-SHA-256 catalog for
  `mvt-wave`, `study-soft-flow`, and `study-beat-petals`. Requests still name
  exactly one preset via `{"preset_id":ID,"policy":"locked-single"}` and provide
  the single matching local preset asset/project. Reject unknown IDs, mismatched
  hashes, extra assets/plugins or other parameters.
- Include the approved catalog in the backend integration identity. Old S14
  requests/results remain historical; callers must issue new requests against
  the new identity. Python protocol schemas do not change.
- Expose the three IDs in `mvt capabilities`, the production Skill, README and
  integration guidance. Do not claim a preset is suitable for every song.
- Parameterize synthetic and same-song acceptance helpers so each selected
  preset can use the unchanged global-time, profile, composition, audio and
  comparison contracts. The checked overlay workflow for the approved presets
  must run through `mvt provider projectm`, not bypass its allowlist.
- Keep all actual song media, requests, manifests, contact sheets, feedback and
  QA outside Git. Do not render a full song in this slice.

## Acceptance

For each new preset, prove same-host repeated MP4 bytes, bounded raw full/excerpt
global-frame channel drift (at most two 8-bit levels and 0.01% of channels),
both closed output profiles, valid silent-CFR provider results,
saved-artifact composition and S11 comparison on public synthetic input. Prove
the production adapter on the three existing `soft-harm` review ranges and
compare its checked overlays with the accepted C control. Inspect contact
sheets for visible effects and captions; record that the user's style decision
is for these candidates and this song only. Run locked Python/Node and schema
checks, stage explicit paths, inspect staged diffs, then commit locally.

## Next action after S15

Select a future full-song or cross-song production request separately. For
`soft-harm`, use the accepted soft-flow preference only after a checked full
composition plan and the normal song workspace approval record; never infer
full-song export authorization from preset inclusion.
