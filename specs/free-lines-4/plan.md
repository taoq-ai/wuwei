# Implementation Plan: free runtime lines with no behaviour change

**Branch**: `claude/free-lines-4` | **Spec**: `specs/free-lines-4/spec.md`

## Summary

Apply the lead's scratch prototype (2,999 to 2,973 lines at 9d6701e), then adjust it where it
reads worse or breaks the 150-character line cap. Add split tests that pin the three `OPS`
alternatives that must stay. Prove no behaviour change with the suite and a differential probe.

## Technical Context

Python 3.11 stdlib, pytest. Runtime budget 3,000 lines in `cli/wuwei/`, at 2,999 on main.

## Constitution Check

- I. Stdlib only: no import added.
- III. An auditor: no door added or removed; `guards` returns what it returned before.
- V. Test first: the split tests ran red with `&&`, `|&` or `&>` dropped from `OPS`.
- VI. Budgets: no config key; runtime falls from 2,999 to 2,976.

## Design

- Walrus rewrites from the prototype in evidence, guards, hook, plan, report, setup, sync, upgrade
  and verdict, except `hook.exception_refs` (`if repo := match[1] or repo:` reads worse).
- `guards.segments`: `dollar` and `glued` booleans; `glued` spans two lines under a comment that
  names why the `''` sentinel stays.
- `guards._unwrap`: nested `if not re.fullmatch(r'<[<&]*', ...)` appends the output redirect target.
- `guards.OPS`: `;;` removed; `\|\|` stays (see the spec's Clarifications).
- `guards.LEDGER_DENIED`: one constant for the three refusal call sites; the `pre_tool` check joins to one line.
- `tests/test_guards.py`: four `re.findall(guards.OPS + r'|\w+', ...)` split cases and one
  `segments` case for the glued `&&>|` and `|&>` runs.
- `.claude/`: rewritten by `setup.vendor('.')` from the worktree root.

## Verification

- Full suite with `/root/.local/bin/pytest -q -p no:cacheprovider`.
- Differential probe: `git archive` of 9d6701e and of the head into two scratch folders; feed both
  `guards.segments` 82,944 generated commands and count differences. A mutant without the sentinel
  confirms the probe sees a change (8,400 differ). The same script also feeds every operator pair
  trailing both words (20,736 commands) and every run over `|&;<>()` up to length 5, alone, glued,
  spaced and trailing (117,642 commands), and compares the raw OPS split of each run once `;;` is
  read as `;` `;`.

## Rollback

Revert the commit.
