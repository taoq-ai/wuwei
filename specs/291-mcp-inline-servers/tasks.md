# Tasks: the registry gate measures servers declared inline in a plugin's plugin.json

**Input**: `specs/291-mcp-inline-servers/` (spec.md, plan.md)

Test first, always: each test task is written, run with the command given, and seen to fail
for the expected reason before the implementation task starts. Run from the repository root
with the interpreter your task names. No absolute local paths, emojis or em-dashes in any
file. Tests build workspaces under `tmp_path` (the autouse `HOME` sandbox in
`tests/conftest.py` holds `installed_plugins.json`), set `WUWEI_NOW` through the existing
`own_workspace` helper, and never need the real ZIRAN.

## Phase 1: shared test helper (no behaviour change)

- [X] T001 Refactor, `tests/test_mcp.py`: move the PATH-stub ZIRAN script and its install
  out of `test_path_stub_init_then_description_drift_before_morning_launch` into a
  module-level helper `ziran_stub(tmp_path, monkeypatch)` (writes `tmp_path / 'ziran'` with
  `'#!' + sys.executable`, `chmod 0o755`, prepends `tmp_path` to `PATH`); the script body is
  unchanged. That test calls the helper. Run
  `python -m pytest -q tests/test_mcp.py -k path_stub`; it stays green.

## Phase 2: tests for US1 and US2 (all must fail before Phase 3)

- [X] T002 [US1] Test, `tests/test_mcp.py`
  (`test_issue_acceptance_inline_plugin_server_registered_expanded_and_drift`): `plugin =
  tmp_path / 'other'` with `.claude-plugin/plugin.json` =
  `{'name': 'other', 'mcpServers': {'docs': {'command': '${CLAUDE_PLUGIN_ROOT}/server', 'description': 'approved'}}}`
  and no `.mcp.json`; `root = own_workspace(tmp_path, monkeypatch, plugin)`, then config
  `[adapters]\nscanner="ziran"\n`; `ziran_stub(tmp_path, monkeypatch)`. Assert:
  `discover(root, config) == [manifest.resolve()]`; `cached(root).exit == 2`;
  `check(root).exit == 0`; exactly one `.wuwei/ziran/plugins/*.json` whose
  `mcpServers.docs.command == str(plugin.resolve()) + '/server'` and whose text has no
  `${CLAUDE_PLUGIN_ROOT}`; exactly one `.wuwei/ziran/snapshots/*/docs.json`, text
  `approved`. Then replace `approved` with `UNTRUSTED CHANGE` in plugin.json:
  `check(root).exit == 1`, still exactly one `snapshots/*/docs.json` (same key, drift not
  re-registration), a `decisions/D-*.md` exists under the day, `cached(root).exit == 1`,
  and `UNTRUSTED CHANGE` is not in the day's `events.jsonl`. Run
  `python -m pytest -q tests/test_mcp.py -k inline_plugin_server` (fails: `discover` returns
  `[]`).
- [X] T003 [US1] Test, `tests/test_mcp.py` (`test_inline_plugin_servers_invalid_fail_closed`,
  parametrized `mcpServers` over `'./servers.json'`, `['./servers.json']`,
  `{'docs': 'fake'}`): a plugin whose plugin.json has that value, scanner `ziran` (no stub
  needed): `check(root)` is exit 2 with `unmeasured` in the reason and `cached(root)` is
  exit 2. Run `python -m pytest -q tests/test_mcp.py -k inline_plugin_servers_invalid`
  (fails: exit 0, the file is never read).
- [X] T004 [US2] Test, `tests/test_mcp.py`: in
  `test_own_server_and_source_checkout_attach_no_discoverable_file` keep every existing
  assertion and replace `assert core().check(root).exit == 0` with
  `result = core().check(root)`, `result.exit == 0` and
  `'covered by plugin integrity' in result.reason`. Run
  `python -m pytest -q tests/test_mcp.py -k own_server` (fails: empty reason).
- [X] T005 [US2] Test, `tests/test_mcp.py`
  (`test_cockpit_lookalike_inline_in_another_plugin_is_measured`, parametrized `server`
  over `COCKPIT` and `{**COCKPIT, 'command': '/bin/sh'}`): `plugin = tmp_path / 'plugin'`
  with `.claude-plugin/plugin.json` = `{'name': 'wuwei', 'mcpServers': {'cockpit': server}}`;
  `root = own_workspace(tmp_path, monkeypatch, plugin)` (scanner `none`, `PLUGIN` not
  patched). Assert `discover == [path.resolve()]`, `cached(root).exit == 2`,
  `check(root)` exit 2 with `unmeasured` in the reason, `launch(root).exit == 2`. Then
  `monkeypatch.setattr(core(), 'PLUGIN', plugin.resolve())` (that install is now WUWEI's):
  `discover == []` and `'covered by plugin integrity' in check(root).reason`. Run
  `python -m pytest -q tests/test_mcp.py -k lookalike_inline` (fails: `discover` returns
  `[]` in the first half).

## Phase 3: implementation

- [X] T006 [US1][US2] Implement, `cli/wuwei/mcp.py` (plan section 1): `PLUGIN` import,
  `COVERED`, `discover(root, config, covered=None)` with the plugin.json source and the own
  skip, `_expanded(root, path)`, and the three edits in `check`. Run
  `python -m pytest -q tests/test_mcp.py tests/test_board_mcp.py`: T002 to T005 pass and
  every #281 test (`test_cockpit_lookalike_file_stays_unmeasured_and_refused`,
  `test_plugin_json_declares_one_stdio_server`) passes unchanged.

## Phase 4: docs and finish

- [X] T007 Docs, `docs/site/configuration.md` section "MCP registry checks (S3)" (plan
  section 3): both plugin sources, `${CLAUDE_PLUGIN_ROOT}` expansion in a copy under
  `.wuwei/ziran/plugins`, WUWEI's own plugin.json reported as covered by plugin integrity,
  any other plugin's servers (lookalike cockpit included) checked.
- [X] T008 Run the full suite `python -m pytest -q`; everything passes. Check every file
  written for em-dashes, emojis and absolute local paths and remove any.

## Phase 5: review fixes

- [X] T009 [US2] Review F1, F2: tests `test_symlinked_signed_manifest_in_another_plugin_is_measured`
  and `test_only_plugin_manifest_sources_are_expanded` in `tests/test_mcp.py` fail first;
  then `discover` decides coverage by `directory.resolve() == PLUGIN`, keys each plugin
  manifest by its install directory and reports those keys in a `plugins` set, and `check`
  expands exactly those entries.
