# File contracts v0.1 — bootstrap baseline

JSON is the initial interchange format. It has one parse path and can be schema-validated. YAML convenience input can be added later without changing the canonical JSON artifacts. Every root has `schema_version: "0.1"`. Unknown fields are rejected; model-generated plans cannot carry executable code.

Python models under `src/music_video_toolkit/contracts.py` are the source of truth once installed. JSON Schema files under `schemas/` are generated from them. Schema validation checks structure; Python validators additionally check ordering, range and identity. Project preflight resolves paths relative to the record that contains them and checks actual files, hashes and cross-file identities as each slice introduces those relationships. Backend support remains a separate check. A structurally valid file is not proof it can render. Bootstrap field changes and regeneration steps are recorded in [migration notes](migrations.md).

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

S03 emits one value every 1024 canonical samples and zero-pads only the final analysis window. Each signal is normalized by its own observed maximum; an all-silent signal is an explicit zero vector. `mix.rms` and the 12 `mix.chroma.*` signals exist in both modes. Four-stem mode adds each stem RMS, `bass.low_energy`, drums `onset` events and a stem manifest. Mix `beat` events are estimates only and never imply a downbeat, bar phase or semantic section.

## Stem and analysis records

`stems/stems.json` identifies the exact four separator outputs, model config/weight hashes, model source and redistribution status. Each 48kHz stereo 24-bit stem records the model output clock, natural resampled sample count, canonical target count and explicit `none|pad|trim` adjustment. `analysis/run.json` records the source/config/model-derived cache key, locked environment identity, elapsed times and output hashes. `--stems none` emits no stem manifest reference and no synthetic stem signals. Cache reuse verifies the referenced files and hashes rather than trusting a prior exit code.

## Visual plan

Contains seed, one closed output profile, mode `abstract|mood|hybrid`, whole-song layers, routes, section overrides and lyrics mode/reference. The only accepted tuples are landscape `1920x1080/30` and portrait `1080x1920/30`; an omitted profile remains the legacy landscape default. Arbitrary sizes, 4K and 60 fps are rejected. Layers have stable IDs, registered `kind`, category `abstract|media|text`, enabled flag, opacity, typed-at-adapter-boundary parameters and optional asset ID. Generic JSON parameters are a bootstrap envelope: backend allowlists and bounds are mandatory before execution in S04/S05.

Routes target `layer_id` + a parameter and consume a named signal/event with an explicit transform. Overrides address existing section/layer IDs. Baseline modes require at least one enabled abstract layer for A, media layer for B, and both for C; text overlays are permitted in all. Disabling the required layer through overrides is checked during plan resolution in S04/S05.

S04 resolves editable abstract plans into `resolved-plan.json`. Its contiguous spans cover `[0, duration_samples)` exactly; named timeline sections use half-open ownership, gaps retain whole-song defaults, and manual label/origin are preserved. When no sections exist, novelty may create unlabeled `automatic` candidate spans only. Orb, ribbon and particles have closed parameter allowlists and numeric bounds. Linear interpolation holds the final sampled signal value; `smooth` records independent attack/release seconds. A missing routed signal is an error rather than zero.

## Structure analysis and reviewed application

S12 `structure.json` is separate from the timeline. It binds the canonical source, exact base timeline hash, locked librosa runtime, analyzer/adapter hashes, configuration and cache identity derived from both the input configuration and completed candidate content. A schema-valid edit to boundaries or groups is not a cache hit. Beat-synchronized cells combine existing normalized `mix.rms` and 12-bin `mix.chroma.*`; cosine self-similarity produces deterministic novelty boundaries and unlabeled repeated-span groups with confidence and anchor provenance. It does not infer semantic section names, downbeats, bars, pitch or melody.

`mvt structure analyze` never changes the base timeline. `mvt structure apply` requires a separate typed selection with `reviewed: true`, exact structure/timeline hashes, a complete contiguous set of selected ranges, and an explicit `require-empty|replace` policy for pre-existing sections. Exact candidate edges remain automatic with propagated confidence; labels or adjusted/unreferenced edges become manual without automatic confidence. Application writes a separate timeline, rebases its source reference to that output record, and never overwrites the base, structure or selection.

## Assets

Stable ID, local relative path, type `image|video|font`, SHA-256 and provenance (`user|harness|synthetic`). Optional license/source note. Paths resolve against the manifest directory, not cwd. Cross-directory references such as `../../mp3/...` are allowed for local production; portable export remaps them explicitly. Remote downloads and generation never happen implicitly in rendering. Videos have an explicit offset/loop/hold/trim policy in S05; their own audio is muted by default. Pin fonts for repeatable Chinese/English typography; do not rely on an unspecified system fallback.

S05 writes `assets.checked.json` after probing actual content. It binds the source manifest hash and every asset hash to typed metadata: dimensions for images; dimensions, exact decoded frame count, constant rational frame rate, duration and audio presence for videos; and reported font families for fonts. The cache key changes when the manifest or any asset content changes. Remote URLs, mislabeled media, variable-frame-rate video and unavailable font metadata are rejected.

Media parameters use `cover|contain`, normalized x/y, scale, bounded deterministic motion, integer z, `none|circle` mask and `normal|add` blend. Video trim is the half-open source-frame interval `[in_frame, out_frame)`. Global samples before `offset_samples` hold `in_frame`; after the trim range, `error`, `loop` or `hold` applies. Video audio is always muted. Section transitions crossfade previous and current media configurations on the canonical sample clock.

## Lyrics

Language, supplied lyric source, source-audio hash, origin `imported|aligned|edited`, and ordered non-overlapping line cues. Stage headings such as `[Chorus]` are context, not sung text. Preserve supplied lyric order, including repeated choruses; missing/unmatched spans are surfaced for correction. `off` requires no timings; `imported` and `auto` both point to a saved lyrics artifact by render time. The render command must never trigger alignment automatically.

S06 imports UTF-8 LRC/SRT only. LRC cues end at the next retained timestamp or canonical song end; the provenance records this rule, offset and skipped stage-heading count. SRT endpoints are explicit and overlaps fail. Each cue owns `[start_sample, end_sample)`, may contain explicit line breaks, and is limited to 240 characters for the bounded layout. Import records the source text hash and refuses to overwrite different or invalid existing `lyrics.json`, preserving hand edits.

S07 aligns known UTF-8 text with isolated WhisperX CPU timing evidence. The ASR transcript is never emitted as lyric content. Exact-character matches map monotonically across the supplied text so repeated choruses retain source order; low-coverage lines remain explicit unmatched report entries. Optional independent reference points use fixed 250 ms median and 500 ms nearest-rank P90 limits. A complete reviewed onset document, including previously unmatched lines, produces a separate `edited` artifact whose cue ends are the next reviewed start or song end and does not rerun a model.

Enabled lyrics require a checked local font asset and the resolved plan binds the lyrics artifact hash. The renderer embeds that font, wraps centered lines inside profile-specific safe-area geometry and font bounds, and applies a 100 ms sample-clock fade capped to half the cue. It tests the declared minimum font exactly and fails explicitly if a cue still exceeds the profile line limit; it does not silently shrink below the bound or clip extra lines. Portrait and landscape have separate responsive limits; this is deterministic layout, not automatic artistic reframing. Interludes have no caption. `off` carries no lyric path/font/hash and does not open a lyric artifact.

## Render manifest

Status, hashes of input artifacts, source hash, seed, environment/backend versions, ordered excerpt ranges and output references. Completed manifests require outputs; failed manifests require an error. Wall-clock run metadata can vary, but cache keys exclude it. Full graph cache keys must include material content, fonts, audio, analysis configuration/model, resolved plan, renderer, fps and seed. Manual edits must survive reruns; never overwrite corrected lyrics/sections with cached automatic proposals.

S08 adds a `preview` request containing uniquely named, ordered and non-overlapping global sample ranges. Executable ranges must also align to 30 fps boundaries (multiples of 1600 samples) and remain inside the canonical song. Each independent clip retains the whole-song frame/sample clock while its MP4 starts at local time zero. An optional review reel concatenates those clips in request order.

Every completed render manifest now requires a cache key. Preview cache identity covers the source record, timeline/analysis provenance, editable and resolved plans, asset manifests and material files including fonts, renderer source and dependency lock, seed, fps, range request and review-reel choice. A cache hit revalidates every declared output hash. Existing stale, incomplete or differently keyed output directories fail without overwrite; failed temporary jobs are removed before any completed aggregate manifest is installed.

S12 carries the validated plan profile through renderer configuration, aspect-aware camera/media fit and crop, normalized motion, particles, lyrics, FFmpeg, output probing, cache identity, manifests and previews. Output probes must match the declared tuple exactly. Landscape and portrait are separate plan variants that may share intent; one is not implicitly derived or artistically reframed from the other.

S11 render/preview manifests additionally record `canonical_audio_sha256`. The field remains optional so older S08–S10 evidence still validates, but comparison requires it and rejects legacy manifests without canonical identity.

## Comparison

A comparison request contains at least two ordered variants with stable IDs, human labels and paths to distinct completed aggregate preview manifests. Aggregate identity requires the recorded preview request and adapter inputs; resolved aliases or symlinks to the same manifest are rejected. Reordering variants changes comparison identity and output order. Comparison never renders or invokes analysis, alignment or plan resolution.

Every variant must share the canonical-audio hash, original-source hash, ordered global sample ranges, range count and actual probed stream profile. Comparison requires H.264/yuv420p video at a constant rational frame rate plus AAC 48 kHz stereo audio; codec parameters, dimensions, time bases, pixel/sample formats and codec extradata are bound by an exact compatibility signature so stream-copy inputs cannot silently disagree. Landscape and portrait therefore require separate comparison requests. Every clip must have the exact frame count implied by its range and probed rational fps, including during standalone `comparison` validation. For each range, decoded stereo 48 kHz `s24le` PCM hashes must match across variants. Preview manifests, all referenced clips and optional per-preview review reels are hash-checked before output installation. Plan, assets, seed, input graph, renderer and environment hashes are recorded per variant and may intentionally differ.

`comparison.json` binds the request, input manifest/clip hashes and probes, tool versions, ordered variants and generated artifact hashes. The review reel is an FFmpeg stream copy in range-major then variant-major order; it is decoded/probed after concatenation and must retain the shared compatibility signature and summed frame count before installation. The labeled contact sheet uses the same relative midpoint frame for every variant within a range. Subjective feedback and winner selection remain separate external records. The output directory is installed atomically; identical intact work may be reused only after all input and output hashes are revalidated, while stale, partial or damaged directories fail without overwrite.

## Command contract

Bootstrap commands are `--help`, `--version`, `capabilities`, `doctor`, `validate` and `schema`. S01 implements `decode`; S02–S05 extend `render`; S03 implements `analyze`; S04 implements `plan resolve`; S05 implements `assets check`; S06 implements `lyrics import`; S07 implements `lyrics align` and `lyrics apply-edits`; S08 implements `preview`; S11 implements `compare`; S12 implements `structure analyze` and `structure apply`:

```text
mvt decode INPUT --project DIR
mvt analyze --project DIR --stems four|none
mvt structure analyze --project DIR --timeline FILE --output FILE
mvt structure apply --project DIR --selection FILE --output FILE
mvt plan resolve --project DIR --plan FILE
mvt assets check --project DIR
mvt lyrics import FILE --project DIR
mvt lyrics align --project DIR --text FILE --language zh|en
mvt lyrics apply-edits --project DIR --edits FILE
mvt render --project DIR --plan FILE --output FILE
mvt preview --project DIR --plan FILE --ranges FILE --output DIR
mvt compare --request FILE --output DIR
```

All tools expose machine-readable results, nonzero failures, stable error codes and actionable missing-dependency messages as their slices implement them. Commands and layer kinds become supported only after their slice tests pass. Rendering and preview use saved artifacts; feature analysis, generation, model download and user decisions remain distinct operations.
