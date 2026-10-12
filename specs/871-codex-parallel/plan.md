# Implementation Plan: parallel Codex seats

**Branch**: `871-codex-parallel` | **Date**: 2026-10-12 | **Spec**: [spec.md](spec.md)

## Summary

Codex task starts take one workspace lock until the job has a thread; `status` returns the
companion's `errorMessage`; `opinion` and `run_loop` release a failed job's seat or build
record so a rerun relaunches; the Codex prompt carries the retro contract rendered from
`verdict.FORMAT`.

## Technical Context

Python 3.11+ stdlib. Files: `adapters/runtime/codex.py`, `cli/wuwei/verdict.py`,
`cli/wuwei/commands/build.py`, `cli/wuwei/dispatch.py`. Tests: `tests/test_runtime.py`
(lock, error, prompt), `tests/test_dispatch.py` (opinion release and relaunch),
`tests/test_build.py` (builder release).

## Constitution Check

- II: a failed job stays exit 2 with its reason; the lock timeout is an OSError, so the
  adapter returns exit 2, never a silent pass.
- III: one start path (`codex._task`) for dispatch and continuation; one wait (`build.wait`)
  carries the error for both callers.
- IV: each change has a failing test first.
- V: `state.lock_ex` and the `.wuwei/*.lock` sidecar pattern are reused (`merge.locked`);
  no daemon, no new module, no config key. The 60 s start bound carries a ponytail comment.

## Changes

1. `codex.py`: `_task(tree, arguments, role, root, brief)` opens `wuwei-start.lock` in the Codex
   home (`CODEX_HOME`, else `~/.codex`), takes it with `state.lock_ex` and runs `task` and `_started`. `_started`, after its workspace-root
   check, polls `status` once a second while its snapshot job is `queued` or `running`
   without a `threadId`, for at most 60 s. `dispatch` and `continue_job` call `_task`.
   `status` adds `error` from `errorMessage`, else a failed job's `summary`. The dispatch
   prompt carries `verdict.retro_contract()` before the mandate.
2. `verdict.py`: `retro_contract()` renders the `Blocked:`, `Gap:` and `Change:` forms from
   `FORMAT`.
3. `build.py` `wait`: the failure message names `status['error']` and says rerun relaunches.
   `run_loop`: on `RuntimeError` from `wait`, write the record back to `ready` (kind
   `build.failed`) and re-raise.
4. `dispatch.py` `opinion`: launch when the seat is not `running`; in the initial round a
   missing, `unmeasured` or `failed` seat dispatches fresh. On `RuntimeError` from `wait`, mark
   the seat `stopped` with `failed` (kind `seat stopped`) and re-raise.
5. `test_opinion_rerun_polls_the_running_job` pinned the bug (a failed job is polled again on
   rerun); it becomes the relaunch test.

## Live smoke fixes (L1, L2, L3)

- L1: `codex.dispatch` adds `Write no file outside <tree>` and, for `sentinel-*` roles, the
  final-message rule plus `verdict.section()`; builders keep `retro_contract()`. `brief.write`
  words the `Verdict file:` line for a second opinion; `opinion`'s rejection continuation asks
  for the verdict as the final message. `opinion` already writes the decision file from the
  result.
- L2a: vcs port `commit_all(repo, item, name, email)` in `adapters/vcs/git.py`, two allowlisted
  argv shapes (`add --all`, `commit --quiet -m <fixed message>`); `build._commit` calls it after
  `wait` succeeds when the worktree is dirty, with `repos[].identity` (refusal names the
  `config set` fix from `commit_push.unset_identity`).
- L2b: `start` in the build record (`next_action`, `open_fix`); `build._unbuilt` in
  `complete_checks` turns a dirty tree or an unchanged head into a `commit` check failure.
- L3: quickstart note only.

## Fix round 1 (review FIX)

- F2: the start lock moves from the workspace to the Codex home (`_home()`, shared with the
  rollout reading), so two workspaces on one host serialize.
- F3: the runtime port gains `cancel(job)` (Codex wraps the companion's `cancel`; Claude
  refuses; none records the absent adapter). `opinion` reads an `unmeasured` seat's old job
  before a fresh dispatch and cancels it while it is `queued` or `running`.
