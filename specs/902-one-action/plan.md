# Implementation Plan: next and every refusal carry one executable action

**Branch**: `902-one-action` | **Date**: 2026-10-12 | **Spec**: [spec.md](spec.md)

## Summary

One pure gate decision (`dispatch.decide`) replaces derive's copy; `next_step` executes it.
`resolve_offer` keeps what its resolver answers, and `build.step` is the one resolver of `build
next` and next's build launches. The listed contradictions close where they start: `_seats`
(fresh seats for stale, lost and missing gates), `receive` (an initial verdict in delta),
merge (the receipt is the record), `raise_action` (a bounded shepherd retry), the spec stop
guard and the build resolver (a Blocked builder asks the owner first), the config-failure hook
and the docs.

## Constitution Check

- II: every changed refusal still exits 1 with its reason; nothing that blocked now passes
  except a stop the charter orders (Blocked) and two read-or-carded commands under a broken
  config.
- III: one gate decision, one build resolver; derive's table and resolve_offer's retry wording
  are deleted.
- IV: test first; `tests/test_one_action.py` drives each case through the real commands and
  hooks (`fakes.day.Day`), red on the base branch.
- V: no new state kind or event kind besides `build.answered`; reuses `_seats`' fresh-seat path,
  `_parked`, `_blocked_card`, `_continue`, `owner_step_call`.
- Hook paths stay pure reads: `decide` reads state, events, git files and owner answers only.

## Files to edit

- `cli/wuwei/dispatch.py`: `decide`, `gate_step`; `next_step` executes `decide`; `_seats` fresh
  path for stale, missing-initial and lost-delta roles (the stale continue goes); `receive`
  takes a late initial in delta; `raise_action` retries the shepherd; `resolve_offer` keeps the
  action; `_blocked_card` takes the build-phase command.
- `cli/wuwei/derive.py`: `_gate` deleted; `offers` maps `decide`.
- `cli/wuwei/commands/build.py`: `step` (the build resolver, the Blocked card); `run` uses it.
- `cli/wuwei/commands/next.py`: `resolve` promotes an owner action to the decision; ENFORCE
  sentence.
- `cli/wuwei/merge.py` `_recorded_gates`: the receipt is the record.
- `cli/wuwei/pr_actions.py` `_gated_push`: reads `decide`.
- `cli/wuwei/specmode.py` `named`: a Blocked stop passes.
- `cli/wuwei/commands/hook.py` `config_failure`: `config check` and `doctor --fix` pass; the
  refusal names them.
- `docs/site/reference.md`, `index.md`, `recovery.md`; `tests/fakes/day.py` (a shepherd that
  does not raise, a builder that stops Blocked).
- Tests: new `tests/test_one_action.py`; existing tests whose expectations encoded the old
  behaviour (`test_next.py`, `test_dispatch.py`, `test_merge.py`, `test_process_depth.py`).

## Verification

Every test file importing a changed module, plus `test_invariants`, `test_docs`,
`test_charters`, under the pipeline interpreter; dispatch, derive, next, build, merge and hooks
under 3.11.
