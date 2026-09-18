# S11 — 同音频方案比较基线

## Outcome

Deliver a typed, reproducible comparison workflow for completed MVT previews before adding new
profiles or visual backends. A comparison proves which inputs are shared and which differ; it does
not render variants implicitly or treat objective media checks as subjective approval.

Also repair the stale external production ledgers whose current text still says the completed S10
cases have not started. Private inputs, plans, reviews and generated media remain outside Git.

## Confirmed contract

- Add authoritative Python `ComparisonRequest` and `ComparisonManifest` models, generated schemas,
  validation support and synthetic examples. A request contains ordered stable variant IDs, labels
  and completed preview-manifest paths.
- `mvt compare --request FILE --output DIR` consumes existing preview outputs. It never invokes
  analysis, alignment, plan resolution or rendering.
- Every variant must have the same canonical source hash, ordered global sample ranges, actual
  probed width/height/fps, range count and audio presence. Variant plan/assets/renderer/input hashes
  are expected to differ and are recorded, not normalized away.
- The command validates every referenced hash and media file, probes the clips, and installs a new
  output directory atomically. An intact identical request may reuse its cache; stale, partial or
  damaged output fails without overwrite.
- The comparison directory contains `comparison.json`, an FFmpeg stream-copy review reel ordered
  range-major then variant-major, and a labeled contact sheet sampled at the same relative frame in
  each range. The manifest binds the request, input manifests, generated artifacts, tool versions
  and hashes. Subjective feedback is a separate external record.
- Repository tests use synthetic A/B/C variants. External acceptance uses `soft-harm`, shared
  canonical audio/timeline/lyrics and identical sparse/transition/climax ranges. It must not add the
  song, generated media or private reviews to Git.
- Update `../projects/README.md`, both case READMEs and both `case.json` status blocks from actual S10
  evidence. These external edits are verified but cannot be committed in this repository.

## Implementation stages

1. **Comparison contracts** — add models, schemas, examples and semantic validation; depends on
   S10; check with focused contract tests and `scripts/export_schemas.py --check`.
2. **Comparison command** — validate completed preview manifests/media, shared invariants, cache and
   atomic output behavior; depends on stage 1; check with synthetic success, mismatch, tamper and
   conflict tests.
3. **Review artifacts** — produce deterministic range-major review reel and labeled contact sheet,
   bind their hashes, and prove no upstream pipeline command runs; depends on stage 2; check with a
   real FFmpeg synthetic A/B/C integration.
4. **Production proof and handoff** — run the same-range `soft-harm` comparison outside Git, repair
   the external ledgers, update capabilities/docs/status with exact evidence, and run all locked
   Python/Node/schema checks; depends on stages 1–3.

Each repository stage is one independently valid local commit. Stage 4 commits only repository
documentation/tests; external workspace edits remain uncommitted by this Git repository. Do not
push.

## Acceptance

- Reordering a variant intentionally changes the comparison identity and reel ordering.
- Any source/range/profile/audio/hash mismatch is a structured failure before output installation.
- Two valid variants never overwrite one another or their original previews.
- Cached reuse revalidates every input and output hash.
- The external comparison record makes it possible to distinguish plan/backend changes from changed
  audio, ranges, typography or renderer versions.

## Non-goals

No portrait support, new analyzer, Astrofox/projectM execution, GUI, model call, subjective winner
selection, publication or remote push.
