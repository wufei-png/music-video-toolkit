# Release checklist

Run this checklist from a clean checkout before publishing a toolkit release. Keep real songs,
provider metadata, generated media, model files and local production workspaces outside Git.

## Repository and contracts

- Confirm `git status --short --ignored` contains only intended tracked changes and known local
  caches.
- Run `uv sync --locked --group dev` and `pnpm --dir renderer install --frozen-lockfile`.
- Run `uv run --locked python scripts/export_schemas.py --check`. If a Python protocol changed,
  regenerate its schema, check compatibility and add versioned migration guidance for a breaking
  change.
- Run `uv run --locked pytest`, `uv run --locked ruff check .`,
  `uv run --locked ruff format --check .` and `pnpm --dir renderer check`.
- Run `git diff --check` and inspect every staged file and staged diff.

## Clean-install production demo

- Build both distributions with `uv build` and inspect the wheel and source archive contents.
- In a temporary clean checkout or unpacked source archive, install the locked Python and Node
  environments plus the pinned Playwright Chromium.
- Follow [the public production demo](../examples/production-demo/README.md) in
  `sample-approval` mode. Confirm it stops after the review reel and does not create a full video.
- Run the demo in explicitly selected `autonomous` mode. Confirm it creates the first cut and that
  the saved-artifact rerender scripts work with analysis, alignment and model paths unavailable.

## Production media gates

For every release candidate made from a real song:

- Review 30–60 seconds total across sparse, transition and climax ranges before rendering the full
  song. Record the reviewed plan, asset and preview hashes with the feedback.
- Confirm the final video is H.264 and exactly the declared supported profile (1920×1080/30 or
  1080×1920/30) with the expected exact frame count; confirm AAC, 48 kHz and two audio channels.
- Confirm the video and canonical-audio endpoints differ by no more than one frame, with any AAC
  padding recorded.
- Scan for unexpected black intervals, missing assets, dropped or duplicated frames and audible
  clipping. Inspect sparse, transition, climax and tail contact sheets.
- Review the first and last lyric cues plus repeated choruses. Confirm expected glyphs render,
  lines stay inside the caption safe area and instrumental gaps have no caption.
- Preserve the final render manifest and its referenced hashes next to the external production
  result. Reproduce at least one saved-artifact render without model access.

Objective checks establish media integrity. Record human visual and listening approval separately;
do not describe an unchecked integration path as passed.

## Rights and publication

- Record provenance and release permission for every distributed audio, image, video and font.
- Confirm package and archive contents contain no private inputs, generated case media, model
  weights, secrets or machine-specific absolute paths.
- Review the release notes against the current CLI capabilities and status. Remove claims for
  unavailable commands or backends.
- Publish, push tags or upload media only after separate authorization.
