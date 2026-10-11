# Requirements checklist: delete the telemetry proposals

**Purpose**: check the spec and plan before implement. **Feature**: [spec.md](../spec.md)

## Completeness

- [x] CHK001 Every unit removed is named with (a) or (b) and where its job lives now (plan table); no (b) unit.
- [x] CHK002 Every reader of the deleted pieces is listed: `_proposals`, `week_file`, `next.step`, `signal.SILENT`, the event map, `guide.WIDGETS`, `commands.WRITES`, and the tests `test_telemetry`, `test_next`, `test_handback`, `test_parallel_dispatch`, `test_signal_status`, `test_docs`.
- [x] CHK003 Kept pieces with a shared caller are named: `latest_final`, `decision.weekday_hours`, `write_day`.
- [x] CHK004 Charters, skills, `agents/`, hooks, templates, CI workflows, scripts and evals were searched: no proposal mention.
- [x] CHK005 No config key is retired; nothing for `workspace.RETIRED`.

## Clarity

- [x] CHK006 The legacy week-file case has one test with its exact assertions (T004).
- [x] CHK007 Each docs and design-spec edit has its new text written out.

## Consistency

- [x] CHK008 Telemetry, its weekly counts, preview, off, send, sharing, OTLP and DORA are untouched.
- [x] CHK009 No test is loosened: each removed assertion covered deleted code.
- [x] CHK010 The design-spec edits carry the owner's date and issue.

## Dependencies

- [x] CHK011 Order with parts 3 to 5 is stated, with what to skip after a rebase.
