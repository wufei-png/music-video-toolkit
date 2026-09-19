# projectM integration

The S13 feasibility probe below is historical; the bounded S14 production route is described later. The upstream [libprojectM source](https://github.com/projectM-visualizer/projectm)
is pinned in `lock.json` at `1e7ef7803b69024d1e0656705670adda2ffac817`; its
`projectm-eval` submodule is pinned at `22fb0cfd8f2dfbcd2b68f2443e7f44e19b32c09a`. The core
license file is LGPL 2.1, and its API headers permit LGPL 2.1 or later. This probe's C++ provider
source is MIT under this repository's license. The `.milk` preset and 2×2 PNG texture are generated
only from constants in `scripts/projectm_feasibility.py` and use the repository's MIT license. They
have no third-party preset pack or texture source. The preset draws a basic waveform; the texture
search directory is configured, but the preset does not sample that texture. Those S13 probe
preset/texture bytes were generated externally; S14 commits a separate approved preset.

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
had not been tested at the S13 handoff. S14 later passed the bounded gates below.

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
This intermediate probe proved only the short self-authored feasibility preset on this Mac.
S14's later full/excerpt and song-range evidence appears below.

## S14 approved-preset offline provider CLI

`build` also compiles the repository's `provider.cpp` into
`/absolute/external/build/mvt-projectm-render`, and records its hash. The CLI
accepts the existing `provider-request` schema. Its project JSON contains only a
`preset` reference with path and SHA-256; that file is the request's sole asset.
For the current approved `mvt-wave` preset, parameters are exactly
`{"preset_id":"mvt-wave","policy":"locked-single"}`. The backend's
`integration_patch_sha256` is the SHA-256 of the locked patch digest bytes followed
by `provider.cpp` bytes. No plugin, additional texture or preset transition is
accepted. The source WAV must be the checked canonical 48 kHz stereo 24-bit PCM.

After explicit setup, run an offline job:

```sh
uv run --locked python scripts/projectm_render.py --request /absolute/input/request.json --output /absolute/new-output --checkout /absolute/external/core --build /absolute/external/build
uv run --locked python scripts/projectm_render_check.py --checkout /absolute/external/core --build /absolute/external/build
```

The native renderer consumes PCM from song frame zero, holds one preset, and writes
only requested global frames to FFmpeg. The wrapper checks the pinned runtime,
approved preset, request, exact raw frame bytes, silent CFR video and completed
manifest before atomically installing the result. Existing/contended destinations
and damaged inputs fail without an installed result. The synthetic check runs two
real exports and exercises output conflict, lock and hash rejection.

The MVT process adapter is callable as:

```sh
mvt provider projectm --request FILE --output DIR --checkout DIR --build DIR
```

It invokes the offline wrapper in a child
process and revalidates the request, result, media and reported video hash at its
own boundary. `mvt doctor` reports `not_installed`, `installed` or `ready` for the
configured runtime (`MVT_PROJECTM_CHECKOUT` and `MVT_PROJECTM_BUILD`); `ready`
means the pinned binary is intact. `mvt capabilities` advertises the bounded
S14 route independently of local runtime readiness.

The synthetic S14 acceptance command also checks the full 30-frame run against a
nonzero 15–20-frame excerpt at the raw RGBA boundary, repeats the encoded excerpt,
exercises both closed profiles, composes canonical audio and saved captions,
re-renders from saved artifacts, and compares a projectM preview with a built-in
abstract preview:

```sh
uv run --locked python scripts/projectm_acceptance_check.py --checkout /absolute/external/core --build /absolute/external/build
```

The retained run under `/Users/wufei2/.cache/mvt/projectm/s14-synthetic-acceptance/`
found exact raw global-frame equality, byte-identical repeat excerpts and 51.89 dB
decoded full/excerpt PSNR. Both profile compositions, saved rerender and S11
comparison passed. This is a synthetic technical proof, not song-level artistic
acceptance.

## S14 external same-audio acceptance

From a prepared external checkout/build, `scripts/projectm_song_check.py` accepts an
existing completed 1920x1080/30 built-in control preview, an MVT project, timeline, saved lyrics
and font. It creates one hash-bound `mvt-wave` request per ordered control range,
runs the MVT process adapter, composes audio/captions, bundles the checked previews,
and runs S11 comparison. Use a new output directory outside Git:

```sh
uv run --locked python scripts/projectm_song_check.py --project /absolute/song/project --timeline /absolute/song/timeline.json --lyrics /absolute/song/lyrics.edited.json --font /absolute/font.ttf --control-preview /absolute/song/built-in/preview.render.json --checkout /absolute/external/core --build /absolute/external/build --output /absolute/song/new-projectm-acceptance
```

The retained `soft-harm` run is at `../projects/soft-harm/s14/projectm-v1/`. Its
canonical WAV SHA-256 is `d03ba9b439bf204b60569e876746d6393daf21616e527fe081f054ef91231c34`.
The exact S11 control ranges are 10–22, 39–51 and 190–202 seconds. Each projectM
provider result passed silent-CFR validation; each composed clip has 360 frames and
the same decoded 48 kHz stereo audio hash as its built-in counterpart. The first
provider range independently repeated with byte-identical SHA-256
`48169aeead734f309e0590e964cd7d58d34ca5e98709c502f61c33919369a970`.
Pre-roll frame counts were 300, 1170 and 5700; provider elapsed times were 6.176,
6.793 and 11.794 seconds on this Mac. The checked comparison is
`comparison/comparison.json` (SHA-256
`a4e67bcb5edd700b95395070f3904d23c5b3f472ff50318d8e3f9dbbf574f945`).
Its contact sheet shows the waveform in all three ranges and saved captions where
lyrics are present. This proves a technical same-audio route, not subjective style
approval or full-song rendering. Other hosts and preset packs remain untested.
