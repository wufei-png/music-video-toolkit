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
