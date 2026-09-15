# File contracts v0.1 — bootstrap baseline

JSON is the initial interchange format. It has one parse path and can be schema-validated. YAML convenience input can be added later without changing the canonical JSON artifacts. Every root has `schema_version: "0.1"`. Unknown fields are rejected; model-generated plans cannot carry executable code.

Python models under `src/music_video_toolkit/contracts.py` are the source of truth once installed. JSON Schema files under `schemas/` are generated from them. Schema validation checks structure; Python validators additionally check ordering, range and identity. Project preflight resolves paths relative to the record that contains them and checks actual files, hashes and cross-file identities as each slice introduces those relationships. Backend support remains a separate check. A structurally valid file is not proof it can render.

## Source record

`source/source.json` records the original input path/hash, canonical path/hash/audio properties and FFmpeg provenance. Its canonical reference resolves to `source/canonical.wav`; relative paths resolve against the source record directory, independent of the process working directory. The canonical format is 48kHz stereo `pcm_s24le`. Its `duration_samples` comes from decoded PCM frames, never from rounded container duration. The original may later be unavailable, but the canonical file and hash are required for project preflight.

## Time and determinism

- Timeline rate is 48000 samples/s; `duration_samples` is the actual canonical PCM frame count, not MP3 container duration × sample rate.
- All cue/range endpoints use non-negative integer samples. Ranges are half-open `[start_sample, end_sample)`; end is greater than start and within the song where applicable.
- Output fps is represented as positive rational numerator/denominator. First delivery accepts 30/1 only.
- Frame f starts at sample `floor(f * sample_rate * fps_den / fps_num)`. A visual impulse for an event at sample s occurs on frame `ceil(s * fps_num / (sample_rate * fps_den))`. Specify this quantization rather than claiming sub-frame display.
- Signals have explicit first sample, hop and values, all finite. RMS normalization, interpolation, attack/release and missing-data policy must be defined in S03/S04. Missing signals are not silence.
- Randomness is seeded and uses global frame/sample time. Transitions and lyrics have exact endpoint ownership; no doubled beat when slicing excerpts.

## Timeline

Contains canonical source SHA-256/path/rate/sample count, analysis provenance, named signals, discrete events and optional sections. Events include their source and confidence where available. Semantic section labels are optional and never inferred from beat count alone. Ordered sections can have gaps at this stage; S04 resolves gaps from whole-song defaults. Stems must be aligned to canonical time and must not be silently padded/truncated without recording the operation.

## Visual plan

Contains seed, a fixed 1080p30 output profile, mode `abstract|mood|hybrid`, whole-song layers, routes, section overrides and lyrics mode/reference. Layers have stable IDs, registered `kind`, category `abstract|media|text`, enabled flag, opacity, typed-at-adapter-boundary parameters and optional asset ID. Generic JSON parameters are a bootstrap envelope: backend allowlists and bounds are mandatory before execution in S04/S05.

Routes target `layer_id` + a parameter and consume a named signal/event with an explicit transform. Overrides address existing section/layer IDs. Baseline modes require at least one enabled abstract layer for A, media layer for B, and both for C; text overlays are permitted in all. Disabling the required layer through overrides is checked during plan resolution in S04/S05.

## Assets

Stable ID, local relative path, type `image|video|font`, SHA-256 and provenance (`user|harness|synthetic`). Optional license/source note. Paths resolve against the manifest directory, not cwd. Cross-directory references such as `../../mp3/...` are allowed for local production; portable export remaps them explicitly. Remote downloads and generation never happen implicitly in rendering. Videos have an explicit offset/loop/hold/trim policy in S05; their own audio is muted by default. Pin fonts for repeatable Chinese/English typography; do not rely on an unspecified system fallback.

## Lyrics

Language, supplied lyric source, source-audio hash, origin `imported|aligned|edited`, and ordered non-overlapping line cues. Stage headings such as `[Chorus]` are context, not sung text. Preserve supplied lyric order, including repeated choruses; missing/unmatched spans are surfaced for correction. `off` requires no timings; `imported` and `auto` both point to a saved lyrics artifact by render time. The render command must never trigger alignment automatically.

## Render manifest

Status, hashes of input artifacts, source hash, seed, environment/backend versions, ordered excerpt ranges and output references. Completed manifests require outputs; failed manifests require an error. Wall-clock run metadata can vary, but cache keys exclude it. Full graph cache keys must include material content, fonts, audio, analysis configuration/model, resolved plan, renderer, fps and seed. Manual edits must survive reruns; never overwrite corrected lyrics/sections with cached automatic proposals.

## Planned command contract

Only `--help`, `--version`, `capabilities`, `doctor`, `validate` and `schema` are bootstrap commands. Future verbs below are **specified, not implemented**:

```text
mvt decode INPUT --project DIR
mvt analyze --project DIR --stems four|none
mvt plan resolve --project DIR --plan FILE
mvt assets check --project DIR
mvt lyrics import FILE --project DIR
mvt lyrics align --project DIR --text FILE --language zh|en
mvt render --project DIR --plan FILE --output FILE
mvt preview --project DIR --plan FILE --ranges FILE --output DIR
```

All tools eventually expose machine-readable results, nonzero failures, stable error codes and actionable missing-dependency messages. Planned commands become supported only after their slice tests pass. Rendering uses resolved artifacts; feature analysis, generation, model download and user decisions remain distinct operations.
