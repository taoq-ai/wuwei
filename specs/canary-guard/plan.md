# Implementation Plan: one canary reader, and the canary behind the ledger door

**Branch**: `fix/canary-guard` | **Spec**: `specs/canary-guard/spec.md`

## Summary

Add `ws.canary(root)`, a reader that returns `''` on a missing, non-regular, unreadable or non-UTF-8
file, and call it at the five canary reads in hook.py. Add `canary` to the ledger door's path list in
guards.py (`LEDGER`, so `CACHE` too) and `/canary` to the ledger's raw-text door word.

## Technical Context

Python 3.11 stdlib. Tests in tests/test_hook.py, tests/test_native_evidence.py and
tests/test_guards.py; corpus rows in tests/fixtures/routes.json. Runtime budget 4,000 lines; main is
at 3,914.

## Constitution Check

- I. Stdlib only: yes.
- III. An auditor: no new door; the canary joins the ledger's.
- V. Test first: the new tests run red on main's code before the change.
- VI. Budgets: no config key; runtime at 3,920 (+6 against the item's 3, recorded in the spec).

## Design

- `ws.canary` keeps main's `is_file()` test, so a FIFO or folder reads as no canary and never blocks,
  and wraps the read in `contextlib.suppress(OSError, UnicodeError)`.
- hook.py: `_report` (native seats), `subagent_stop` (the kept report), `_seat_stop`, `post_tool`
  (the seat launch) and the kept-report delivery each call `ws.canary(root)` in place of the inline
  read.
- guards.py line 36: `LEDGER, CACHE = ('ledger', 'ledger.jsonl', 'canary'), (..., 'canary', 'cache')`.
  Line 33: the fourth `DOOR_WORDS` entry reads `(/ledger|/canary|(?![\w./-]))`.

## Lines that may meet #1288 (config-door)

#1288 rewrites guards.py line 36 (it adds `OWNED` to the same assignment) and adds `SEAT_WORDS` after
line 33. Both changes here sit on those lines, so the second merge resolves one hunk by hand: keep
both `canary` entries and #1288's `OWNED` and `SEAT_WORDS`. Nothing else in #1288's guards.py hunks
is touched here.

## Checks

- Route corpus differential: every route of the head's corpus through `test_every_route_reads_as_recorded`
  at main's code and at the head, with the corpus sha256.
- Generated probe (`probe.py`): path class x wrapper x write route, read through `guards.pre_tool`
  and the PreToolUse hook at main and head, each beside the same case on `.wuwei/ledger.jsonl`.
  `run.sh` runs the Bash cases under real bash, for the owner.
- Mutants on `cli/wuwei/` and `.claude/wuwei/cli/wuwei/`, one suite at a time.
