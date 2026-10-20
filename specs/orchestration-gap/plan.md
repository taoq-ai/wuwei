# Implementation Plan: WUWEI names an orchestration gap

**Branch**: `1180-orchestration-gap` | **Spec**: spec.md | **Tier**: full

## Summary

One helper and one row in `board.py`, one word in the `DUTY` pattern, one guard in `hook.stop`.
The charter and the skill get a sentence each. No new ledger kind, config key, door or file format.

## Technical context

Stdlib Python 3.11+, runtime under `cli/wuwei/` at most 3,400 lines (3,208 at main 0f6572e6,
3,220 at the head). Tests in `tests/test_watch.py` (board) and `tests/test_hook.py` (Stop), with
`tests/test_status_perf.py` updated for the new row.

## Design

- `board.running(root, session)`: today's `seat.stopped` and `seat.unconfirmed` agent ids make the
  gone set; the result is the roles of today's `seat.started` rows whose session equals the given
  one, whose agent id is a string and not gone. It lives in `board.py` because `hook` imports
  `board`, not the reverse.
- `board.compute` ends with the team row. The open PR count is the distinct `pr` values of the
  rows built so far; a gate gap is a match of `evidence.GATES`, the pattern the board already uses
  for gate gaps; a head is green when its row has no gap starting `CI ` or `required check`.
- `hook.stop` calls `board.running(root, payload.get('session_id'))` in place of
  `running(root) > 0`, and `hook.running` is removed (no caller left after #1172 merged).
- `evidence.DUTY` gains `orchestration:`.

## Constitution check

Stdlib only, test first, shortest diff, no speculative abstraction (one helper with two callers),
runtime budget held (12 of 12).

## Measurements

- Route corpus differential (specs/orchestration-gap/route_diff.py) at main 0f6572e6 and the head:
  corpus sha256 9e099867c909e8400bd80bdcb7e6e4b5d8914785ac6171ed9a56e8aa3a7901b0, 257 routes, 530
  cases, 5 moved. guards.bash 257 and PreToolUse Bash 257: 0 moved. Fixture payloads 8: 0 moved.
  SessionStart: 40 items moved (the team row is appended to the board), 0 items unchanged. Stop, 6
  seat states: 4 moved. No seat and a builder stopped in this session: the reminder gains the
  team line. A seat a dead session left running, and a seat this session left unconfirmed: main
  was silent, the head reminds. A shepherd and gate seat running in this session, and a builder
  running in this session: silent at both.
- Mutants (specs/orchestration-gap/mutants.py) at 3fada9ac, applied to both copies, run one at a
  time: 15 of 15 killed.
