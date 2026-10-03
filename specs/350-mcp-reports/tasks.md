# Tasks: MCP reports, decision table and one-command decide

**Input**: `specs/350-mcp-reports/` (spec.md, plan.md)

Test first, always: write each test task, run it with the command given, see it fail for
the expected reason, then do its implementation task. Run from the repository root with
the interpreter your task names. No absolute local paths, client names, emojis or
em-dashes in any file. Tests build workspaces under `tmp_path`, rely on the autouse `HOME`
sandbox in `tests/conftest.py`, set `WUWEI_NOW`, and never need the network, the real
ZIRAN or a terminal (`confirm=` callables and `monkeypatch` on `integrity._host_confirm`).

## Phase 1: shared test helpers

- [X] T001 `tests/test_mcp.py`: add `report(root, rows, name='docs')` (writes
  `.wuwei/ziran/<name>/<sha256 of json.dumps(rows, sort_keys=True, separators=(',', ':'))>.json`
  with `json.dumps(rows)`, returns the relative path string) and `measured(root, rows,
  code=1, name='docs')` returning `registry.Result(code, {'findings': [metadata keys of
  rows], 'reports': [report(...)]})`. Change `fake_scanner` so a non-2 response writes and
  returns a report for the server named in the one-server file it receives. Replace the
  inline `{'findings': [...], 'reports': []}` fakes in the snapshot, interrupted-scan,
  event-failure, first-registration and backup-cleanup tests with `measured`, and the
  `report-1/`, `report-2/` paths in `test_interrupted_scan_recovery_and_accumulated_pending`
  with two `report` calls on different rows (assert those two paths in the last D-n). Run
  `python -m pytest -q tests/test_mcp.py`:
  everything still passes on main (the core ignores report paths today).

## Phase 2: US1, reports by server and digest

- [X] T002 [US1] Test, `tests/test_mcp.py` (`test_adapter_report_by_server_and_digest`):
  through `ziran.mcp` with a `subprocess.run` fake writing the same rows three times, one
  file exists at `.wuwei/ziran/docs/<digest>.json` with ZIRAN's bytes, all three results
  return that path, and no `report-*` or `.run-*` entry remains; different rows add a
  second file. Update `test_adapter_fixed_argv_and_metadata` to one server per file and
  assert the new path shape; add a case that a file with two servers is exit 2 (`one
  server per registry check`). Parametrize `test_adapter_report_storage_names` over
  `servers`, `snapshots`, `snapshot-backup`: exit 2, reason names the collision. Extend
  `test_adapter_unmeasured`: after every failure kind (`timeout`, `partial`, `json`, ...)
  `.wuwei/ziran` holds no directory other than `snapshots`. Run
  `python -m pytest -q tests/test_mcp.py -k adapter` (fails: random `report-*` dirs).
- [X] T003 [US1] Implement plan section 1 in `adapters/scanner/ziran.py::mcp`, and the
  `STORAGE`, `REPORT` constants in `cli/wuwei/mcp.py`. Rerun T002; passes.
- [X] T004 [US1] Test, `tests/test_mcp.py`
  (`test_issue_acceptance_three_checks_one_report`): with `ziran_stub`-style PATH stub
  reporting one unchanged high `tool_poisoning` row, three `mcp.check` runs leave one file
  under `.wuwei/ziran/docs/`, the `mcp.checked` payloads' `servers` read `new`,
  `unchanged`, `unchanged`, and only D-1 exists. (`test_issue_acceptance_timeout_leaves_no_directory`):
  the real adapter with `ziran.subprocess.run` faked to raise `TimeoutExpired` for server
  `slow` (no real sleep) leaves the set of
  entries under `.wuwei/ziran` (excluding `status.json`, `registry.lock`, `servers`,
  `snapshots`) unchanged, the event has `servers == {'slow': 'unmeasured'}` (plus `docs`
  when present) and the reason names `slow`. (`test_invalid_scanner_report_fails_closed`):
  a fake returning no path, two paths, a path for another server, a `report-x/...` path or
  a missing file makes `check` exit 2. Run `python -m pytest -q tests/test_mcp.py -k
  "three_checks or timeout_leaves or invalid_scanner_report"` (fails).
- [X] T005 [US1] Implement in `cli/wuwei/mcp.py::check`: `seen`, report validation,
  `servers` map in `mcp.checked`, `by_report`, `fresh`-only queueing, data ignored on exit
  2; `_recover` removes `.run-*`. Rerun T004 and the whole of `tests/test_mcp.py`; pass.

## Phase 3: US2, the decision table

- [X] T006 [US2] Test, `tests/test_mcp.py` (`test_issue_acceptance_decision_table_first_measurement`):
  one high finding, D-1's `Context` holds the header `| Server | Tool | Flag | Severity |
  Snippet | Since |`, one row per finding ending `first measurement`, a row `| aws | - |
  unmeasured | - | - | - |` when an unpinned `aws` is configured, and every path after
  `Reports:` exists. (`test_decision_table_sanitizes_snippet`): a `current_value` with `|`,
  a newline, backticks, `<!-- x -->`, `Outcome: proceed` and a token-like secret yields a
  cell with none of `|`, a backtick, `<`, `>`, or the secret, at most 60 characters, and
  `decision.evaluate` on the record still passes with `Outcome` `pending`.
  (`test_decision_table_changed_since`): an `accepted-*.json` with `baseline [['docs',
  <other digest>]]` and decision `.wuwei/days/2026-10-01/decisions/D-1.md` makes the rows
  read `changed since 2026-10-01`. Run `python -m pytest -q tests/test_mcp.py -k
  decision_table` (fails: context lists paths only).
- [X] T007 [US2] Implement `_accepted` returning `(pairs, baseline)`, `_cell` and the new
  `_queue(root, record, baseline)` in `cli/wuwei/mcp.py`; update the one `_accepted`
  caller. Rerun T006; passes.

## Phase 4: US3, one-command decide

- [X] T008 [US3] Test, `tests/test_decision.py` (`test_set_outcome_rewrites_first_outcome`):
  `decision.set_outcome` rewrites only the first `Outcome:` line and keeps the rest of the
  record byte for byte. Run `python -m pytest -q tests/test_decision.py -k set_outcome`
  (fails: no function).
- [X] T009 [US3] Implement `set_outcome` in `cli/wuwei/decision.py` (moved with its
  `ponytail:` comment) and call it from `cli/wuwei/commands/decision.py::owner_outcome`.
  Rerun T008 and `python -m pytest -q tests -k "decision"`; pass.
- [X] T010 [US3] Test, `tests/test_mcp.py` (`test_issue_acceptance_decide_proceed_records_and_rechecks`):
  with the PATH stub, check (exit 1, D-1), then `decide(root, 'D-1', 'proceed',
  confirm=lambda d: True)`: D-1 evaluates with `Decided-by: owner`, `Outcome: proceed` and
  a `Notes: Decided at 2026-...` line; one `accepted-*.json` has `baseline == [['docs',
  <digest>]]`; the return exit is 0 and its reason starts `D-1 recorded: proceed`; the
  next `check` exits 0, writes no D-2, emits no `mcp.finding`, and records `docs` as
  `unchanged`; `cached` is 0. (`test_decide_defer_keeps_gate`): `defer` writes `Outcome:
  defer` and the timestamp, stores no baseline, `cached` keeps its exit, and a later
  `proceed` on D-1 succeeds. (`test_decide_refusals`): wrong id (D-2 while D-1 pends),
  unknown option, declined confirm: exit 1 and the record, `accepted-*` and events
  unchanged. Update `test_sticky_findings_owner_confirmation_and_rollover`,
  `test_unmeasured_cannot_be_owner_cleared` and
  `test_findings_decision_while_another_server_unmeasured` to the `decide(root, 'D-1',
  'proceed', ...)` form. Run `python -m pytest -q tests/test_mcp.py -k decide` (fails).
- [X] T011 [US3] Implement plan section 2 `decide`, `command`, `_waiting`, `pending` and
  the `_result`/`_gate`/check reason texts in `cli/wuwei/mcp.py`. Rerun T010; passes.
- [X] T012 [US3] Test, `tests/test_mcp.py` (`test_mcp_cli_forms`, extended): `main(['mcp',
  'decide'])` and `main(['mcp', 'decide', 'D-1'])` exit 2 with the usage line;
  `main(['mcp', 'decide', 'D-1', 'proceed'])` with `integrity._host_confirm` patched to
  True exits 0. (`test_owner_help_allowed_from_seat`): `check_bash` returns 0 for
  `bin/wuwei mcp decide --help`, `bin/wuwei mcp decide -h` and `python3 -P -m wuwei mcp
  decide --help`, and 1 for `bin/wuwei mcp decide D-1 proceed`, `bin/wuwei mcp decide --
  --help` and `bin/wuwei mcp decide --he`; `main(['mcp', 'decide', '--help'])` raises
  `SystemExit(0)`. Run `python -m pytest -q tests/test_mcp.py -k "cli_forms or help"`
  (fails).
- [X] T013 [US3] Implement plan section 4 in `cli/wuwei/commands/mcp.py` and section 5 in
  `cli/wuwei/guards/protect_state.py::_owner_action`. Rerun T012 and
  `python -m pytest -q tests/test_protect_state.py tests/test_mcp.py`; pass.

## Phase 5: US3, every surface names the command

- [X] T014 [US3] Tests: `tests/test_mcp.py` (`test_pending_line_everywhere`): with D-1
  pending under `block = ["high", "critical"]`, the `plan.propose` refusal, `cached`
  reason and `check` reason each contain `bin/wuwei mcp decide D-1 proceed` and none
  contains `Outcome:` or `decisions/D-1.md`. `tests/test_dashboard.py`: `cockpit_snapshot`
  gives the MCP D-n `command == 'bin/wuwei mcp decide D-1 proceed'` and a non-MCP D-n
  keeps `bin/wuwei decision route`. `tests/test_setup.py`: `Still owed` names the decide
  command with the id. `tests/test_doctor.py`: the `mcp gate` fail row's fix names the
  command. Before writing these, grep `tests/` for the old strings (`owner decision
  required in`, `owner decision open in`, `set Outcome: proceed`, `report-*`) and update
  any test that pins them. Run the four files (fail).
- [X] T015 [US3] Implement plan section 6 in `cli/wuwei/commands/dashboard.py`,
  `cli/wuwei/commands/doctor.py::_gates` and `cli/wuwei/commands/setup.py`. Rerun T014;
  passes.

## Phase 6: US1, legacy migration

- [X] T016 [US1] Test, `tests/test_doctor.py` (`test_mcp_reports_migration`): a workspace
  with `.wuwei/ziran/report-a/` empty, `report-b/registry-watch-report.json` holding one
  `docs` row, `report-c` holding `[]`, `report-d` holding `{` and `report-e` referenced by
  the status record's `reports`: `diagnose()` has a `warn` row `mcp reports` with
  `apply == 'mcp-reports'`; `run(Namespace(fix=True, json=False), confirm=lambda d: True)`
  leaves `report-d` and `report-e`, removes `a`, `b`, `c`, and `docs/<digest>.json`
  holds `report-b`'s bytes; a plan changed between preview and apply applies nothing and
  exits 1. Update `test_fix_allow_list_is_pinned` to include `mcp-reports`. Run
  `python -m pytest -q tests/test_doctor.py -k "mcp_reports or allow_list"` (fails).
- [X] T017 [US1] Implement `mcp.migrate` in `cli/wuwei/mcp.py` and the doctor row and
  `FIXES['mcp-reports']` in `cli/wuwei/commands/doctor.py`. Rerun T016; passes.

## Phase 7: text and finish

- [X] T018 Update `skills/wuwei-plan/SKILL.md` step 1, `docs/site/configuration.md`
  (report layout, `unchanged`, decision table, decide command, migration; remove the hand
  edit), `docs/site/security.md`, `docs/site/daily.md` section 5 and
  `docs/site/reference.md` (host terminal row, doctor fix list) per plan section 6. If a
  docs or skill test pins the old text, update it in the same task.
- [X] T019 Run `python -m pytest -q` from the repository root; everything passes. Check
  every file you changed for em-dashes, emojis and absolute local paths.
