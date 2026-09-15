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

Lyrics can be off, imported, or automatically aligned to the supplied text. Preserve repeated lines and language; check alignment around chorus repetitions and long notes, and surface unmatched spans. Save edits so future alignment does not overwrite them. Both enabled modes feed the same stored cue format to rendering.

## Review and iteration

Read [production workflow](references/workflow.md) for the artifact checklist and feedback method.

Determine and record the review mode before rendering. Default is **sample approval**: confirm direction, prepare media/plan, render several excerpts totaling about 30–60 seconds covering a sparse passage, climax and transition, then wait for feedback before full-song export. Do not choose times based on lyric headings alone. Record the exact plan/assets/ranges shown and user response. Do not include a full-render command in a sample-approval run until explicit feedback accepts that plan/material version. If the user explicitly chooses **autonomous**, complete a first cut within the agreed constraints and report decisions for later revision without labeling self-review as user approval.

Preview ranges use global 48 kHz sample positions and must align to the 30 fps frame grid: each endpoint is a multiple of 1600. Use a new output directory for changed plans or ranges; the command preserves an existing stale/different directory instead of overwriting it. Reusing the same directory is a cache request and succeeds only when its manifest and every output hash still match.

Evaluate separate musical responses, visual hierarchy, lyric legibility, transitions and whole-song pacing. Fix taste decisions in the plan; record reusable capability gaps as development feedback. Preserve the approved versions and re-render only affected material where supported. Changed sample content needs corresponding review in sample-approval mode.

## Final production handoff

Provide video and preview paths, resolved plan, asset and lyric references, render manifest, actual checks, and open quality issues. Existing analysis, plans and local materials must be sufficient to rerender without this Skill or a model. Do not imply permission to publish/distribute the song from permission to render it.
