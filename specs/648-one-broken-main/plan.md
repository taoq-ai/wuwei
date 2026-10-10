# Implementation Plan: one broken main is one fix item

**Branch**: `648-one-broken-main` | **Date**: 2026-10-10 | **Spec**: [spec.md](spec.md)

## Summary

The build loop's one decision point, `build.complete_checks`, learns one rule: when every
failing fast check names lint locations only on files the item did not change, the failure is
main's. It then admits one fix item through the existing `plan.add` and holds the item instead
of resuming its builder: one state write records `main_broken.<fix id>` and sets the build
action to `wait` naming the fix item. One helper, `state.held`, reads that action for `next`,
`dispatch` and `build`, so a held item takes no seat and no build row. When the fix item
merges (or is parked), `build.next_action` turns the `wait` into a `continue` that tells the
builder to rebase, and the checks rerun through the existing loop.

Owner directive (2026-10-10): built on `main` without #646 or #637. No `seat_findings`, no
`plan add --from-finding`, no `depends_on` field.

## Technical Context

**Language/Version**: Python 3.11+, stdlib only at runtime.
**Testing**: pytest. New `tests/test_main_broken.py` reuses `seat` (`tests/test_build_next.py`),
`day_set` (`tests/test_dispatch.py`), `root` and `approved` (`tests/test_next.py`) and `setup`
(`tests/test_build.py`). Neutral fixtures only (items `A`, `B`, repo `app`, `cli/untouched.py`).
**Storage**: the day's `state.json` (new key `main_broken`); events `build.held` and
`build.released`; the fix item is an ordinary `plan.added` item.
**Constraints**: `next.step` runs on hook paths: it reads `data` only and imports nothing new.
The diff read in `complete_checks` happens only when a check failed.

## Constitution Check

- I stdlib only: yes (`re`, `pathlib`).
- II exits: no new command. `build next` keeps exit 0 for a `wait` action; the Codex loop
  exits 1 on `wait` with the reason. An unreadable diff or a refused `plan.add` gives no hold
  (today's round), never a silent pass.
- III one behaviour, one function: the hold rule is `fast_checks.unchanged`; the wait rule is
  `state.held`; the `continue` action is built in `build._continue`, used by the failure round
  and the release.
- IV test first: each test ran red before its change.
- V ponytail: no new command, verb or config. The fix item reuses `plan.add`. CI checks
  deferred. The path heuristic carries a `ponytail:` comment.
- VII security: the recorded path is constrained by the location pattern to `[\w./-]`, has no
  `..` segment and must be a file inside the worktree; no error output is stored.
- Workflow: design 9.2 gains I57 with its check in `tests/test_invariants.py`; design 5.3 gains
  a dated amendment bullet.

## Design

1. `cli/wuwei/fast_checks.py`: `LOCATION`, `SUMMARY`, `unchanged(failures, changed, tree)`.
2. `cli/wuwei/state.py`: `held(data, name)`; `STATE_PRODUCERS['main_broken'] = 'wuwei build'`.
3. `cli/wuwei/commands/build.py`:
   - `_save(also=)` applies a second change in the same write.
   - `_continue(root, record, feedback)`: the resume action, shared by the failure round and
     the release.
   - `_fix_id(data, repo, path)`: `fix-main-<repo>-<path words>`, a `-2`, `-3` successor when
     that item merged.
   - `_main_broken(...)`: the item's changed paths (diff against its merge base through
     `dispatch._changes`, plus `vcs.status`), `fast_checks.unchanged`, then (check, path, fix)
     unless the diff is unreadable, the fix id is the item itself, or that item is parked or
     escalated.
   - `_admit(...)`: `plan.add(fix, goal=<held item's goal>, title='Fix main: ...',
     source='main-broken')` unless it is already an item; a refusal holds nothing.
   - `_hold(...)`: the `wait` action and the `main_broken` entry in one `build.held` write.
   - `_release(...)`: in `next_action`'s same-brief branch, a held build whose fix ended
     becomes a `continue` (`build.released`) telling the builder to rebase and rerun.
   - `run` prints the wait reason on `build check` exit 1; `run_loop` exits 1 on `wait`.
4. `cli/wuwei/commands/next.py` `step`: held items are skipped and uncounted; a held wait row
   when nothing else is due.
5. `cli/wuwei/dispatch.py`: `launch_set` counts only seated builds; `candidate` falls back to
   `main_broken`.
6. `cli/wuwei/commands/event.py`, `cli/wuwei/signal.py`: both events reserved and silent.
7. `charters/builder.md` step 9 sentence, regenerated `agents/builder.md`.
8. `docs/specs/2026-09-24-wuwei-design.md`: 5.3 amendment and the I57 row.

## What must not change

- A failure with no lint location (every existing build-loop test) gets today's `continue`,
  signature and park behaviour.
- `open_fix`, `fix_rounds`, `max_rounds` and the gate and PR fix flows.
- `fast_checks.record`, the checks adapters and the push guard's evidence.
- `merge`, `pr_actions` and the CI path (Deferred).
