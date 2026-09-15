# Development contract

Read `docs/implementation/START-HERE.md`, `status.md`, and the selected slice before changing code. The production Skill under `skills/` is for making videos, not for implementing this repository.

- User decisions in `docs/architecture/design.md` are settled. Resolve factual questions from code/tools; reopen choices only if new evidence invalidates them.
- Work on one dependency-ready slice at a time, following implement-in-stages. Its portable execution contract is reproduced in START-HERE; use the installed skill when available.
- Inspect tracked, untracked and ignored files. Never commit external songs, raw provider metadata, generated media, models, or unrelated work.
- Use locked Python and Node environments. Report untested integration paths honestly; mocks, schema checks and synthetic tests do not prove song quality.
- Keep the Python protocol models authoritative; regenerate JSON schemas and check compatibility when changing them. Add versioned migration guidance for breaking changes.
- Never label an unimplemented command or backend as available. Update capabilities, status and user-facing instructions with actual behavior.
- Stage explicit paths, inspect staged diffs, run `git diff --check`, then commit each independently valid slice. Push/publish only when separately requested.
- Update status with commit/check evidence, blockers and the exact next action. Keep production approvals and subjective visual feedback in the external song workspace.
