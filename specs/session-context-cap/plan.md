# Implementation Plan: the SessionStart context fits Claude Code's 10,000-character cap

**Branch**: `fix/session-context-cap` | **Spec**: `specs/session-context-cap/spec.md`

## Summary

`session_start` inlines the CLI path, `_way.md` and the Decisions and Done sections of
`_common.md`, names the files to read, and trims the board's last items to fit under 10,000
characters, with a count of what it left out. A final cut at 10,000 holds the cap when the board
has no item left to drop.

## Technical Context

Python 3.11 stdlib. Tests in tests/test_charters.py (the charter fitness tests). Runtime budget
3,400 lines; main is at 2,992, and this item may add 6 (estimate 3).

## Constitution Check

- I. Stdlib only: yes, `re` and `pathlib`, already imported.
- III. An auditor: no new door; only the orientation text changes.
- V. Test first: the three new tests ran red on a copy of main (16,092, 28,638 and 29,162 characters).
- VI. Budgets: no config key; runtime at 2,995 (+3).

## Design

- `read(name)` returns a charter's text, or '' when the file is missing, as the old `is_file()`
  filter did.
- The Decisions and Done sections come from `_common.md` by heading:
  `^## (?:Decisions|Done)\n.*?(?=^## |\Z)`, in file order. `test_decisions_and_done_are_stated_once_in_common`
  already holds both headings in `_common.md`.
- The pointer line names `planner.md` and `_common.md` by absolute path, and the workspace's
  `.wuwei/` folder for goals and standards.
- The board text is split into lines. An item line is one that starts with `- <item id> ` for a
  row on the board. While the final string (the parts joined by blank lines, then the board and
  the left-out line it would carry) is `SESSION_CAP` (10,000) characters or more and an item line
  remains, the board loses everything from its last item line on, and the count goes up by one.
  A count above zero adds `<n> more item(s) left out; ``wuwei status`` lists them all.`
- `'\n\n'.join(parts)[:SESSION_CAP]` holds the cap when no item line is left to drop.
- Goals and standards are no longer inlined (up to 6,000 characters). `/wuwei-run` step 2 reads
  both, and the pointer names where they are.
- Docs: the SessionStart rows in `docs/design.md` and `docs/site/concepts/hooks.md`, and the
  first-day line in `docs/site/getting-started.md`, say what the session start now carries.

## Lines

hook.py +6 over main: `session_start` is 19 lines with its docstring and the `left` helper, from
14, and `SESSION_CAP` is one line beside `REF`. Runtime 3,026 at main 6682925 to 3,032 at the head,
read with `cat cli/wuwei/*.py | wc -l` on each tree.

## Measurements

Measured with `TMPDIR=<scratch>/tmp python -I specs/session-context-cap/measure.py <tree> <items>
[<goals and standards chars>]`. It runs `hook.handle(root, 'SessionStart', ...)` with the code host
stubbed and prints the length of `additionalContext`. Trees: `git archive` copies of main at
6682925 and the head at 9eba49f.

| Workspace | main | head | items shown, left out (head) |
| --- | --- | --- | --- |
| empty | 16,096 | 5,319 | none |
| 40 items | 22,614 | 9,936 | 28, 12 |
| 40 items, 3,000-character goals and standards | 28,642 | 9,936 | 28, 12 |
| 200 items, 3,000-character goals and standards | 54,922 | 9,937 | 28, 172 |

The figures include the scratch tree and workspace paths (about 110 characters each, five
times). An installed plugin path is a similar length; a shorter one leaves the board more room.

## Guard testing (AGENTS.md)

`specs/session-context-cap/route_diff.py` reads every route in `tests/fixtures/routes.json`
through `guards.bash` and through `hook.handle` PreToolUse, every fixture payload through its own
event, and SessionStart for 0 and 40 items, at main and at the head, with the corpus sha256.
Result at 9eba49f against main 6682925: corpus sha256
9e099867c909e8400bd80bdcb7e6e4b5d8914785ac6171ed9a56e8aa3a7901b0 on both; 523 cases; guards 257,
0 moved; PreToolUse Bash 257, 0 moved; payloads 7, 0 moved; SessionStart 2, 2 moved (0 items:
15,988 to 4,876 characters; 40 items: 20,457 to 9,345, with paths normalised). Against the round 1
head (9422fdf, d9d48c1 merged with main): 523 cases, 0 moved.

## Mutants

`python -I specs/session-context-cap/mutants.py <repo> <sha> <scratch> <pytest>` applies each
mutant to both `hook.py` copies in a fresh `git archive` copy, one at a time, and runs
tests/test_charters.py, test_hook.py, test_codex.py and test_setup.py (381 tests). At 9eba49f:
26 mutants, 25 killed, 1 hole. Every off-by-one of the loop condition and the cap fails all 80
sweep points: `> CAP`, `>= CAP - 1`, `>= CAP + 1`, the cap at 10,001 and at 9,999, and the
measure with one join newline. The hole, `>= CAP` to `> CAP - 1`, is the same test on integers.
