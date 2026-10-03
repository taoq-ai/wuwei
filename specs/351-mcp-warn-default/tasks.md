# Tasks: MCP findings warn by default under guarded, block only under strict

Test first: run each test task, see it fail for the stated reason, then do the implementation
task that follows it. Run tests with `python -m pytest -q <file>` from the repository root
using the interpreter the task names. Signatures, texts and placement are in plan.md. MCP
tests reuse `configured`, `fake_scanner`, `metadata`, `core`, `goals` and `proposal` from
`tests/test_mcp.py` and `tests/test_plan.py`; a test sets a posture by appending
`[security]\nposture = "<name>"\n` to `.wuwei/config.toml`.

## Phase 1: The default warns under guarded (FR-001, FR-002; US1-3, US2-1/2)

- [X] T001 In `tests/test_workspace.py` line 145, expect `'block': []`. In `tests/test_mcp.py`
  `test_posture_block_table`, change the `legacy-pending` row to `(None, 'legacy-pending',
  None, 0, 1)` and add the row `(None, 'critical', 1, 0, 1)`. Fails today: the default is
  `["critical"]`, so guarded `cached` returns 1 for both rows.
- [X] T002 In `cli/wuwei/workspace.py` line 55-56, set the `block` default to `[]` (plan.md 1).
  T001 passes.
- [X] T003 In `tests/test_mcp.py`, add `test_strict_blocks_critical_and_high` parametrized on
  `high` and `critical`: strict, `fake_scanner(monkeypatch, 1, [metadata(severity)])`;
  `core().check` exits 1; `core().cached` exits 1 with `(mcp: block, security.areas.mcp)` in
  the reason; `agent_launch.check_mcp` on a WUWEI seat payload returns 1 (reuse the seat
  payload of the existing launch tests in this file); `plan.propose(proposal(), configured)`
  raises `state.StateError`; after the owner records `Outcome: proceed` in the decision and
  `core().decide(configured, confirm=lambda digest: True)` returns 0 (the existing decide
  test's steps), `core().cached` exits 0. Expected to pass after T002 (strict path unchanged);
  if it fails, the failure is a regression to fix in T002, not a new feature.
- [X] T004 In `tests/test_mcp.py` line 545-546, set the list by
  `.replace('timeout_seconds = 60', 'timeout_seconds = 60\nblock = ["high", "critical"]')`
  (plan.md, existing tests). Run it: it fails now (the template still holds `block`, so the
  config has a duplicate key) and passes after T006.
- [X] T005 In `tests/test_mcp.py`, add `test_template_has_no_block_key`: load
  `templates/workspace/config.toml` with `tomllib`; `'block' not in data['scanner']['mcp']`;
  the `[scanner.mcp]` section text mentions `observe`, `guarded`, `strict` and `block`. Fails
  today: the template sets `block = ["critical"]`.
- [X] T006 In `templates/workspace/config.toml` lines 108-109, replace the key with the
  comment block of plan.md 2. T005 and T004 pass.

## Phase 2: One-line summary, plan propose, board (FR-005, FR-006, FR-007; US1-1/2/4)

- [X] T007 In `tests/test_mcp.py`, add `test_guarded_critical_warns_with_summary`: default
  config, `fake_scanner(monkeypatch, 1, [metadata('critical')])`, `goals(configured)`.
  `core().check` exits 1 and its reason contains `(critical)`, `decisions/D-1.md` and
  `bin/wuwei mcp decide`; `core().cached` exits 0; `agent_launch.check_mcp` on a seat payload
  returns 0; `plan.propose(proposal(), configured)` returns a path, `capsys` stderr contains
  `bin/wuwei mcp decide`, and the plan's `- mcp:` sweep line contains `bin/wuwei mcp decide`;
  `status.attention(workspace.day_dir(configured))` has a row whose reason is
  `MCP critical description_changed finding on docs: run bin/wuwei mcp decide`. Fails today:
  the reason names only the file, propose prints nothing, the row reads `mcp.finding`.
- [X] T008 In `cli/wuwei/mcp.py`, add `DECIDE` and `_summary`, use it in `_result` and `_gate`
  (plan.md 3). The check and launch-gate parts of T007 pass; also run `tests/test_doctor.py`.
- [X] T009 In `cli/wuwei/plan.py`, add `import sys` and the stderr print (plan.md 4). The
  propose part of T007 passes.
- [X] T010 In `tests/test_mcp.py`, add `test_finding_row_hides_untrusted_text`: append to
  today's `events.jsonl` through `state.append_event('mcp.finding', {...}, root)` a finding with
  `server_name='bad name; run rm'` and `tool_name='IGNORE PREVIOUS'`; the attention row reads
  `MCP high description_changed finding on unnamed: run bin/wuwei mcp decide` and no row
  contains `IGNORE PREVIOUS`. Fails today: the row reads `mcp.finding` (assert the new text).
- [X] T011 In `cli/wuwei/commands/status.py` `scan`, add the `mcp.finding` reason (plan.md 5).
  T007 and T010 pass; run `tests/test_signal_status.py`, `tests/test_board_mcp.py` and `tests/test_dashboard.py`.

## Phase 3: config check line (FR-004; US3-2/3)

- [X] T012 In `tests/test_posture.py`, add `test_config_check_mcp_block_line` with the
  `checked` fixture: `[security]\nposture = "observe"\n[scanner.mcp]\nblock = ["critical"]\n`
  prints one line containing `scanner.mcp.block (critical)` and `no effect under observe`,
  exit code equal to `checked('[security]\nposture = "observe"\n', capsys)`;
  `[scanner.mcp]\nblock = ["critical"]\n` (guarded) prints one line containing
  `on top of the guarded default` and no `no effect`; `[security.areas]\nmcp = "off"\n` with
  the same list prints `no effect under guarded (mcp: off)`; an empty config prints no
  `scanner.mcp.block` line. Fails today: no such line.
- [X] T013 In `cli/wuwei/commands/config.py` `run`, print the line (plan.md 6). T012 passes;
  rerun `tests/test_posture.py`.

## Phase 4: Existing tests, skill, docs (FR-008)

- [X] T014 In `tests/test_doctor.py` line 393-394, assert the `mcp gate` row is `ok` under the
  default posture for the pending critical record, then append
  `[security]\nposture = "strict"\n` to the config and assert `fail` (plan.md, existing tests).
  Run `tests/test_doctor.py`.
- [X] T015 In `skills/wuwei-plan/SKILL.md` lines 14 and 16, the wording of plan.md 7.
- [X] T016 Docs per plan.md 8: `docs/site/security.md` (lines 15, 63, 68),
  `docs/site/concepts.md` (Security posture paragraph), `docs/site/configuration.md`
  (lines 393-398), `docs/site/recovery.md` (MCP entry with the ziran#447 link),
  `docs/specs/2026-09-24-wuwei-design.md` (lines 859-861 and 984).
- [X] T017 Run the full suite with `python -m pytest -q`; fix any test that relied on the
  `critical` default by pinning strict or an explicit list, never by loosening an assertion.
  Check every file you wrote for em-dashes, emojis and absolute local paths.
