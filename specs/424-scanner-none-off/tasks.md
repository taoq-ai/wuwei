# Tasks: adapters.scanner = none turns the MCP gate off with one nudge line

Test first: run each test task, see it fail for the stated reason, then do the implementation
task that follows it. Run tests with `python -m pytest -q <file>` from the repository root
using the interpreter the task names. Signatures, texts and placement are in plan.md. MCP
tests reuse `source`, `configured`, `fake_scanner`, `measured`, `approve`, `core`,
`own_workspace`, `inline_plugin` and `strict` from `tests/test_mcp.py`. A test sets a posture
by appending `[security]\nposture = "<name>"\n` to `.wuwei/config.toml`. `ziran` is on `PATH`
on developer hosts: a test that needs it absent sets `PATH` to an empty `tmp_path` directory.
Neutral fixture names only (`docs`, `acme/widget`).

## Phase 1: `none` turns the gate off (FR-001, FR-002, FR-003; US1)

- [X] T001 In `tests/test_mcp.py`, add `test_no_scanner_gate_is_off` parametrized on posture
  `observe`, `guarded`, `strict`: the `source` fixture (one `docs` server, approved with
  `approve(root, 'docs')`, `WUWEI_NOW` set), config `[adapters]\nscanner = "none"\n` plus the
  posture. Assert `core().cached(root)` is `(0, core().NO_SCANNER)`; `core().launch(root)`
  exits 0; `agent_launch.check_mcp` on a WUWEI seat payload built as in
  `tests/test_agent_launch.py` (around line 540-556) returns `(0, NO_SCANNER)`. Fails today: under strict
  `cached` exits 2 (no record), and `NO_SCANNER` does not exist.
- [X] T002 In `cli/wuwei/mcp.py`, add `NO_SCANNER` and the `cached` branch (plan.md 1). T001
  passes.
- [X] T003 In `tests/test_mcp.py`, add `test_no_scanner_check_says_it_once_a_day`: same
  workspace, guarded. First `core().check(root)` returns `(0, NO_SCANNER)`; second returns
  exit 0 with reason `''`; `.wuwei/ziran/status.json` does not exist; today's events hold
  exactly one `mcp.checked` with payload `{'exit': 0, 'servers': {}, 'scanner': 'none'}` and
  no `adapter: none`; `capsys` stderr does not contain `scanner.mcp: unmeasured`. Then set
  `WUWEI_NOW` to the next day: `check` returns the line again. Also assert
  `status.attention(workspace.day_dir(root))` has no `mcp.checked` row. Fails today: exit 2,
  record written, `adapter: none` appended.
- [X] T004 In `tests/test_mcp.py`, add `test_no_scanner_mcp_check_command`: with
  `monkeypatch.chdir(root)`, `commands/mcp.py` `run(Namespace(action='check', words=[],
  widget=False))` exits 0 and stderr is exactly `NO_SCANNER + '\n'`; a second run exits 0 with
  empty stderr. Fails today: exit 2.
- [X] T005 In `tests/test_workspace.py`, next to `test_init_layout`, add
  `test_init_without_scanner_exits_0`: a `tmp_path` project with `.mcp.json` holding one
  `docs` server (`{"command": "fake-server"}`), approved in the sandboxed `~/.claude.json`
  (`projects[<project path>].enabledMcpjsonServers = ["docs"]`); `init.run(Namespace(path=...))`
  returns 0; stderr contains `NO_SCANNER` exactly once and no `unmeasured`. Fails today: exit
  2 with `scanner.mcp: unmeasured`.
- [X] T006 In `tests/test_setup.py`, add `test_setup_owes_no_mcp_step_without_scanner`: the
  fixtures of `test_pending_mcp_decision_is_owed_by_command`, `mcp.check` left real, scanner
  `none`, the same approved `docs` server; the last line names neither `mcp decide` nor `mcp
  check`. Fails today: the last line is `Next: bin/wuwei mcp decide proceed-unmeasured docs`.
- [X] T007 In `cli/wuwei/mcp.py` `check`, add the `none` block (plan.md 1). T003 to T006 pass.

## Phase 2: plan propose and doctor (FR-004, FR-006; US1-3, US3)

- [X] T008 In `tests/test_plan.py` (or `tests/test_mcp.py` next to the #351 propose test that
  uses `plan.propose(proposal(), configured)`), add `test_propose_without_scanner_prints_line`:
  `none`, guarded, one attached server, `goals(root)`. `plan.propose` returns the plan path,
  stderr contains `NO_SCANNER`, the plan file has `- mcp: ` + `NO_SCANNER`; a second propose on
  the same day (after removing the plan as the existing re-propose test does, or a fresh
  workspace whose day already holds the marker event from `core().check`) still writes the
  sweep line with `NO_SCANNER` and prints nothing about MCP; `next.step(root)` returns state
  `gate`. Fails after T007 alone: no print, and the second run's sweep reads `MCP registry: no
  attached servers`.
- [X] T009 In `cli/wuwei/plan.py` `propose`, change the print condition and the sweep line
  (plan.md 2). T008 passes.
- [X] T010 In `tests/test_doctor.py`, add `test_gates_without_scanner`: the `ws` fixture (its
  default `CONFIG` has scanner `none`), write `"mcpServers": {"cockpit": {...}}` into the
  fixture plugin's `.claude-plugin/plugin.json`, and also `record(ws.root, exit=2,
  unmeasured=[['docs', DIGEST]], reason='MCP registry unmeasured; docs: unmeasured')` (an
  earlier-today record). `row(rows, 'mcp gate')` is `ok` with value `NO_SCANNER`; `row(rows,
  'mcp cockpit')` is `{'section': 'gates', 'name': 'mcp cockpit', 'status': 'ok', 'value':
  'covered by plugin integrity'}`; no `mcp docs` row. Fails today: no `mcp cockpit` row and
  `mcp docs` is `warn unmeasured`.
- [X] T011 In `cli/wuwei/commands/doctor.py` `_gates`, add the `none` block (plan.md 3). T010
  passes.

## Phase 3: a configured scanner that cannot start (FR-005; US2)

- [X] T012 In `tests/test_mcp.py`, add `test_scanner_cannot_start_blocks_under_guarded`
  parametrized on `guarded` (expect 2), `strict` (2), `observe` (0): the `configured` fixture
  (scanner `ziran`, `docs` approved), `monkeypatch.setenv('PATH', str(empty))` with `empty` a
  new `tmp_path` directory. `core().check(root)` exits 2, reason starts `MCP registry could not
  run: ziran watch-registry: unmeasured: FileNotFoundError`; `status.json` has `exit 2` and
  `unmeasured == []`; `core().cached(root).exit` equals the parametrized code and, when 2, its
  reason contains `could not run`; `core().launch(root).exit` matches. Fails today: guarded
  `cached` exits 0 and the record lists `docs` as unmeasured.
- [X] T013 In `tests/test_mcp.py`, add `test_scanner_without_data_is_could_not_run`: replace
  `registry.load` with a scanner whose `mcp` returns `registry.Result(2, None, 'ziran
  watch-registry: unmeasured: ValueError: ZIRAN >= 0.39.0 required; version unavailable or
  unsupported')`; guarded `cached` exits 2 and the snapshots directory is restored from the
  backup (seed one snapshot file before the check and assert it is unchanged after). And the
  contrast: `fake_scanner(monkeypatch, 2)` (data present) keeps `docs` per-server unmeasured
  and guarded `cached` exits 0. Fails today on the first half.
- [X] T014 In `cli/wuwei/mcp.py` `check`, add the could-not-start block (plan.md 1). T012 and
  T013 pass.

## Phase 4: existing tests that assumed `none` means unmeasured

- [X] T015 Run `python -m pytest -q tests/test_mcp.py tests/test_doctor.py tests/test_setup.py
  tests/test_agent_launch.py tests/test_brief.py tests/test_signal_status.py
  tests/test_dashboard.py tests/test_board_mcp.py tests/test_headless_e2e.py
  tests/test_integrity.py tests/test_runtime.py tests/test_reference_adapters.py
  tests/test_workspace.py tests/test_plan.py`. For each failure caused by T002/T007/T014, keep
  the test's intent: if it tests unmeasured, refusal, records or decisions, add
  `scanner = "ziran"` under `[adapters]` in its config and supply a fake scanner
  (`fake_scanner`, `scanned`, `ziran_stub`) or an empty `PATH`; if it tests the `none` default
  itself, assert the new result (`NO_SCANNER`, exit 0). Known from a prototype of the two
  `none` branches against main: see the list below. Never weaken an assertion about `ziran` behaviour.
  - `tests/test_mcp.py` `test_own_server_and_source_checkout_attach_no_discoverable_file[none]`:
    under `none` assert `check` returns `(0, NO_SCANNER)` on the first call; keep the
    `covered by plugin integrity` assertion for `ziran`.
  - `tests/test_mcp.py` `test_cockpit_lookalike_file_stays_unmeasured_and_refused` and
    `test_cockpit_lookalike_inline_in_another_plugin_is_measured`: configure `scanner =
    "ziran"` with an empty `PATH`; after T014 the refusal is could-not-run (exit 2) for the
    lookalike, which keeps the test's point (a lookalike is never covered).
  - `tests/test_doctor.py` `test_gates_mcp_servers`: write `[adapters]\nscanner = "ziran"\n`
    first (the `ws` fixture stubs `ziran` on `PATH`).
  - Further entries: see "Measured failures" below.

## Measured failures

A scratch copy of main with only the two `none` branches (`cached`, `check`, no once-per-day
marker, no could-not-start block), run over `tests/test_mcp.py`, `test_doctor.py`,
`test_setup.py`, `test_agent_launch.py`, `test_brief.py`, `test_signal_status.py`,
`test_board_mcp.py`, `test_runtime.py`, `test_reference_adapters.py`, `test_workspace.py`,
`test_plan.py`, `test_quiet_sweeps.py` and `test_env_credentials.py`, failed exactly these
tests because of the change (all pass on main):

- `tests/test_mcp.py::test_init_registers_and_reports_poisoning[False|True]`: config left at
  `none` while `fake_scanner` replaces `registry.load`. Fix: write `[adapters]\nscanner =
  "ziran"\n` instead of `''` (line 326) and set it in the upgrade branch too.
- `tests/test_mcp.py::test_own_server_and_source_checkout_attach_no_discoverable_file[none]`:
  see T015 above.
- `tests/test_mcp.py::test_cockpit_lookalike_file_stays_unmeasured_and_refused` (5 cases) and
  `::test_cockpit_lookalike_inline_in_another_plugin_is_measured` (2 cases): see T015 above.
- `tests/test_mcp.py::test_symlinked_signed_manifest_in_another_plugin_is_measured` and
  `::test_only_plugin_manifest_sources_are_expanded`: rely on the `scanned` helper's fake
  `registry.load` with config `none`. Fix: configure `scanner = "ziran"` (and an empty `PATH`
  where the test expects the unscanned refusal before `scanned` runs).
- `tests/test_doctor.py::test_gates_mcp_servers`: see T015 above.

Failures in `test_setup.py`, `test_signal_status.py` and `test_quiet_sweeps.py` in that run
were artifacts of the copy's location (a sibling plugin directory triggered "restart Claude
Code") and do not occur in the worktree. The could-not-start block (T014) was not in the
prototype; T015's run catches anything it adds, most likely tests that configure `ziran`
with nothing on `PATH` and expect per-server unmeasured.

## Phase 5: docs (FR-007)

- [X] T016 In `tests/test_docs.py`, add `test_scanner_none_turns_the_gate_off`: flattened
  `security.md` contains `the registry gate is off`, `mcp: not measured (no scanner configured;
  set adapters.scanner = "ziran" to measure)` and `cannot start (not on PATH, wrong version) is
  a check that could not run`, and no longer contains `The \`none\` scanner reports unmeasured
  rather than clean`; flattened `configuration.md` contains `turns the registry gate off` and
  `tool drift or poisoning`, and no longer contains `the \`none\` adapter are unmeasured`.
  Fails today.
- [X] T017 Edit `docs/site/security.md` (lines 5, 9, 57) and `docs/site/configuration.md`
  (lines 150, 337-339) as in plan.md 5. T016 passes; run `tests/test_docs.py` whole.

## Phase 6: finish

- [X] T018 Run the full suite `python -m pytest -q`; all pass. Grep the changed files for
  em-dashes and emojis; none.
- [ ] T019 Orchestrator, outside this worktree (spec A6): in `_pipeline/release.sh` line 33,
  require `init` exit 0 (`[ "$c" = 0 ]`) and drop the "tracked as a bug" note; line 34's
  comment about `integrity check` exit 2 without a scanner is stale too. Not a builder task.
