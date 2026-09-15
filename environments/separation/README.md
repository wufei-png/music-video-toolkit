# Separation and analysis runtime

This locked Python 3.12 environment isolates the optional `audio-separator`/PyTorch/model stack from the lightweight `mvt` CLI.

```bash
uv sync --project environments/separation --locked
uv run --project environments/separation --locked audio-separator --env_info
uv run --project environments/separation --locked audio-separator --list_models --list_filter drums --list_format json
```

S03 selects `htdemucs.yaml` for the first four-stem proof. Model files live outside Git under the caller-selected model directory. Demucs code is MIT; the pretrained-weight license is not confirmed by the upstream repository, so do not redistribute the downloaded weights.

The explicit `audioread` and librosa 0.10.2.post1 constraints repair two upstream 0.44.2 packaging incompatibilities observed in the live Mac proof: a missing imported dependency and use of the removed `librosa.get_duration(filename=...)` argument. Do not loosen these pins without rerunning real separation and export.
