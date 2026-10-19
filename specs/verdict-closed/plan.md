# Implementation Plan: closed findings go under Probes, and a refused verdict names the next free file

**Branch**: `fix/verdict-closed` | **Spec**: `specs/verdict-closed/spec.md`

## Summary

One sentence in gate rule 6 and two lines in the verdict block. One helper line in
`hook._verdict_problem` that finds the next free `<base>-N.md`, used by the three refusals that
tell a seat to write beside a file.

## Technical Context

Python 3.11 stdlib. Tests in `tests/test_hook.py` and `tests/test_charters.py`. Runtime at 2,986
on main (3d2eb29); the item's budget is 1 line.

## Constitution Check

- I. Stdlib only: yes (`re`, `pathlib`).
- III. An auditor: no new door; the refusals stay returned problem strings.
- V. Test first: the new tests ran red before the change (14 failed).
- VI. Budgets: no config key; runtime 2,987 (+1).

## Design

- `free = lambda p: next(n for i in range(2, 999) if (n := <base> + f'-{i}.md') not in {names in p.parent})`.
  `<base>` is `p.stem` with a trailing `-<digits>` dropped when seven hex characters precede the
  dash. `p.parent.iterdir()` lists symlinks, dangling ones included, so a link is never "free".
- The shape refusal: `'\nWrite the corrected verdict to {free(path)} beside it (the next free number) in this shape:\n'`.
- The copy-in refusal: `write yours beside it as {free(copy)}.`
- The replaced-verdict refusal: `Write yours to {free(path)} beside it (the next free number)`.
  Its three source lines fold into two, which pays for the helper's second line.
- `verdict.FORMAT` line 19 says closed findings go under Probes; no line added.
- `charters/_gate.md`: rule 6 and the block; the verdict paragraph tightened so the generated
  agents stay at or under 2,250 words.

## Lines

hook.py +1 (helper +2, the refusal message -1). Runtime 2,986 to 2,987.

## Guard testing (AGENTS.md)

- `probe_differential.py` reads every route in `tests/fixtures/routes.json` through `guards.bash`
  and the PreToolUse hook, replays every payload fixture, and runs a generated matrix of verdict
  hand-backs, at main and at the head. `compare.py` prints the corpus sha256 and each moved row.
- The guard parser is untouched, so the combinatorial bash probe and the normalisation probes do
  not apply.
- `mutants.py` runs each mutant in a fresh `git archive` copy.
