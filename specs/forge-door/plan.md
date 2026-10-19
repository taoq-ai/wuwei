# Implementation Plan: the forged-hook door reads a hook call made through Python

**Branch**: `fix/forge-door` | **Spec**: `specs/forge-door/spec.md`

## Summary

`guards.bash` refused a hand-made hook call only when the program was named wuwei and its next word
was `hook`. Three module constants and one rule in the same place widen it to the routes the guard
can read. The code rule also joins the door words, so a multi-line or unreadable command naming it
is refused too.

## Technical Context

Python 3.11 stdlib (possessive quantifiers need 3.11). Tests in tests/test_guards.py and the route
corpus tests/fixtures/routes.json. Runtime 3,026 lines at 5fe8347; the item's budget is 8.

## Constitution Check

- I. Stdlib only: yes, `re` and `pathlib`.
- III. An auditor: the change only refuses; it writes nothing.
- V. Test first: each round's new tests ran red before its change (31 failed at main; 2, 5, 2 and 1
  in the later rounds), then green.
- VI. Budgets: no config key, no new ledger kind; runtime at 3,034.

## Design

- `FORGE`: two patterns. One is the wuwei module named as code, not as a path: `wuwei` with no
  word character, `/` or `.` before it and no word character, `/` or `-` after it. The other is a `hook` or `record` word.
- `FILLED`: a whole word holding a character sh fills in at run time (`$`, a backtick, a glob or a
  brace). It is anchored at the word's start and read with a possessive `\S*+`, so a long word is
  read once (linear time).
- `CLI`: the CLI's subcommand on the joined argv. That is `wuwei`, `wuwei/__main__.py` or
  `wuwei.__main__`, any `--` words, then `hook` or a filled word. It also matches the CLI with no
  subcommand, as the whole argv or after `-m`, which xargs completes. And a filled word followed
  by `hook` (`"$W" hook`).
- A runner is a segment whose program word is filled, a shell, or one with a word whose name
  starts with `python` or `pypy` (so `uv run python` and `ionice python3` count).
- `bash()` refuses a runner when the command matches both FORGE patterns, or when the argv starts
  with two filled words and the command names `hook` (`x=hook; "$W" $x`). It also refuses a
  runner or the wuwei program whose argv matches CLI. The reason keeps the old text first. The two
  whole-command reads (FORGE and `hook`) run once before the segment loop, so a command of many
  segments stays linear.
- `DOOR_WORDS` gains FORGE, so the raw-text rule refuses a here-document or unreadable command that
  names the module beside hook or record. `hook.door()` reads the same tuple, so a guard error on
  such a command fails closed.
- SECURITY.md lists the script-file case, built names and code from a variable as open. The
  design and doors pages name the new shapes.

## Lines

guards.py +8 (three constants, the door words wrapped onto a second line, one line before the loop, the
rule from 2 lines to 5): runtime 3,026 to 3,034.
