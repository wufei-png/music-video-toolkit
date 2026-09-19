# projectM S13 feasibility only

This probe does not register a projectM backend. The upstream [libprojectM source](https://github.com/projectM-visualizer/projectm)
is pinned in `lock.json` at `1e7ef7803b69024d1e0656705670adda2ffac817`; its
`projectm-eval` submodule is pinned at `22fb0cfd8f2dfbcd2b68f2443e7f44e19b32c09a`. The core
license file is LGPL 2.1, and its API headers permit LGPL 2.1 or later. This probe's C++ provider
source is MIT under this repository's license. The `.milk` preset and 2×2 PNG texture are generated
only from constants in `scripts/projectm_feasibility.py` and use the repository's MIT license. They
have no third-party preset pack or texture source. The preset draws a basic waveform; the texture
search directory is configured, but the preset does not sample that texture. No preset or texture
bytes are committed.

Explicit external setup on macOS (may use the network):

```sh
git clone --filter=blob:none https://github.com/projectM-visualizer/projectm.git /absolute/external/projectm/core
git -C /absolute/external/projectm/core checkout --detach 1e7ef7803b69024d1e0656705670adda2ffac817
git -C /absolute/external/projectm/core submodule update --init --depth 1 vendor/projectm-eval
cmake -S /absolute/external/projectm/core -B /absolute/external/projectm/build -DCMAKE_BUILD_TYPE=Release -DENABLE_PLAYLIST=OFF -DBUILD_TESTING=OFF -DENABLE_SDL_UI=OFF -DENABLE_SYSTEM_PROJECTM_EVAL=OFF -DENABLE_INSTALL=ON
cmake --build /absolute/external/projectm/build --parallel 6
```

Offline feasibility run from this repository:

```sh
uv run --locked python scripts/projectm_feasibility.py --core /absolute/external/projectm/core --build /absolute/external/projectm/build --output /absolute/external/new-feasibility-output
```

The run verifies commit, submodule, license, provider source, preset and texture hashes. It compiles
the small CGL offscreen provider against the built shared library, generates public 48 kHz stereo
24-bit PCM, feeds six 1600-sample frame spans, sets explicit frame times `0/30` through `5/30`,
reads an offscreen framebuffer, and encodes two silent H.264/yuv420p 1920×1080/30 results. Each
result has a provider manifest that passes `validate_provider_result`. Output and build products stay
outside Git. `feasibility-report.json` retains revisions, licenses, timings and result hashes.

Observed on 2026-09-19 at `/Users/wufei2/.cache/mvt/projectm/feasibility-final/`: the core and
provider compiled on macOS arm64. Both six-frame results passed silent-CFR, exact frame-count,
profile, input and output hash checks. The first MP4 SHA-256 was
`6f213fa226fe43c46606e91e286c81249bbc85c5d40d2b6f146509f01b54956c`; the second was
`5c5d8e1a51b5565ab75c725450e907ddb6e43e3f4c25dc2d885bfae53d9d2322`. Their bytes
differed even with the same input, explicit frame times and environment. The exact cause was not
isolated. Nonzero global-range replay, longer preset state, texture sampling and cross-host output
have not been tested. These are concrete gates before any production adapter, so projectM remains
absent from `mvt capabilities`.

## S14 locked deterministic runtime

S14 pins a small downstream patch in `patches/0001-seeded-rendering.patch`. It fixes the
random seeds used by preset state, generated noise textures and the preset timekeeper;
the supported provider path also locks one preset per job. This does not establish
cross-host pixel identity or support arbitrary preset packs.

Prepare and build in separate external directories. `prepare` can clone from the
upstream URL, or `--source` may name an existing local clone. Build and render are
offline after preparation:

```sh
uv run --locked python scripts/projectm_env.py prepare --checkout /absolute/external/core
uv run --locked python scripts/projectm_env.py build --checkout /absolute/external/core --build /absolute/external/build
uv run --locked python scripts/projectm_env.py check --checkout /absolute/external/core --build /absolute/external/build
```

`check` verifies the pinned commit, evaluation submodule, license, exact applied
patch diff, untracked source, CMake origin and built library hash. A source or binary
change requires explicit rebuild and a fresh evidence record. The retained patched
six-frame probe at `/Users/wufei2/.cache/mvt/projectm/s14-seeded-probe/` produced
the same encoded SHA-256 twice:
`ed79f203d65222cee0f350c93b507b298019e7334df45f76428957773985f559`.
This proves only the short self-authored feasibility preset on this Mac; S14's
full-range production gates are still pending.
