# Tasks: Keys from a newer template warn instead of refusing, and setup and doctor say when to restart Claude Code

Test first: run each test task, see it fail for the stated reason, then do the
implementation task that follows it. Run tests with `python -m pytest -q <file>` from the
repository root using the interpreter the task names. Signatures, texts and placement are
in plan.md.

New tests go in `tests/test_config_transition.py` unless a task names another file.
Fixtures there: a workspace at `tmp_path / 'ws'` whose `.wuwei/config.toml` is the shipped
template text plus the edits each test names, integrity seeded with
`fakes.integrity.seed`, `WUWEI_WORKSPACE` removed; a fake plugin directory
`tmp_path / 'cache' / '<version>'` with `.claude-plugin/plugin.json` =
`{"name": "wuwei", "version": "<version>"}`, monkeypatched as `integrity.PLUGIN`; markers
are `.in_use/<os.getpid()>` files. Replay hooks in process as in
`tests/test_config_failure.py` (`sys.stdin` patched, `hook.run(SimpleNamespace(event=...))`,
`capsys`). Neutral names only.

## Phase 1: Unknown keys warn below strict (US1; FR-001, FR-002, FR-003, FR-005)

- [X] T001 In `tests/test_config_transition.py`, add failing tests:
  (a) `[scanner.mcp]` gains `blok = ["high"]` under the default posture:
  `load_config(root, warnings=found)` returns a config and `found == ['config.toml:
  unknown key scanner.mcp.blok at line <n>; did you mean scanner.mcp.block?']` (n from
  the written text);
  (b) the same with `security.posture = "strict"` raises `ConfigError` with that text;
  (c) `nonsense = 1` under strict raises with `remove it or use a documented key`;
  (d) a PreToolUse Bash `ls` with (a)'s config exits 0 and stdout has no `deny`; with
  (b)'s config it denies with the unknown-key text;
  (e) `posture = "observe"` and `guards.mode = "shadow"` both behave as (a);
  (f) `template_version = "0.1.0"` loads with no warning.
  Fails today: `load_config` has no `warnings` and raises in every posture.
- [X] T002 In `cli/wuwei/workspace.py`, add `template_version` to `SCHEMA`, the `unknown`
  parameter and nearest key in `_validate`, and the posture decision, memo and
  `warnings` in `load_config` (plan.md 1, without the newer-template check yet). In
  `tests/test_workspace.py` and `tests/test_config_failure.py`, update the four tests
  plan.md "Tests that change" names. T001 passes; run `tests/test_workspace.py`,
  `tests/test_config_failure.py`, `tests/test_profiles.py`, `tests/test_calibrate.py`.
- [X] T003 In `tests/test_config_transition.py`, add failing tests: with (a)'s config and
  `WUWEI_WORKSPACE` set, `wuwei.commands.config.run` prints
  `wuwei config check: warning: config.toml: unknown key scanner.mcp.blok` to stderr
  (fake `code_host` through `registry.load` as `tests/test_doctor.py` does, so no `gh`);
  in `tests/test_doctor.py`, with the `ws` fixture config plus a typo key, the
  Workspace `config` row is `warn`, value `loads; 1 unknown keys`, detail the warning.
  Fails today: no warning output, the row is `fail`.
- [X] T004 In `cli/wuwei/commands/config.py` `run` and `cli/wuwei/commands/doctor.py`
  `diagnose` and `_workspace`, pass and print the warnings (plan.md 5, 6). T003 passes;
  run `tests/test_doctor.py`.

## Phase 2: Version helpers and the old hook (US2; FR-002, FR-004, FR-006)

- [X] T005 In `tests/test_config_transition.py`, add failing tests for
  `cli/wuwei/integrity.py`: `version()` reads the fake `plugin.json` and is `''` when it
  is missing; `release('0.13.0') == (0, 13, 0)` and `release('')`, `release('1.x')` are
  None; `newer_template({'template_version': '0.13.0'})` with plugin `0.12.0` is
  `('0.12.0', '0.13.0')` and None for `'0.12.0'`, `'0.11.0'`, `''`, `'dev'`;
  `other_versions()` with `cache/0.12.0/.in_use/<pid>` and `cache/0.13.0/.in_use/<pid>`,
  `PLUGIN` = `cache/0.13.0`, is `['0.12.0']`, and `[]` when the sibling's `.in_use` is
  empty or absent; `restart(config)` builds the plan.md 2 text for both triggers and is
  `''` with neither. Fails today: no such functions.
- [X] T006 In `cli/wuwei/integrity.py`, add `RESTART`, `version`, `release`,
  `newer_template`, `other_versions`, `restart` (plan.md 2). T005 passes.
- [X] T007 In `tests/test_config_transition.py`, add the failing acceptance test of US2:
  plugin `0.12.0`, config with `template_version = "0.13.0"`, `security.posture =
  "strict"` and `blok = ["high"]` under `[scanner.mcp]`; two PreToolUse Bash `ls` calls
  with one `session_id` both exit 0 with no deny; today's `events.jsonl` holds exactly
  one `config.newer_template` with `{"plugin": "0.12.0", "template": "0.13.0",
  "session": <id>}`; a second session adds one more; the `wuwei-heartbeat` session adds
  none; with `template_version = "0.12.0"` the call denies and no event is written.
  Also `wuwei.commands.event.run` with kind `config.newer_template` returns 1 (reserved).
  Fails today: the call denies, no event.
- [X] T008 In `cli/wuwei/workspace.py` `load_config`, add the `integrity.newer_template`
  exception to the strict raise; in `cli/wuwei/commands/hook.py`, add the
  `newer_template` recorder in the `CONFIG_EVENTS` block; in
  `cli/wuwei/commands/event.py`, reserve the kind (plan.md 1, 3, 4). T007 passes; run
  `tests/test_config_failure.py`, `tests/test_hooks.py`, `tests/test_posture.py`,
  `tests/test_docs.py`.
- [X] T009 In `tests/test_doctor.py`, add failing tests with the `ws` fixture: (a) a
  sibling `ws.plugin.parent / '0.10.0' / '.in_use' / str(os.getpid())` makes the
  `in_use` row `warn` with value
  `plugin 0.10.0 running against template 0.11.0: restart Claude Code` and fix
  `integrity.RESTART`; (b) no sibling but config `template_version = "0.12.0"` (fixture
  plugin is `0.11.0`) gives `plugin 0.11.0 running against template 0.12.0: restart
  Claude Code`. In `tests/test_signal_status.py` (or wherever `status.line` is tested),
  `status.line` with `restart` set contains that text and without it is unchanged.
  Fails today: the row is always ok, the line has no restart part.
- [X] T010 In `cli/wuwei/commands/doctor.py` `_install` and
  `cli/wuwei/commands/status.py` `snapshot` and `line`, use `integrity.restart`
  (plan.md 6, 7). T009 passes; run `tests/test_doctor.py`, `tests/test_signal_status.py`.

## Phase 3: Writing the version and the restart line (US3; FR-007, FR-008)

- [X] T011 In `tests/test_config_transition.py`, add failing tests for `init._stamp` with
  plugin `0.13.0`: replaces `template_version = ""` and `"0.12.0"`; prepends the line
  when absent (the result parses and `template_version` is top-level); leaves `"0.14.0"`
  and the text unchanged; no-op when `version()` is `''`. In `tests/test_workspace.py`:
  `init` writes `template_version` equal to the repository's `.claude-plugin/plugin.json`
  version and a following `init --upgrade` prints `No workspace changes needed`; a
  previous-version workspace without the key gets `Upgraded config.toml:
  template_version <version>` and `--dry-run` writes nothing. Fails today: no
  `_stamp`, no key.
- [X] T012 In `cli/wuwei/commands/init.py`, add `_stamp` and use it in `run` and
  `upgrade`, with the upgrade warnings (plan.md 8, without the restart line yet); in
  `templates/workspace/config.toml`, the comment and the `template_version` line
  (plan.md 10). T011 passes; run `tests/test_workspace.py`, `tests/test_docs.py`,
  `tests/test_profiles.py`, `tests/test_templates_errors.py`.
- [X] T013 In `tests/test_config_transition.py` (or `tests/test_setup.py` with its
  `project`, `host`, `terminal` fixtures), add failing tests: with
  `integrity.PLUGIN` = `cache/0.13.0` and a marker in `cache/0.12.0/.in_use`, `setup`'s
  last stdout line is `integrity.RESTART`, and `init --upgrade`'s last stdout line is
  too; without the sibling marker neither prints it; `init --upgrade --dry-run` never
  prints it; `setup` on a workspace without `template_version` shows the stamp in its
  proposal. In `tests/test_docs.py` (or a new assertion in the transition file),
  `.github/workflows/release.yml` contains `integrity.RESTART` and `append_body: true`.
  Fails today: no restart line, no stamp, no workflow body.
- [X] T014 In `cli/wuwei/commands/setup.py` (`run` finally, `_setup` stamp),
  `cli/wuwei/commands/init.py` (`upgrade` restart line) and
  `.github/workflows/release.yml` (plan.md 8, 9, 10). T013 passes; run
  `tests/test_setup.py`, `tests/test_workspace.py`.

## Phase 4: Marker exclusion across an upgrade (US4)

- [X] T015 In `tests/test_integrity.py`, add a test next to
  `test_in_use_markers_do_not_change_measure`: two signed plugin directories
  `cache/0.12.0` and `cache/0.13.0` (the existing `plugin` helper and faked signature
  adapter), `.in_use/12345` in one and `.in_use/23456` in the other after signing;
  `measure(plugin=...)` on each exits 0 with the fingerprint measured before the
  markers; with `integrity.PLUGIN` set to each, `other_versions()` names only the
  other. Expected to pass on first run (verification of #324 on the upgraded path); if
  it fails, fix `_prune` only for the reason it names.

## Phase 5: Docs and the full suite (FR-009)

- [X] T016 In `docs/site/configuration.md` and `docs/site/reference.md`, the edits of
  plan.md 10. Run `tests/test_docs.py`.
- [X] T017 Run `python -m pytest -q` from the repository root; everything passes. Check
  every file you wrote for em-dashes, emojis and absolute local paths.
