# Tasks: A broken config.toml can be read and fixed from the session

Test first: run each test task, see it fail for the stated reason, then do the
implementation task that follows it. Run tests with `python -m pytest -q <file>` from the
repository root using the interpreter the task names. Signatures, texts and placement are
in plan.md.

New tests go in `tests/test_config_failure.py` unless a task names another file. Its
fixture: a workspace at `tmp_path / 'ws'` (so `tmp_path / 'outside'` is outside it) with
`.wuwei/config.toml` =
`'cap = 1\nrepos = []\n[[repos]]\nname = "example/app"\npath = "app"\ndefault_branch = "main"\n'`
(so `repos` is on line 2), `.wuwei/charters/builder.md`, integrity seeded with
`fakes.integrity.seed`, and `WUWEI_WORKSPACE` removed with `monkeypatch.delenv`. Replay
hooks in process: `monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(payload)))`,
`hook.run(SimpleNamespace(event=...))`, `capsys.readouterr()` (the pattern of
`tests/test_records_after_dryrun4.py::test_config_error_names_config_toml`). Payloads carry
`session_id`, `transcript_path`, `cwd` (the workspace unless a task says otherwise),
`hook_event_name`, `tool_name` and `tool_input`. Use neutral names only.

## Phase 1: The hint (US3, FR-003, FR-005)

- [X] T001 In `tests/test_config_failure.py`, add failing tests:
  (a) `workspace.load_config(root)` raises `ConfigError` whose text starts with
  `config.toml: Cannot mutate immutable namespace ('repos',)` and contains
  `repos is assigned on line 2; delete that line before using [[repos]] tables`;
  (b) with `WUWEI_WORKSPACE` set to the workspace, `wuwei.commands.config.run(SimpleNamespace())`
  returns 1 and stderr contains that same fix text;
  (c) `'nonsense = 1\n'` still raises `unknown key nonsense` with no `repos is assigned`.
  Fails today: no hint.
- [X] T002 In `cli/wuwei/workspace.py` `load_config`, add the hint in the `except` and the
  keyword-only `raw` parameter (plan.md 1). T001 passes; run `tests/test_workspace.py` and
  `tests/test_records_after_dryrun4.py`.

## Phase 2: The template (US3, FR-004)

- [X] T003 In `tests/test_config_failure.py`, add a failing test: the template text
  (`templates/workspace/config.toml`) parsed with `tomllib` has no `repos` key; the
  template plus `'\n[[repos]]\nname = "example/app"\npath = "app"\ndefault_branch = "main"\n'`
  written as a workspace `config.toml` loads with `load_config`, and
  `config['repos'][0]['name'] == 'example/app'`. Fails today: the immutable-namespace error.
- [X] T004 In `templates/workspace/config.toml`, delete `repos = []` and reword the comment
  (plan.md 3). In `tests/test_workspace.py`, re-anchor
  `test_upgrade_preserves_nonadjacent_repo_tables` on `'[prioritisation]\n'` (plan.md,
  Tests that change). T003 passes; run `tests/test_docs.py` and `tests/test_workspace.py`.

## Phase 3: The hook failure mode (US1, US2; FR-001, FR-002, FR-007)

- [X] T005 In `tests/test_config_failure.py`, add failing PreToolUse tests with the broken
  fixture:
  (a) `Read` with `file_path` the absolute `.wuwei/config.toml` exits 0 and stdout is empty;
  (b) each of: `Read` of relative `.wuwei/charters/builder.md`, `Grep` with `path`
  `.wuwei/config.toml`, `Glob` with `path` `.wuwei/charters`, `ToolSearch` with
  `{'query': 'select:Read'}` exits 0;
  (c) `Bash` `{'command': 'ls'}` exits 2, stdout is one deny decision whose
  `permissionDecisionReason` starts with `config.toml:`, contains
  `repos is assigned on line 2`, and has no `outward:` line;
  (d) each of: `Write` of `.wuwei/config.toml`, `Read` of `notes.md` in the workspace,
  `Grep` with no `path`, `Agent`, and `mcp__example__send_message` exits 2 with that same
  reason;
  (e) after (c), today's `events.jsonl` (`workspace.day_dir(root)`) holds a `hook.refusal`
  whose `reason` is that reason;
  (f) cwd `tmp_path / 'outside'` (created, no `.wuwei`): `Read` of the workspace's
  absolute `.wuwei/config.toml` exits 0, and `Bash` `ls` exits 0.
  Fails today: (a), (b) and (f) exit 2; (c) carries a second `outward:` reason.
- [X] T006 In `tests/test_config_failure.py`, add a failing Stop test with the broken
  fixture (`stop_hook_active` false): exit 0, stdout empty, and stderr contains
  `repos is assigned on line 2` exactly once (`stderr.count('config.toml:') == 1`).
  Fails today: exit 2 with a block decision.
- [X] T007 In `cli/wuwei/commands/hook.py`, add `CONFIG_EVENTS`, `REPAIR_READS`,
  `config_failure`, `repair_read`, the config load after `env.load(root)` and the
  `ConfigError` branch at the top of the discovery `except` (plan.md 2). T005 and T006
  pass; run `tests/test_hooks.py`, `tests/test_records_after_dryrun4.py`,
  `tests/test_shadow.py` and `tests/test_stop.py`.

## Phase 4: init --upgrade repair (US4, FR-006)

- [X] T008 In `tests/test_workspace.py`, next to the upgrade tests, add failing tests using
  `previous_workspace` with `'\n[[repos]]\nname = "app"\npath = "repo"\ndefault_branch = "main"\n'`
  appended to its `config.toml` (so `repos = []` stays on line 4):
  (a) `init --upgrade --dry-run` exits 0, stdout contains
  `Would upgrade config.toml: remove repos = []`, and no file under `.wuwei` changed;
  (b) `init --upgrade` exits 0, stdout contains `Upgraded config.toml: remove repos = []`,
  the file has no `repos = []` line, still has `# Owner comment stays.`, `tomllib` loads it
  with `repos[0]['name'] == 'app'`;
  (c) a second `init --upgrade` prints `No workspace changes needed` and changes nothing;
  (d) in `test_upgrade_previous_workspace` (no tables), assert the upgraded file still
  contains the line `repos = []`.
  Fails today: (a) and (b) exit 2 on the TOML error.
- [X] T009 In `cli/wuwei/commands/init.py`, add `_without_empty_repos` and use it in
  `upgrade` (plan.md 3). T008 passes; run `tests/test_workspace.py`.

## Phase 5: Docs and finish

- [X] T010 In `docs/site/configuration.md`, add the paragraph after the minimal
  `[[repos]]` example (plan.md 4). Run `tests/test_docs.py`.
- [X] T011 Run the full suite (`python -m pytest -q`), then the hook latency tests with
  `WUWEI_BENCH=1` (`python -m pytest -q tests/test_hooks.py -k latency`). Check every file
  you wrote for em-dashes, emojis and absolute local paths.
