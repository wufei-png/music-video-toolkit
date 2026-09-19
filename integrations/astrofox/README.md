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
modified checkout. The empty stack is intentional until the reviewed CLI patches land in S13.
