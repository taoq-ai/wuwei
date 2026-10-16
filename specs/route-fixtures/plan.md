# Implementation Plan: the routes seats run and the payloads the harness sends are fixtures the suite reads

**Branch**: `claude/route-fixtures` | **Spec**: `specs/route-fixtures/spec.md`

## Summary

Add `tests/fixtures/routes.json` and `tests/fixtures/payloads/*.json`, and the tests that read
them. No runtime change.

## Technical Context

Python 3.11 stdlib, pytest. Runtime budget 3,000 lines; main is at 2,999, so this item adds none.

## Constitution Check

- I. Stdlib only: the tests read JSON with the standard library.
- III. An auditor: no door added or changed; the fixtures record the verdicts main gives.
- V. Test first: the new tests ran red (10 failed) before the fixtures existed.
- VI. Budgets: runtime stays at 2,999.

## Design

- `test_guards.py`: `door_reached(decision)` maps a guard decision to pass, merge, create, push or
  refusal. `test_every_route_reads_as_recorded` is parametrized over the routes, ids the commands,
  with `origin`, `current_branch` and the code host (`FakeGh`) stubbed. One test checks the corpus
  shape and the ping route; one checks every fixture file for secrets, the canary and local paths.
- `test_hook.py`: `test_every_recorded_payload_replays_without_an_error` replays each payload
  through `hook.handle` under its `hook_event_name`, asserting no output, no `hook.error`, and the
  `seat.started` and `seat.stopped` agent ids a table names. A second test keeps the table and the
  directory in step.

## Sources

- Commands: `grep -rnE '(gh|git) ' charters skills docs/site` and the duties in charters/shepherd.md,
  charters/builder.md and charters/_gate.md.
- Workspace commands: `.wuwei/traces.jsonl` rows of 2026-10-16 naming `gh api` (21 distinct).
- Payload shapes: the Agent `tool_use` inputs and `toolUseResult` in this session's transcript,
  `.wuwei/ledger/` seat rows, and tests/test_codex.py.
