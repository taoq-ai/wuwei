# Implementation Plan: the gate depth reads the item's flags

**Branch**: `663-depth-reads-flags` | **Date**: 2026-10-10 | **Spec**: [spec.md](spec.md)

## Summary

One check at the shared spot. `dispatch.step_zero` is the one function that decides when gate
step zero runs; it gains an optional `flags` argument, and a true `trust_surface` or
`boundary_relevant` runs step zero at standard, naming the flag. `brief.depth_line` passes the
item's flags through. Nothing else changes in runtime code: the security reviewer for a flagged
item already holds on main and gets a pinning test. The rule is recorded as invariant I43 and in
the three docs rows that state when step zero runs.

## Technical Context

Python 3.11+ stdlib only (constitution I). pytest dev-only. No new module, function, config
key, state key or event kind. Two runtime files change by a few lines each.

## Constitution Check

- I stdlib: nothing new imported.
- II exits: no new exit path; `step_zero` stays a pure function.
- III one behaviour one function: the rule lives only in `dispatch.step_zero`; the brief
  passes data to it and adds no logic of its own.
- IV test first: every implementation task below follows its failing test.
- V simplicity: an optional argument with a `None` default, so the two other callers
  (`dispatch.tier`, `pace._guard`) stay untouched; no flag-name constant beyond the literal
  tuple at its one use; no light-depth branch for a state WUWEI cannot record.
- VII security: the rule only adds review depth; nothing can remove it. Flags are written only
  by `wuwei plan approve` (`state.py:342`), so a seat cannot turn them off to skip step zero.
- Workflow: a changed gate rule adds row I43 to design 9.2 and `i43` to
  `tests/test_invariants.py`.

## Design

### cli/wuwei/dispatch.py, `step_zero` (line 220)

Signature `step_zero(value, paths, trust_paths, flags=None)`. Order:

1. `value == 'light'`: `None` (unchanged).
2. `value == 'full'`: `(True, '')` (unchanged).
3. New: `named = [name for name in ('trust_surface', 'boundary_relevant') if (flags or {}).get(name)]`;
   when `named`, return `(True, ', '.join(named))`.
4. The path loop and the skip return (unchanged).

Docstring gains one sentence: a `trust_surface` or `boundary_relevant` flag runs it whatever the
diff (#663).

### cli/wuwei/brief.py

- `depth_line(role, value, worktree, paths=(), trust_paths=(), flags=None)` (line 30): pass
  `flags` as the fourth argument of `dispatch.step_zero` (line 39). The run line already prints
  `f' ({reason})'`, so the output is `Depth: standard; step zero: run (trust_surface)` with no
  format change.
- The call in the brief writer (lines 450-452): add `current.get('flags')` as the last
  argument. `current` is the item row read at line 367.

### Must not change

- `dispatch.tier` (line 119) and `pace._guard` (`pace.py:64`) keep calling `step_zero` without
  flags: their result is the pace's `guard`, and a guard makes fast and careful pace raise the
  tier to full. Flagged items already reach `pace.adjust` as `flagged`.
- `LIGHT_GATE`, the full line, the builder line, the skip line text, the tier record, the role
  set, `next_step`, `verdict.lint`.
- No existing test assertion changes.

### Docs and invariant

- `docs/specs/2026-09-24-wuwei-design.md`:
  - 5.3 table, row `Mutation step (gate step zero)` (line 556), standard column: append `, or
    the item is flagged trust_surface or boundary_relevant (#663)`.
  - 9.2 table, new last row after I37:
    `| I43 | A trust_surface or boundary_relevant item runs gate step zero at standard whatever its diff, and its brief names the flag; no path turns a flagged run into a skip | dispatch.step_zero at standard and full on a non-guard and a guard path under each flag, both flags, agent_surface alone and none | #663; one decision in dispatch.step_zero; a flagged item is never light (I15) |`
    (code spans as in the neighbouring rows). If #657 or another item lands I43 first, take
    the next free number in both places.
- `tests/test_invariants.py`: `i43(case, rules)` returning `rules.memo(('step zero flags',),
  compute)`, where `compute` calls `dispatch.step_zero` and returns a failure string or `None`:
  - each flag alone and both, at standard, on `['cli/wuwei/mask.py']` and on
    `['cli/wuwei/guards/x.py']`: `(True, <names>)`;
  - `agent_surface` alone and `{}` and `None` on `['cli/wuwei/mask.py']`: `(False, ...)`;
  - each flag at full: `(True, '')`.
  Register `'I43': i43` in `INVARIANTS` and `'I43': ()` in `READS`.
- `docs/site/concepts.md` line 389, standard column of `Gate step zero (mutation)`: append `, or
  the lead flagged it trust_surface or boundary_relevant`.
- `docs/site/daily.md` line 334: `mutates only when its diff touches guard code or a trust
  path, or the lead flagged it trust_surface or boundary_relevant`.

## Tests

- `tests/test_process_depth.py`:
  - extend `depth_day` with `flags=None` (writes `items.X.flags.update(flags)` through
    `state._write_state` like `gates`);
  - new parametrized `test_gate_brief_runs_step_zero_for_a_flagged_item` (spec US1 scenarios 1
    to 4) writing a `security` gate brief;
  - new `test_flagged_item_gets_the_security_reviewer` (US2) with `tiered(root, monkeypatch,
    [('cli/wuwei/mask.py', 3, 1)], flags=['trust_surface'])` and `dispatch.tier`.
  `root`, `tiered`, `brief`, `day` are already imported there.
- `tests/test_invariants.py`: `i43`, run by the existing walk; `test_table_matches_the_checks`
  checks the design row.
- The existing parametrized `test_gate_brief_says_when_step_zero_runs` is the regression for
  unflagged items (US1 scenario 5) and stays as it is.

## Project Structure

```text
cli/wuwei/dispatch.py                    step_zero: optional flags
cli/wuwei/brief.py                       depth_line passes flags; call site passes current flags
tests/test_process_depth.py              flagged gate brief and security role tests
tests/test_invariants.py                 i43
docs/specs/2026-09-24-wuwei-design.md    5.3 row, 9.2 I43
docs/site/concepts.md                    step zero row
docs/site/daily.md                       one sentence
```
