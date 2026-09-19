# Astrofox bar variants and overlays

Astrofox `BarSpectrumDisplay` draws a frequency-bin bar spectrum from the song's FFT, with an optional mirrored reflection. Its colors, reflection height and frequency interval live in the Astrofox project. The placement and intensity of a *composite over a built-in MVT preview* are separate production choices. Save both sets of choices with the song outside the toolkit repository.

## Project parameters

The pinned Astrofox 2.0.0 defaults apply when a project omits a property: `shadowHeight=100`, `minFrequency=0`, `maxFrequency=6000`, `maxDecibels=-12`, `smoothingTimeConstant=0.5`; `barWidth` and `barSpacing` are automatic. Inspect the actual project and pinned `BarSpectrumDisplay.ts` before describing its current look. `shadowColor` is independent from the main two-color `color` gradient. A dark mirrored area in a composite may be obscured by background subtraction; verify rendered frames before concluding the source project has no reflection.

Create a *new* project file with [astrofox_bar_variant.py](../scripts/astrofox_bar_variant.py). It changes only explicitly supplied properties of one display ID, reports source/output hashes and effective defaults, and refuses to overwrite a file. Available options: `--color-top`, `--color-bottom`, `--shadow-color-top`, `--shadow-color-bottom`, `--shadow-height`, `--min-frequency`, `--max-frequency`, `--max-decibels`, `--smoothing`, `--bar-width`, `--bar-spacing`, `--width`, `--height`, `--opacity`. Supplying bar width or spacing disables its auto-size setting. Keep the unedited source and the variant report.

```text
python3 TOOLKIT/skills/make-music-video/scripts/astrofox_bar_variant.py \
  --input SONG/input/project.json --output SONG/input/project-variant.json \
  --display-id BARS_ID --color-top '#f4c978' --color-bottom '#b45138' \
  --shadow-height 0 --max-frequency 3000 > SONG/input/variant-report.json
```

The colors and `3000` Hz in this example express one song review choice. They are not general defaults. Copy each selected provider request into the variant input directory, set its `project.path` relative to that request and `project.sha256` to the reported output hash. Validate each request and completed provider manifest, then render the *same canonical audio, global ranges and profile* with the pinned checkout. A project change invalidates the old request hash and requires a new provider output directory.

## Overlay on a built-in preview

The usual `mvt provider compose`/`bundle` route produces a standalone Astrofox variant with MVT audio and lyrics. When the user asks to *add* bars to an already completed built-in preview, [astrofox_overlay_preview.py](../scripts/astrofox_overlay_preview.py) layers each checked silent provider clip over the corresponding checked built-in clip, copies its audio, and writes a hash-bound aggregate preview manifest. This is a production composition helper; it is not a new MVT renderer backend or a full-song approval. Use only same-range, same-profile providers. `mvt compare` performs the final stream and identity checks.

Save an overlay config beside the song, with paths relative to the config file:

```json
{
  "schema_version": "0.1",
  "base_preview_manifest": "../built-in/preview.render.json",
  "provider_manifests": [
    "sparse-provider/provider-manifest.json",
    "transition-provider/provider-manifest.json",
    "climax-provider/provider-manifest.json"
  ],
  "profile": {"width": 1920, "height": 1080, "fps_num": 30, "fps_den": 1},
  "background_subtract_rgb": [50, 63, 90],
  "up_px": 300,
  "mix": 0.4
}
```

`background_subtract_rgb` subtracts channels to suppress the dark provider backdrop; sample it from rendered frames for a different project. `up_px` shifts the bar video upward (0 through the frame height), and `mix` adds its processed RGB values at 0–1 strength. The helper assumes matching full-frame provider videos and a completed built-in preview; it is not general alpha-key compositing. If that assumption fails, choose a suitable native MVT layer or prepare a different reviewed composition method. Preserve the config and provider manifest hashes in the output record.

```text
python3 TOOLKIT/skills/make-music-video/scripts/astrofox_overlay_preview.py \
  --config SONG/overlay-config.json --output SONG/overlay-preview
mvt validate --kind render SONG/overlay-preview/preview.render.json
```

For a fair A/B, hold the base preview, ranges, profile, overlay parameter values and encoding settings fixed while changing only the intended Astrofox project properties. Each overlay config points to its own provider manifests. Compare two completed aggregate preview manifests with `mvt compare`; review the contact sheet and short reel, then record user feedback. Do not render a full song in sample-approval mode until its changed material is accepted.

## Overlay on an accepted full render

When the user explicitly requests a full-song overlay, keep the completed built-in render and its manifest unchanged. Make a new Astrofox request with range start 0 and end at the largest frame-aligned sample position **within** the canonical duration. A full MVT render may have one final frame beyond that position. [astrofox_overlay_full.py](../scripts/astrofox_overlay_full.py) checks both source identities, hashes, profile and frame counts, then holds the final Astrofox frame once if needed. It copies the built-in audio stream and writes a separate full-render manifest. Run `mvt validate --kind provider-manifest` and `mvt validate --kind render`, and check the final audio packets, endpoints, black frames and representative visuals against the saved base render. Keep all song inputs and media outside Git.

Use a per-song config with the same overlay choices as the accepted short samples:

```json
{
  "schema_version": "0.1",
  "source_record": "../mvt-project/source/source.json",
  "base_render_manifest": "../final/accepted.mp4.render.json",
  "provider_manifest": "provider/provider-manifest.json",
  "profile": {"width": 1920, "height": 1080, "fps_num": 30, "fps_den": 1},
  "background_subtract_rgb": [50, 63, 90],
  "up_px": 300,
  "mix": 0.4,
  "output_name": "song-astrofox-overlay.mp4"
}
```

```text
python3 TOOLKIT/skills/make-music-video/scripts/astrofox_overlay_full.py \
  --config SONG/overlay-config.json --output SONG/full-overlay
mvt validate --kind render SONG/full-overlay/song-astrofox-overlay.mp4.render.json
```

This script uses channel subtraction and additive blending. It assumes a full-frame Astrofox output with the same selected style and a previously completed MVT base render. A changed palette, placement or intensity needs visual review against that song; a setting accepted for one song is not automatically approved for another.
