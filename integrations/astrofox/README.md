# Pinned downstream Astrofox environment

`lock.json` pins the upstream Git commit, its pnpm lock, MIT license and ordered patch bytes.
The full upstream checkout, dependency store, renderer output and downloaded FFmpeg stay outside
this repository. `prepare` may clone over the network. `build` may download locked packages.
Rendering is a separate offline operation and must not call either setup command.

Run from the MVT repository:

```sh
python scripts/astrofox_env.py prepare --checkout /absolute/external/astrofox-checkout
python scripts/astrofox_env.py build --checkout /absolute/external/astrofox-checkout
python scripts/astrofox_env.py check --checkout /absolute/external/astrofox-checkout
```

The checkout path must be outside the MVT Git tree. `prepare` refuses a checkout at another
revision, unexpected edits, untracked source or a patch stack mismatch. It never resets a
modified checkout. The first downstream patch adds the hidden Electron job route and local,
hash-checked project/audio/assets/plugin loading. Build it before running the public smoke check:

```sh
uv run --locked python scripts/astrofox_smoke.py --checkout /absolute/external/astrofox-checkout
```

The smoke check exercises a hidden renderer, checks that a real HTTP request is blocked, and
rejects synthetic tampered audio, remote media and unpinned plugins.

The second patch adds `pnpm astrofox-render --request FILE --output DIR` inside the pinned
checkout. FFmpeg and FFprobe must be installed on `PATH` before rendering. The command verifies
the prepared patch identity, uses a hidden window and prints one JSON result to stdout. Progress
goes to stderr. It writes a silent H.264/yuv420p CFR video and provider manifest together by
renaming a completed sibling directory. An existing destination is never overwritten. A failed or
cancelled job removes its temporary output. No setup or download runs in the render command.

Run the real synthetic export checks after prepare/build:

```sh
uv run --locked python scripts/astrofox_render_check.py --checkout /absolute/external/astrofox-checkout
uv run --locked python scripts/astrofox_compose_check.py --checkout /absolute/external/astrofox-checkout
```

Set `MVT_ASTROFOX_CHECKOUT` to the prepared checkout or pass `--checkout` to
`mvt provider astrofox`. `mvt doctor` distinguishes `not_installed`, `installed`, `ready` and
`proven` from actual local evidence. Render a typed `provider-request.json` with
`mvt provider astrofox --request FILE --output DIR`; use its `provider-manifest.json` only after
the command succeeds. `mvt provider compose` rechecks the request and result, adds the project's
canonical audio and optional saved lyrics through the normal MVT preview path, and writes
`provider-composition.json`. For multiple ordered global ranges, pass each composition to
`mvt provider bundle --composition FILE ... --output DIR`, then compare that aggregate preview
with a distinct built-in preview through `mvt compare`. See the generated schemas and
`docs/architecture/contracts.md` for exact artifact fields.

The checkout and its plugins/assets must stay local and hash-pinned. Manual opening of Astrofox is
only a debugging or failure-recovery fallback; it is not the production route or acceptance proof.
There is no MCP provider in this slice.
