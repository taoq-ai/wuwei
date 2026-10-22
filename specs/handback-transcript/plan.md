# Implementation plan: handback-transcript

**Spec**: `specs/handback-transcript/spec.md`
**Item**: handback-transcript, tier full, goal G-1

## Technical context

- Stdlib-only Python 3.11+, runtime under `cli/wuwei/`, cap 3,600 lines. Main b9522fc7 holds
  3,448; the brief's budget is +16.
- hook-transcript (#1172, on main) holds the launch check in `subagent_stop`: the meta file beside
  the seat transcript names the seat's type and an Agent tool_use, which the session transcript
  holds. `transcript_rows` reads a regular file under `ws.PROJECTS`, links resolved.
- `transcript(payload)` read the seat transcript by its raw path; `_settled` and `last_text`
  preferred the payload's `last_assistant_message`; `pre_tool` linted and attested the
  hand-back's `tool_input.message`.

## Design

1. `transcript` reads through `transcript_rows` (confined) and also returns every report it
   saw (each text part and each tool_use `message`).
2. `_report(root, payload, text)` holds the launch check moved out of `subagent_stop`, finds the
   seat transcript (the payload's `agent_transcript_path`, else the one beside the session
   transcript), rereads it for about 2 s as `_settled` did, and returns the payload text when the
   transcript holds it, else the transcript's last report when the payload has none. Else it
   records `seat.unconfirmed` with the reason and returns None. `_settled` goes.
3. `pre_tool` lints and attests a sentinel's hand-back only from `_report`.
4. `subagent_stop` calls `_report`; the kept-report branch no longer needs its own file check.
5. Tests: `launched` in `tests/conftest.py` hard-links a seat transcript (a symlink out of the
   projects folder no longer reads) and, when none is named, writes the payload's message as the
   harness would. The hand-back helper lays out a launch and a transcript holding the call.

## Cost

One more read of the seat transcript at a sentinel's hand-back. A reread wait (up to about 2 s)
only when the transcript does not yet hold the report.

## Proof

- Tests first: forged hand-back, forged stop, links out of the folder, and the real sentinel flow
  from fixtures built from a real session (`fixtures.py`); red at b9522fc7.
- `route_diff.py` and `compare.py`: the route corpus at main and the head through guards.bash and
  the PreToolUse hook (planner and seat), with its sha256; the sentinel flow and its forged shapes.
- `mutants.py`: 11 mutants of the changed expressions, both runtime copies, one at a time.
