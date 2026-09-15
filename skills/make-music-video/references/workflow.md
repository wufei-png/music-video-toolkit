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

## Feedback record

For each finding record: song ID; sample/global time; observed issue; expected experience; category (`taste`, `material`, `timing`, `tool`); proposed change; affected artifact/layer; verification after rerender. A song needing warmer colors is a plan edit. All songs needing bounded opacity routing is a toolkit capability gap. Do not turn every taste request into new engine code.

## Reproduction record

Save source/canonical hashes, analysis model/config identity, timeline/plan/assets/lyrics hashes, renderer/tool versions, seed, font/media hashes, output ranges, actual output paths and checks. Re-render consumes these files directly and does not regenerate materials or re-run alignment implicitly.
