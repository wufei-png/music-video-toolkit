---
name: make-music-video
description: 制作或修改音乐视频：理解歌曲、制定分段视觉计划、使用已有生成工具或用户素材、组织样片与成片。适用于 music-video-toolkit 制作流程，不用于实现工具包本身。
---

# Make a music video

You are directing a song production using deterministic toolkit commands. Keep song artifacts in a user-selected production directory outside the toolkit repository. Locate the toolkit checkout from the user/environment; do not assume a machine-specific path. If this Skill is copied out of the repository, obtain the checkout path to read its documentation and run its CLI.

## Establish actual capability

Read the checkout's `docs/implementation/status.md` and run `mvt capabilities` if installed. Trust that current report rather than inferring availability from the bootstrap or implementation plan. Never claim that a planned verb has run. If the requested production needs missing features, explain the specific missing slice; preserve useful creative/material work and hand off development separately.

For supported workflows read `docs/architecture/contracts.md` and `mvt --help`. Run `mvt doctor` before a costly analysis or render. The core has no generation-provider orchestration. Discover image/video tools available in the current harness and use them within the user's scope, or import supplied files. Generated files must exist locally before entering the asset manifest. Missing tools or inputs remain explicit; never fabricate an asset path or success. For a rights-safe command rehearsal in a toolkit checkout, use [the public production demo](../../examples/production-demo/README.md).

## Creative decisions and artifacts

Understand the provided audio, lyrics and metadata; label metadata-only musical descriptions as such. Use listening/analysis evidence where available. Resolve facts from files before asking about genuine creative tradeoffs. Reuse previously settled choices.

Choose A abstract, B media mood scenes, or C layered A+B. Start from whole-song defaults, then override sections where the musical arrangement warrants it. Reuse registered layers and parameters; do not place executable code into plans. For C, compose existing A/B layers through alpha, masks and timing. Keep fonts, media provenance, hashes and explicit duration/loop choices in the production artifacts.

Choose exactly one supported output tuple per plan: landscape `1920x1080/30` or portrait `1080x1920/30`. Treat them as separate plan variants that may share intent; inspect crop, hierarchy and lyrics in each, and never describe a mechanical portrait layout as automatic artistic reframing. Do not invent arbitrary dimensions, 4K or 60 fps support.

When repeated-form evidence is useful, run `mvt structure analyze` against the saved timeline and review the separate `structure.json`. It proposes unlabeled novelty boundaries and repeated spans only. Create an explicit reviewed selection, choose the existing-section replacement policy deliberately, and apply it to a new enriched timeline. Never infer semantic section names, downbeats, bars, pitch or melody from this artifact, and never overwrite the base timeline.

Lyrics can be off, imported, or automatically aligned to the supplied text. Preserve repeated lines and language; check alignment around chorus repetitions and long notes, and surface unmatched spans. Save edits so future alignment does not overwrite them. Both enabled modes feed the same stored cue format to rendering.

## Review and iteration

Read [production workflow](references/workflow.md) for the artifact checklist and feedback method.

Determine and record the review mode before rendering. Default is **sample approval**: confirm direction, prepare media/plan, render several excerpts totaling about 30–60 seconds covering a sparse passage, climax and transition, then wait for feedback before full-song export. Do not choose times based on lyric headings alone. Record the exact plan/assets/ranges shown and user response. Do not include a full-render command in a sample-approval run until explicit feedback accepts that plan/material version. If the user explicitly chooses **autonomous**, complete a first cut within the agreed constraints and report decisions for later revision without labeling self-review as user approval.

Preview ranges use global 48 kHz sample positions and must align to the 30 fps frame grid: each endpoint is a multiple of 1600. Use a new output directory for changed plans or ranges; the command preserves an existing stale/different directory instead of overwriting it. Reusing the same directory is a cache request and succeeds only when its manifest and every output hash still match.

When the user wants to compare two or more completed variants, create an ordered comparison request whose stable IDs and labels point to distinct completed aggregate preview manifests, then run `mvt compare --request FILE --output DIR`. The variants must use the same canonical audio, exact ranges and same output profile with stream-compatible H.264/yuv420p + AAC 48 kHz stereo CFR media. Use separate comparison requests for landscape and portrait. Compare only audits saved previews and creates a range-major reel plus labeled contact sheet; it must not be used as a shortcut that silently renders, resolves, analyzes or aligns a variant. Keep winner selection and subjective feedback in the external production record.

For an Astrofox or projectM visual variant, check `mvt doctor` and the local pinned runtime first. Create a typed provider request binding the canonical WAV, project, checked assets, profile and one global range. Astrofox accepts its pinned local project/plugins/assets; projectM accepts only the approved `mvt-wave` preset hash, one preset per job, and the exact `{"preset_id":"mvt-wave","policy":"locked-single"}` parameters. Run `mvt provider astrofox` or `mvt provider projectm` with its required checkout/build, then `mvt provider compose` with the project, timeline and optional saved lyrics plus checked font. Repeat per range, use `mvt provider bundle` on the ordered composition records, and compare that completed aggregate with a distinct built-in MVT preview. Keep all song files and output outside this repository. The provider video is silent; MVT supplies canonical audio and captions. Rendering is offline. A failed provider job is not a completed variant. The Astrofox editor may be opened only to debug a failure. projectM's bounded waveform is a technical route, not an artistically approved style; MCP remains unavailable.

For Astrofox bar styling or a silent Astrofox overlay on an existing built-in preview or completed full render, use [Astrofox variants](references/astrofox-variants.md). Its scripts expose palette, reflection, frequency range, bar geometry and overlay placement/intensity as saved parameters. Check the effective inherited defaults and compare the same ranges/audio/profile before selecting a look; song-specific colors are examples, not Skill defaults. Full-song overlay requires the user's explicit full-output direction or the workflow's accepted sample feedback.

Evaluate separate musical responses, visual hierarchy, lyric legibility, transitions and whole-song pacing. Fix taste decisions in the plan; record reusable capability gaps as development feedback. Preserve the approved versions and re-render only affected material where supported. Changed sample content needs corresponding review in sample-approval mode.

## Final production handoff

Provide video and preview paths, resolved plan, asset and lyric references, render manifest, actual checks, and open quality issues. Existing analysis, plans and local materials must be sufficient to rerender without this Skill or a model. Do not imply permission to publish/distribute the song from permission to render it.
