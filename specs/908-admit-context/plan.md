# Implementation Plan: repo, goal, parent item, scope and title carry through admission

**Branch**: `908-admit-context` | **Date**: 2026-10-12 | **Spec**: [spec.md](spec.md)

## Summary

The context each automatic admission already knows goes into the item record it writes, and
`_start` reads that record. Ambiguity refuses once with the exact flags.

## Constitution Check

- III: shared spots only: `plan.add` (every admission), `dispatch._start` (every start),
  one id helper for both adopted paths.
- IV: test first; each claim that holds has a red test.
- V: no new state kind or event; the finding and item records gain optional keys (`item`,
  `repo`, `goal`, `parent`, `evidence`). Reuses `dispatch.candidate` for the repository.
- VI: stdlib only.

## Files to edit

- `cli/wuwei/commands/seat.py`: `note --item`; `run_fix` records item, goal, repository.
- `cli/wuwei/plan.py`: `adopted_id`; `_owner_prs` uses it; `add` inherits from the finding,
  refuses ambiguity with the exact command, keeps `title`, records `parent` and `evidence`.
- `cli/wuwei/shepherd.py` `claim_pr`: a linked PR keeps its item, a different id is refused;
  `adopted_id`, `repo=` to `plan.add`.
- `cli/wuwei/commands/build.py` `_admit`: `repo` argument from the held record.
- `cli/wuwei/dispatch.py` `_start`: recorded worktree, recorded title and evidence.
- `cli/wuwei/commands/next.py`: `_finding_command` adds the selections a finding cannot infer.
- `cli/wuwei/commands/pr.py`: `--item` help names the id shape.
- `charters/builder.md`, regenerated `agents/builder.md`; `docs/site/reference.md`,
  `docs/site/daily.md`.
- Tests: new `tests/test_admit_context.py`; `test_plan.py` (the two-repository id test becomes
  three repositories with one short name and one file); `test_shepherd.py` (claim in three
  repositories); `test_main_broken.py` (fix item records its repository).

## Verification

The whole suite under 3.12; plan, seat, build, dispatch, shepherd, reconcile, pr actions,
charters, docs and invariants under 3.11.
