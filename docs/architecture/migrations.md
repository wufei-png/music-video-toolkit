# Contract migration notes

The repository is still on the `0.1` bootstrap contract. These dated revisions record fields that became mandatory when their execution slice shipped. Regenerate derived artifacts with the current CLI instead of editing hashes by hand.

## 2026-09-15 — S05 resolved media plans

Resolved plans created before S05 lack `assets_sha256`, `checked_assets_path` and `checked_assets_sha256`. Run `mvt assets check`, then rerun `mvt plan resolve`. Editable visual plans and asset manifests do not need a structural migration.

## 2026-09-15 — S06 imported lyrics

Imported `lyrics.json` now records `text_source_sha256` and import `provenance`; rerun `mvt lyrics import` from the original UTF-8 LRC/SRT file. The importer refuses to overwrite an existing edited artifact, so choose a new output and reconcile edits explicitly.

Enabled plan lyrics now require `font_asset_id`, referring to a font in `assets.json`. Resolved plans also bind `lyrics_sha256`. Add the font asset and license/source note, run `mvt assets check`, then rerun `mvt plan resolve`. Off-mode plans need no lyric or font fields.

## 2026-09-16 — S07 automatic alignment

The new `alignment` report schema records known-text line matches, exact runtime/model provenance and optional fixed-threshold reference metrics. Existing imported lyric artifacts do not change. Automatic output uses origin `aligned`; save a complete reviewed onset document with `mvt lyrics apply-edits` to create a separate origin `edited` artifact, including manual starts for every unmatched line.

## 2026-09-16 — S08 preview cache identity

Render manifests now require `cache_key`. Old completed manifests remain evidence for their original run but cannot be reused as S08 cache entries. Rerun `mvt render` or `mvt preview` from the saved plan and material inputs to create a current manifest; do not add a guessed key by hand.

The new `preview` request records ordered, non-overlapping global sample ranges. Executable endpoints must be multiples of 1600 samples for 30 fps output. Existing full-song plans, lyrics and manual sections need no structural migration.

## 2026-09-19 — S11 comparison source identity

New render and preview manifests record `canonical_audio_sha256`. The field is optional at schema level so completed S08–S10 records remain valid historical evidence, but `mvt compare` requires it because the older `source_sha256` field identifies the original input rather than the canonical WAV. Rerun `mvt preview` from saved artifacts to produce a directly comparable manifest; do not guess or copy a canonical hash from an unrelated project.

S11 adds `comparison-request` and `comparison` artifacts. Comparison consumes completed previews only. There is no migration from a single preview: create a request that points to at least two intact variant manifests using identical ranges, then run `mvt compare --request FILE --output DIR`. Subjective review notes remain separate and are not migrated into `comparison.json`.

The post-implementation S11 review made comparison probes stricter. New `comparison.json` records require H.264/yuv420p and AAC 48 kHz stereo codec fields, average frame rate and a stream-compatibility hash; standalone validation also derives each expected frame count from its sample range. Earlier S11 comparison manifests remain historical evidence but no longer satisfy the current schema. Preserve any review notes, then rerun `mvt compare` from intact aggregate previews. Full-render manifests and hand-authored render manifests without `preview_request` plus `preview_adapter` input evidence are intentionally rejected, as are two request paths that resolve to the same preview.

## 2026-09-19 — S12 closed output profiles and structure artifacts

Editable and resolved plans now accept exactly `1920x1080/30` or `1080x1920/30`. Existing editable plans that omit `output` remain landscape and require no edit. Regenerate resolved plans so the selected profile is explicit, and rerun render/preview so cache identities and manifests bind it. Existing landscape evidence remains structurally valid; it is not upgraded into portrait evidence. Arbitrary dimensions, 4K and 60 fps have no migration because they are unsupported.

S12 adds generated `structure` and `structure-selection` schemas. There is no implicit migration from the legacy RMS novelty fallback or from existing manual sections. Run `mvt structure analyze` against an intact analysis timeline, review candidates into a separate selection, choose `require-empty` or `replace` explicitly, then run `mvt structure apply` to a new timeline path. Preserve the base timeline. Adjusted edges and labels are manual decisions; do not copy automatic confidence to them.

Comparison remains a same-profile operation. Use separate comparison requests for landscape and portrait previews, even when their plans share intent and ranges; mixed dimensions are deliberately rejected rather than reframed or transcoded.

## 2026-09-19 — S13 external visual-provider artifacts

S13 adds `provider-request` and `provider-manifest` schemas without changing existing source, timeline, plan, lyric or preview models. Old manual Astrofox exports and unbound videos are not provider results: create a current typed request, render with the pinned downstream CLI, and keep its completed manifest and video together. Do not fill missing hashes from guesses or rename an old video into a completed result. The conformance check rejects audio-bearing media, non-CFR or incorrect clocks, stale or tampered inputs, and incomplete results.

For S11 comparison, first use `mvt provider compose` for each range to add the same canonical audio and optional saved lyrics through MVT. Use `mvt provider bundle` to construct a completed aggregate preview from ordered compositions, then point an ordinary comparison request at that manifest and a distinct built-in preview manifest. Prior S11/S12 artifacts remain valid if they already pass current comparison preflight. The S13 projectM feasibility result is historical and cannot be reused as an S14 production result.

The post-review Astrofox patch stack has a new hash because output locking and the readiness timer were corrected. Earlier S13 provider videos remain historical evidence; the current adapter refuses requests carrying the old patch identity. Prepare and build a fresh external checkout, update the request backend patch hash from `integrations/astrofox/lock.json`, and rerender into a new output directory. Doctor also requires a current build hash record for `out/` and `node_modules`; run explicit `build` after changing either tree.

## 2026-09-19 — S14 bounded projectM provider

S14 uses the existing `provider-request` and `provider-manifest` schemas, so there is no protocol
version migration. A production request must select the pinned projectM revision and current
integration patch identity, contain only the approved `mvt-wave` preset with its hash, and use
exactly `{"preset_id":"mvt-wave","policy":"locked-single"}` parameters. Recreate requests from
the checked canonical WAV and current runtime; do not relabel S13 feasibility files or reuse an
old result after changing the preset, patch or binary. Composition, bundle and comparison use
the same S13 artifacts and paths. Existing Astrofox and built-in results remain valid if they
pass their current checks.

## 2026-09-21 — S15 projectM preset catalog

S15 retains the `0.1` provider schemas and `locked-single` request shape. The
approved ID-to-SHA-256 catalog now includes `mvt-wave`, `study-soft-flow`, and
`study-beat-petals`. The integration identity additionally binds canonical
sorted JSON of the catalog, so pre-S15 projectM requests and provider results
remain historical even for `mvt-wave`. Recreate each request from the checked
canonical WAV, current `integration_identity()`, one matching preset project
and asset, and exact `{"preset_id":"ID","policy":"locked-single"}` parameters.
Render to a fresh directory, then recompute composition, bundle and comparison
artifacts. Preserve older visual reviews as dated evidence; do not edit their
identity fields or treat them as current production results. Astrofox and
built-in requests are unaffected.
