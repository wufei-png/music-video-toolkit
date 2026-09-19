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
