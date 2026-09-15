# Start here — next development session

## Read in order

1. [Status](status.md): actual completed work, next slice, validation evidence.
2. [Design](../architecture/design.md): confirmed product decisions.
3. [Contracts](../architecture/contracts.md): authoritative time and artifact semantics.
4. [Slice index](README.md), then only the first dependency-ready unfinished slice.
5. Current source, tests and relevant upstream documentation; [evidence](../architecture/evidence.md) identifies unproven paths.

The bootstrap is complete only when status says so. **S01–S10 are later implementation, not this session's completed features.** Do not implement all slices just because they exist; follow the new user's scope. If asked to proceed through the plan, work in order and persist within that authorization.

## Portable implement-in-stages contract

Use the installed `implement-in-stages` Skill when available. Otherwise this repository contains the required workflow:

- At most 10 dependency-ordered stages; each delivers one meaningful independently checkable result and leaves the repository valid.
- State the selected stage, dependencies, result and checks before editing.
- Implement one stage, verify its observable contract, stage explicit paths and inspect the staged diff, then commit once checks pass.
- Never stage unrelated/pre-existing inputs. A failed live integration or user-review gate stays open; record what failed and what is needed.
- Revise only unfinished stages when evidence invalidates the plan. Do not claim a later-stage test must pass before an earlier stage is valid.
- After the final authorized stage, run all applicable checks and commit any verified fixes. Report commits, actual checks and remaining limits.

## Continuation prompt

> Read AGENTS.md and docs/implementation/START-HERE.md. Inspect current status and implement the next dependency-ready slice using implement-in-stages. Respect the confirmed design, run its checks, inspect and commit explicit paths locally, and update status with evidence and the next action. Do not push or publish. Report any live integration or visual-review gates that remain open.

## Production inputs

The public repository must work without the original songs. Tests generate synthetic click/stem/media fixtures. On the original host only, the parent directory has `mp3/` and `projects/`; `projects/README.md` describes the two local cases and feedback records. Other users supply their own files. Do not copy private lyrics/provider metadata into public fixtures.

## How to resume a blocked stage

Read its evidence log, distinguish environment/install failure from incorrect behavior, reproduce the smallest failing integration, and retain prior manual corrections. A model/device or protocol change updates provenance and relevant cache keys. For missing production review, ask for the actual sample feedback; elapsed time never implies approval. Each stage's automated result can be committed independently when its own contract is valid; do not claim full release acceptance before S10's song review.
