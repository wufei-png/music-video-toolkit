# Production artifacts and feedback

Keep a production brief, source inventory, canonical audio/analysis, asset manifest, editable visual plan, lyrics if enabled, preview ranges, review notes and render manifests together in the external production directory. Generated outputs and model caches are not source-controlled toolkit files.

## Useful production sequence

1. Inventory files, verify source identity and available tooling. Capture requested mode, lyrics policy, review mode and output profile.
2. Decode/analyze with supported commands. Keep canonical time and provenance; distinguish automatic proposals from manual section/lyric corrections.
3. Prepare a coherent material brief. When generating through the harness, retain prompt/settings and actual local result path where available. Replace assets through stable IDs and update hashes.
4. Create whole-song defaults and selected section overrides. Validate structure, cross-file identities, asset readiness, fonts and render support before a long run.
5. Choose excerpts using musical evidence: sparse, peak and a transition with context on both sides. Preserve global song time for each excerpt. If excerpts overlap, avoid counting duplicate seconds toward the intended review coverage.
6. In sample-approval mode, present the clips and collect specific feedback. Record approvals against plan/material hashes. In autonomous mode, record self-review honestly; do not label it user approval.
7. Render the full song from resolved artifacts. Check duration, resolution/fps, A/V endpoints, lyrics, clipping, transitions and resource failures. Report limitations distinctly from success.

## Current command sequence

Run from the toolkit's locked environment, or use an installed `mvt` executable:

```text
mvt capabilities
mvt doctor
mvt decode INPUT --project PROJECT
mvt analyze --project PROJECT --stems four|none
# optional structure proposal, then only after explicit review:
mvt structure analyze --project PROJECT --timeline TIMELINE.json --output STRUCTURE.json
mvt structure apply --project PROJECT --selection STRUCTURE-SELECTION.json --output TIMELINE-ENRICHED.json
mvt assets check --project PROJECT
mvt lyrics import FILE --project PROJECT --language TAG
# or: mvt lyrics align --text FILE --project PROJECT --language zh|en
# and after review: mvt lyrics apply-edits --project PROJECT --edits FILE
mvt plan resolve --project PROJECT --plan PROJECT/visual-plan.json
mvt preview --project PROJECT --plan PROJECT/resolved-plan.json --ranges PROJECT/preview.json --output PREVIEW_DIR --review-reel
# after separately completing two or more variants with identical ranges:
mvt compare --request COMPARISON_REQUEST.json --output COMPARISON_DIR
mvt render --project PROJECT --plan PROJECT/resolved-plan.json --output OUTPUT.mp4
```

Lyrics commands are conditional. `render` is conditional on accepted sample feedback unless the recorded mode is autonomous. After analysis, alignment and material creation are complete, reproducible preview/full commands use only the saved project, plan, ranges and local assets; they do not run models or contact generation services.

Comparison is also conditional. Its request points only to distinct completed aggregate preview manifests and preserves variant order. Verify that variants intentionally share canonical audio, ranges, output dimensions/fps and H.264/yuv420p + AAC 48 kHz stereo CFR compatibility before running it. Compare landscape and portrait in separate requests; paired inspection can assess shared intent but is not an automatic-reframing claim. Save `comparison.json`, the range-major reel and labeled contact sheet alongside a separate feedback record; objective comparison success is not user approval.

## Feedback record

For each finding record: song ID; sample/global time; observed issue; expected experience; category (`taste`, `material`, `timing`, `tool`); proposed change; affected artifact/layer; verification after rerender. A song needing warmer colors is a plan edit. All songs needing bounded opacity routing is a toolkit capability gap. Do not turn every taste request into new engine code.

## Reproduction record

Save source/canonical hashes, analysis model/config identity, timeline/plan/assets/lyrics hashes, renderer/tool versions, seed, font/media hashes, output ranges, actual output paths and checks. Re-render consumes these files directly and does not regenerate materials or re-run alignment implicitly.
