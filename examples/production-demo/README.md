# Public production demo

This deterministic fixture exercises the same artifact and command path as a local song without distributing third-party audio, lyrics, fonts or generated media. It uses a three-second synthetic song so installation checks stay short; real sample reviews should total about 30–60 seconds.

From an installed checkout:

```bash
uv sync --locked --group dev
uv run --locked python examples/production-demo/create_fixture.py /tmp/mvt-sample-demo --review-mode sample-approval
PATH="$PWD/.venv/bin:$PATH" /tmp/mvt-sample-demo/run-workflow.sh
```

The sample-approval script stops after three preview clips and a review reel. Record explicit feedback in `feedback.md`; only then run a full render for the approved plan:

```bash
uv run --locked mvt render \
  --project /tmp/mvt-sample-demo/project \
  --plan /tmp/mvt-sample-demo/project/resolved-plan.json \
  --output /tmp/mvt-sample-demo/approved-first-cut.mp4
```

An explicitly autonomous rehearsal includes the first-cut command:

```bash
uv run --locked python examples/production-demo/create_fixture.py /tmp/mvt-auto-demo --review-mode autonomous
PATH="$PWD/.venv/bin:$PATH" /tmp/mvt-auto-demo/run-workflow.sh
```

After the first run, rerender from saved artifacts into a new destination:

```bash
PATH="$PWD/.venv/bin:$PATH" /tmp/mvt-sample-demo/rerender-preview.sh /tmp/mvt-sample-demo/preview-copy
PATH="$PWD/.venv/bin:$PATH" /tmp/mvt-auto-demo/rerender-first-cut.sh /tmp/mvt-auto-demo/first-cut-copy.mp4
```

These two scripts invoke only `preview` or `render`; they do not invoke analysis, separation, alignment, a model or the network. Reusing the original preview output instead performs a hash-validated cache hit.
