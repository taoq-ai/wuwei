# Implementation Plan: the SessionStart context fits Claude Code's 10,000-character cap

**Branch**: `fix/session-context-cap` | **Spec**: `specs/session-context-cap/spec.md`

## Summary

`session_start` inlines the CLI path, `_way.md` and the Decisions and Done sections of
`_common.md`, names the files to read, and trims the board's last item lines to fit under
10,000 characters, with a count of what it left out. A final cut at 10,000 holds the cap.

## Technical Context

Python 3.11 stdlib. Tests in tests/test_charters.py (the charter fitness tests). Runtime budget
3,400 lines; main is at 2,986, and this item may add 6 (estimate 3).

## Constitution Check

- I. Stdlib only: yes, `re` and `pathlib`, already imported.
- III. An auditor: no new door; only the orientation text changes.
- V. Test first: the three new tests ran red on a copy of main (16,092, 28,638 and 29,162 characters).
- VI. Budgets: no config key; runtime at 2,989 (+3).

## Design

- `read(name)` returns a charter's text, or '' when the file is missing, as the old `is_file()`
  filter did.
- The Decisions and Done sections come from `_common.md` by heading:
  `^## (?:Decisions|Done)\n.*?(?=^## |\Z)`, in file order. `test_decisions_and_done_are_stated_once_in_common`
  already holds both headings in `_common.md`.
- The pointer line names `planner.md` and `_common.md` by absolute path, and the workspace's
  `.wuwei/` folder for goals and standards.
- The board text is split into lines. While the joined parts plus the board exceed 9,900
  characters and the last line is an item line (`- `), the last line is dropped and counted. A
  count above zero adds `<n> more items left out; ``wuwei status`` lists them all.`
- `'\n\n'.join(parts)[:10000]` is the last word on the cap.
- Goals and standards are no longer inlined (up to 6,000 characters). `/wuwei-run` step 2 reads
  both, and the pointer names where they are.
- Docs: the SessionStart rows in `docs/design.md` and `docs/site/concepts/hooks.md`, and the
  first-day line in `docs/site/getting-started.md`, say what the session start now carries.

## Lines

hook.py +3 (18 lines for `session_start` with its docstring, from 14 plus the removed
goals and standards loop): runtime 2,986 to 2,989.

## Measurements

Measured with `python -I measure.py <tree> <items> [<goals and standards chars>]` (a scratch
script that runs `hook.handle(root, 'SessionStart', ...)` with the code host stubbed and prints the
length of `additionalContext`), from the scratch folder, on a `git archive` copy of main and on the
head worktree:

| Workspace | main | head | items shown, left out (head) |
| --- | --- | --- | --- |
| empty | 16,092 | 5,298 | none |
| 40 items | 22,610 | 9,915 | 28, 12 |
| 40 items, 3,000-character goals and standards | 28,638 | 9,915 | 28, 12 |
| 200 items, 3,000-character goals and standards | unmeasured | 9,916 | 28, 172 |

The figures include the scratch folder's tree path (about 110 characters, four times). An
installed plugin path is a similar length.

## Guard testing (AGENTS.md)

`specs/session-context-cap/route_diff.py` reads every route in `tests/fixtures/routes.json`
through `guards.bash` and through `hook.handle` PreToolUse, every fixture payload through its own
event, and SessionStart for 0 and 40 items, at main and at the head, with the corpus sha256.
Expected: no route or payload moves; both SessionStart cases move.

## Mutants

`specs/session-context-cap/mutants.py` applies eight textual mutants to `session_start` in fresh
`git archive` copies and runs the session start tests. At f33f139: 8 mutants, 8 killed, 0 holes.
