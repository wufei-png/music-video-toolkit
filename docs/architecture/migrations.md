# Contract migration notes

The repository is still on the `0.1` bootstrap contract. These dated revisions record fields that became mandatory when their execution slice shipped. Regenerate derived artifacts with the current CLI instead of editing hashes by hand.

## 2026-09-15 — S05 resolved media plans

Resolved plans created before S05 lack `assets_sha256`, `checked_assets_path` and `checked_assets_sha256`. Run `mvt assets check`, then rerun `mvt plan resolve`. Editable visual plans and asset manifests do not need a structural migration.

## 2026-09-15 — S06 imported lyrics

Imported `lyrics.json` now records `text_source_sha256` and import `provenance`; rerun `mvt lyrics import` from the original UTF-8 LRC/SRT file. The importer refuses to overwrite an existing edited artifact, so choose a new output and reconcile edits explicitly.

Enabled plan lyrics now require `font_asset_id`, referring to a font in `assets.json`. Resolved plans also bind `lyrics_sha256`. Add the font asset and license/source note, run `mvt assets check`, then rerun `mvt plan resolve`. Off-mode plans need no lyric or font fields.

## 2026-09-16 — S07 automatic alignment

The new `alignment` report schema records known-text line matches, exact runtime/model provenance and optional fixed-threshold reference metrics. Existing imported lyric artifacts do not change. Automatic output uses origin `aligned`; save a complete reviewed onset document with `mvt lyrics apply-edits` to create a separate origin `edited` artifact, including manual starts for every unmatched line.
