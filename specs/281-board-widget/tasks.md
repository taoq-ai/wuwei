# Tasks: the day board as an inline widget through a plugin MCP server

**Input**: `specs/281-board-widget/` (spec.md, plan.md)

Test first, always: each test task is written, run with the command given, and seen to fail
for the expected reason before its implementation task starts. Run from the repository
root with the interpreter your task names. No absolute local paths, emojis or em-dashes in
any file. Tests build workspaces under `tmp_path`, set `WUWEI_NOW`, and invoke Python with
`sys.executable`.

## Phase 1: shared spot in the dashboard

- [X] T001 Test, `tests/test_dashboard.py` (`test_board_snapshot_and_template_are_shared`):
  with the `workspace` fixture, `dashboard.board_snapshot(day)` equals
  `{'phases': [... 8 phases as in the existing serve test ...], 'build_phases': ('spec', 'implement', 'fix'), 'cap': 3}`
  and `dashboard.TEMPLATE == ROOT / 'templates/dashboard.html'`. Run
  `python -m pytest -q tests/test_dashboard.py -k shared` (fails: no attribute).
- [X] T002 Implement, `cli/wuwei/commands/dashboard.py`: `TEMPLATE`, `board_snapshot`, and
  `run` using both (plan section 1). Then run `python -m pytest -q tests/test_dashboard.py`;
  every existing test stays green.

## Phase 2: US1 and US2, the server (P1)

- [X] T003 Test, `tests/test_board_mcp.py` (new; helper `rpc(lines, monkeypatch)` that
  runs `board.serve(io.StringIO(...), out)` and returns the parsed response lines):
  `test_tools_list_and_ui_resource`: `initialize` with `protocolVersion` `2025-06-18`
  echoes it and reports `serverInfo.name == 'wuwei'`; `tools/list` has exactly one tool
  `wuwei_board` with the input schema, `annotations.readOnlyHint is True`,
  `destructiveHint is False` and `_meta == {'ui': {'resourceUri': 'ui://wuwei/board.html'}}`;
  `resources/list` lists that URI with `text/html;profile=mcp-app`; `resources/read` returns
  `(ROOT / 'templates/dashboard.html').read_text()` exactly with that mime type. Run
  `python -m pytest -q tests/test_board_mcp.py -k ui_resource` (fails: no module).
- [X] T004 Test, `tests/test_board_mcp.py` (`test_protocol_errors_keep_serving`): one input
  with an unparseable line, `[]`, a notification `notifications/initialized`, an unknown
  method, `tools/call` named `other`, `resources/read` of `ui://other`, then `ping`:
  responses are, in order, `-32700` with id `None`, `-32600`, (nothing for the
  notification), `-32601`, `-32602`, `-32602`, and `{'result': {}}` for `ping`.
  Run `python -m pytest -q tests/test_board_mcp.py -k protocol`.
- [X] T005 Test, `tests/test_board_mcp.py`
  (`test_issue_acceptance_board_matches_status_and_dashboard`): a workspace day (shapes from
  `tests/test_dashboard.py::test_cockpit_snapshot_reads_pending_records_and_optional_lanes`)
  with items `b` (`planned`) and `a` (`implement`, `running`, `pr_url`
  `https://example.test/pull/1`), a `gate_verdicts` entry `a:security:gate` with verdict
  `pass`, `raised_prs` and a `watch.actions` episode for that PR, and `decisions/D-3.md`
  (the `D3` text) with `decision_routes` `{'D-3': {'reversibility': 'one-way', 'recommendation': 'A'}}`
  (its `decision.pending` row is the nudge); `CLAUDE_PROJECT_DIR` set to the root. `tools/call wuwei_board`: `isError is False`; the first text line equals
  `status.line(status.snapshot(day))`; the Work rows list `b` before `a`, and `a`'s row
  contains `implement`, `running`, `security gate: pass` and the PR URL; the PRs table holds
  the PR with `ci_red` and its waiting-on; the Decisions table holds `D-3`, `Choose <fix>?`,
  `owner` and `bin/wuwei decision route D-3`; the Attention table has one row per
  `status.attention(day)` row; the text ends with the `Full cockpit:` line.
  `structuredContent` parses to `board_snapshot(day)` (build phases as a list),
  `state.read_state(directory=day)`, the events file text and `cockpit_snapshot(day)`.
  Run `python -m pytest -q tests/test_board_mcp.py -k acceptance_board`.
- [X] T006 Test, `tests/test_board_mcp.py` (`test_scope_and_unmeasured`): outside any
  workspace, `tools/call` text is `No WUWEI workspace here; run bin/wuwei init to create one.`
  with `isError is False` and no `structuredContent`; a root without today's day directory
  gives a text starting `WUWEI no plan yet` and creates no directory; a corrupt
  `state.json` gives `isError is True`, text starting `WUWEI board unmeasured:` and no
  `structuredContent`; a cell value `x|y\nz` renders as `x\|y z`. Run
  `python -m pytest -q tests/test_board_mcp.py -k unmeasured`.
- [X] T007 Test, `tests/test_board_mcp.py`
  (`test_issue_acceptance_no_write_path`): the T005 workspace; record
  `{path: bytes}` for every file under `tmp_path`; monkeypatch `workspace.atomic_write` and
  `state.append_event` to raise `AssertionError`; serve every method from T003 and T004 plus
  `tools/call`; the tool result has `isError is False` and the recorded tree is identical
  (same paths, same bytes). Run `python -m pytest -q tests/test_board_mcp.py -k write`.
- [X] T008 Implement, `cli/wuwei/commands/board.py` (plan section 2) until T003 to T007
  pass. Keep the module under 150 lines.
- [X] T009 Test, `tests/test_board_mcp.py` (`test_bin_wuwei_board_smoke`): one real stdio
  run, `subprocess.run([sys.executable, '-P', '-m', 'wuwei', 'board'], input=<initialize line, tools/list line>, env={**os.environ, 'PYTHONPATH': str(ROOT / 'cli')}, cwd=tmp_path, capture_output=True, text=True, timeout=30)`:
  exit 0, exactly two stdout lines, ids 1 and 2, the second listing `wuwei_board`. Run
  `python -m pytest -q tests/test_board_mcp.py -k smoke`; it passes with T008 (it pins the
  redacting stdout and flush path).

## Phase 3: US1 widget, one template (P1)

- [X] T010 Test, `tests/test_board_mcp.py` (`test_template_renders_from_tool_result`;
  `skipif` node is absent, like `tests/test_dashboard.py`): extract the template script as
  the dashboard tests do; harness defines `cells` and `document` as there, `setInterval`
  as a no-op, `fetch` rejecting, and `window = {parent: host, addEventListener}` where
  `host.postMessage` records each message, answers `ui/initialize` with
  `{jsonrpc: '2.0', id: 1, result: {}}` (source `host`), first delivers a forged
  `ui/notifications/tool-result` with `source` another object (must be ignored), and on
  `ui/notifications/initialized` delivers the real one whose `structuredContent` is the
  T005 call's `structuredContent`. After `setImmediate`: the recorded methods are
  `['ui/initialize', 'ui/notifications/initialized']`; `columns` contains `<strong>a</strong>`
  and `<strong>b</strong>`; `decisions` contains `D-3` and `Choose &lt;fix&gt;?`; `prs`
  contains `ci_red`; `error.textContent == ''`; the forged payload's marker text appears
  nowhere. Run `python -m pytest -q tests/test_board_mcp.py -k template` (fails: page
  never renders without fetch).
- [X] T011 Implement, `templates/dashboard.html` (plan section 3). Then run
  `python -m pytest -q tests/test_dashboard.py tests/test_board_mcp.py`; the existing
  harness tests pass unchanged.

## Phase 4: US3 shipped, signed, and out of the default gate (P1)

- [X] T012 Test, `tests/test_board_mcp.py` (`test_mcp_json_declares_one_stdio_server`):
  `json.loads((ROOT / '.mcp.json').read_text())` equals the plan section 4 object. Run
  `python -m pytest -q tests/test_board_mcp.py -k mcp_json` (fails: file missing).
- [X] T013 Implement, `.mcp.json` (plan section 4).
- [X] T014 Test, `tests/test_integrity.py`
  (`test_release_package_covers_every_shipped_file`): add
  `assert {'.mcp.json', 'cli/wuwei/commands/board.py'} <= names`. Run
  `python -m pytest -q tests/test_integrity.py -k release_package` (fails: `.mcp.json` not
  staged).
- [X] T015 Implement, `scripts/build-release.py` (plan section 5).
- [X] T016 Test, `tests/test_mcp.py` (`test_own_server_needs_a_scanner_to_be_discovered`):
  a workspace `root` under `tmp_path` with `.wuwei/` and no `.mcp.json` of its own; write
  `Path.home() / '.claude/plugins/installed_plugins.json'` with one user-scope entry whose
  `installPath` is `str(ROOT)`; with no config (scanner `none`), `core().discover(root, config)`
  is `[]`, `core().cached(root).exit == 0` and `core().check(root).exit == 0`; with
  `.wuwei/config.toml` `[adapters]\nscanner="ziran"\n`, `discover` is
  `[ROOT / '.mcp.json']`. Run `python -m pytest -q tests/test_mcp.py -k own_server`
  (fails: discovered under `none`).
- [X] T017 Implement, `cli/wuwei/mcp.py` (`discover`, plan section 6). Then run
  `python -m pytest -q tests/test_mcp.py`.

## Phase 5: docs and the full run

- [X] T018 Docs, `docs/site/daily.md` and `docs/site/configuration.md` (plan section 7).
  Run `python -m pytest -q tests/test_docs.py`.
- [X] T019 Run `python -m pytest -q`; everything passes. Grep the changed files for
  em-dashes, emojis and absolute local paths and remove any.

## Phase 6: ship fix, the source checkout must not attach a server

The ship step found `test_headless_e2e.py::test_scratch_build_and_observer_preserve_hook_results`
red: the fixture clones the WUWEI repository as a managed repo, the clone carries the root
`.mcp.json` as a project MCP file, and with the `none` scanner `plan propose` refuses as
unmeasured. The same holds for any workspace that manages a WUWEI checkout, and Claude Code
offers that file as a project server to every contributor. The root cause is the root
`.mcp.json` doubling as a project config; FR-008 only excluded the running install's copy.

- [X] T020 Test, `tests/test_mcp.py`
  (`test_own_server_and_source_checkout_attach_no_discoverable_file`, scanners `none` and
  `ziran`): the plugin installed from `ROOT` and a managed repo holding a copy of every
  top-level file of `ROOT`; `discover` is `[]`, `cached` and `check` are exit 0. Negative
  (`test_cockpit_lookalike_file_stays_unmeasured_and_refused`): a `.mcp.json` with the
  cockpit entry, exact or with changed `command` or `args`, in the install (with
  `mcp.PLUGIN` pointed at it) or in the workspace is discovered and `cached`, `check` and
  `launch` are exit 2. `tests/test_board_mcp.py`
  (`test_plugin_json_declares_one_stdio_server`) and `tests/test_integrity.py`
  (`release_package`): the server is `plugin.json` `mcpServers` and no root `.mcp.json`
  exists or ships. All fail on 5552148.
- [X] T021 Implement: move the server into `.claude-plugin/plugin.json` `mcpServers`,
  delete the root `.mcp.json`, drop it from `scripts/build-release.py` and
  `scripts/headless_e2e.py`, and remove the FR-008 exclusion from `mcp.discover`
  (dead without the file). Docs: `docs/site/configuration.md`. The e2e test passes once the
  change is committed (its fixture clones HEAD); verified with the clone pointed at a HEAD
  without `.mcp.json`.
