# Implementation Plan: a seat's end is recorded apart from acceptance of its report

**Branch**: `905-stop-report` | **Date**: 2026-10-12 | **Spec**: [spec.md](spec.md)

## Summary

The stop hook records that the bound seat ended even when its result cannot be recorded: it
stops the seat unmeasured and keeps its report. Identity is checked first, so a late or foreign
stop never touches the seat. Malformed usage is unmeasured. `next` offers to record the kept or
transcript report (`seat stop <name> --verdict`, through `stop_with_report`) before
`--unmeasured`.

## Constitution Check

- III: one recording path per seat end, `agent_launch.stop`; the report is still read once, in
  `hook.fill_stop_text` (claim 1 did not hold).
- IV: tests first, red before the code.
- V: reuses `brief.stop_text`, `state.stop_seat`, `stop_with_report`; no new command.

## Files to edit

- `cli/wuwei/commands/build.py`: `Mismatch` for the agent identity checks in `stopped`; usage
  that does not normalize becomes `{}`; `record_result` drops a kept `report` with `reason`.
- `cli/wuwei/guards/agent_launch.py` `stop`: an already stopped seat returns; builder identity
  first; any other error goes to `_unrecorded`, which keeps the report and stops the seat
  unmeasured only if its record is unchanged since the stop read it.
- `cli/wuwei/state.py` `stop_seat`: `report` and `expected` keywords.
- `cli/wuwei/brief.py`: `keep_report`, `recovery`.
- `cli/wuwei/commands/next.py`: the stuck-seat command is `brief.recovery`.
- `cli/wuwei/commands/seat.py`: `--verdict` with no file reads `kept_report`.
- `docs/site/recovery.md`, `docs/site/reference.md`: the kept report and `--verdict` alone.
- `tests/test_handback.py`: the issue's cases.

## Verification

Full suite under 3.12; agent_launch, brief, build, build_next, doctor, handback, hooks, next,
seat forms, spec mode, state, traces, verdict and e2e day files under 3.11.
