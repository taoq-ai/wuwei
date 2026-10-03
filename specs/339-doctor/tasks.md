# Tasks: wuwei doctor

**Input**: `specs/339-doctor/` (spec.md, plan.md)

Test first, always: each test task is written, run with the command given, and seen to fail
for the expected reason before its implementation task starts. Run from the repository
root with the interpreter your task names. No absolute local paths, client names, emojis
or em-dashes in any file. Tests build workspaces under `tmp_path`, rely on the autouse
`HOME` sandbox in `tests/conftest.py`, set `WUWEI_WORKSPACE` and `WUWEI_NOW`, and never
need the network, the real `gh`, the real ZIRAN, a real service manager or a terminal.

Before T001, confirm on main what the chain landed and note it in the spec's Assumptions
if it differs: #324 (`.in_use` pruning in `integrity.py`), #326 (the `repos` hint text in
`workspace.load_config` and `init._without_empty_repos`), #328 (`config promote` fills
`fast_checks = []`), #329 (`classic protection: none visible` in `config check`), #327
(`commands/setup.py`, and a `config set` path with a `confirm` parameter). Whatever is
missing becomes a Deferred entry and its rows stay printed fixes.

## Phase 1: the command, rows and exit rule

- [X] T001 Test, `tests/test_doctor.py`: fixture `ws` as in plan "Test approach" (fake
  plugin directory with `bin/wuwei` executable, `hooks/hooks.json`,
  `.claude-plugin/plugin.json` and `MANIFEST.sha256.sig`; an installed plugins file in the
  sandboxed `HOME` listing it; `heartbeat.measure` replaced by ok probes; the `Service`
  fake for `registry.watch_service`; `registry.load` fakes for `host`, `code_host` and
  `vcs`; a `bin/` on `PATH` with stubs for `gh`, `launchctl`, `systemctl`; one repository
  `acme/widget` under `tmp_path` with `.git/`, `fast_checks = ["ruff check ."]`, an
  identity, today's MCP record with no servers, `.wuwei/calibration.json`, and the watch
  unit file at `workspace.watch_unit(root)[1]` with a watch clock event today). Tests:
  `test_outcome_findings_before_unmeasured` (`outcome` over row lists: warn or fail gives
  1 even with an unmeasured row; only unmeasured gives 2; all ok gives 0) and
  `test_fix_allow_list_is_pinned` (`set(doctor.FIXES) == {'integrity-reconfirm',
  'init-upgrade', 'config-promote', 'calibrate', 'watch-install', 'listen-install',
  'config-set'}`, without `config-set` if #327 is absent). Run
  `python -m pytest -q tests/test_doctor.py` (fails: no module).
- [X] T002 Implement, `cli/wuwei/commands/doctor.py`: `SECTIONS`, `DOCS`, `CODES`,
  `_row`, `_capture`, `outcome`, `render`, `register`, `run`, and `FIXES` with its seven
  ids whose preview and apply are stubs raising `NotImplementedError` until T024. Rerun
  T001; passes.

## Phase 2: US1, the rows

- [X] T003 [US1] Test, `tests/test_doctor.py` (`test_install_rows`): healthy fixture gives
  `ok` rows `plugin` (path, version, `signed release`), `integrity`, `in_use` (`0 ...
  (expected)`), `hooks` (`registered in Claude Code`), `launcher`, `python`. Then: a real
  `PLUGIN/.in_use/12345` file is `ok` `1 Claude Code process markers (expected)` and adds
  no finding; the plugin missing from the installed plugins file is `fail` with
  `/plugin install wuwei@wuwei in Claude Code`; a `.git/` checkout missing from it is `ok`
  `development checkout ...`; `integrity.fresh` faked to
  `Result(2, reason='page: plugin integrity: .in_use/12345')` on a release is `fail` with
  the review-or-reinstall fix and no `apply`; on a checkout (`.git/` present, no `.sig`) it
  has fix `wuwei integrity reconfirm` and `apply == 'integrity-reconfirm'`. Run
  `python -m pytest -q tests/test_doctor.py -k install` (fails).
- [X] T004 [US1] Implement `_install` in `cli/wuwei/commands/doctor.py` (plan section 1).
  Rerun T003; passes.
- [X] T005 [US1] Test, `tests/test_doctor.py` (`test_host_rows`, parametrized): `gh`
  absent from `PATH` is `fail` with the install fix; `auth_status` exit 1 is `fail`
  `gh auth login`, exit 2 `unmeasured`; `adapters.code_host = "none"` is `ok`
  `not used`; vcs `identity` exit 2 is `fail` with the `git config --global` fix;
  `adapters.scanner = "ziran"` without a `ziran` stub is `fail`; `claude` absent is `ok`
  with inbound `none` and `fail` with inbound `slack`; `adapters.runtime = "codex"`
  without `codex` is `fail`; free memory below `host.free_memory_mb` is `fail`;
  `adapters.host = "none"` is `unmeasured` and appends no event; no `launchctl` or
  `systemctl` stub is `fail`. Run `python -m pytest -q tests/test_doctor.py -k host`
  (fails).
- [X] T006 [US1] Implement `_host` in `cli/wuwei/commands/doctor.py`. Rerun T005; passes.
- [X] T007 [US1] Test, `tests/test_doctor.py` (`test_workspace_rows` and
  `test_no_workspace`): with no `.wuwei/` above `cwd` and no `WUWEI_WORKSPACE`, Install and
  Host rows are present, Workspace is one `fail` row naming `wuwei setup --shadow`, Guards
  has only `outside workspace`, exit 1. In the fixture: `repos = []` above a `[[repos]]`
  table is a `fail` `config` row whose value carries the #326 hint, fix
  `wuwei init --upgrade`, `apply == 'init-upgrade'`, and the Gates and Day sections are one
  `unmeasured` row each; an unknown key is `fail` with `edit .wuwei/config.toml: ...` and
  no `apply`; `init.upgrade` faked to print `Would upgrade config.toml: add x` gives a
  `warn` `template` row with that detail and `apply == 'init-upgrade'`, and a
  `Charter override needs review: lead.md ...` line gives a separate `warn` row without
  `apply`; a missing repository path, a path without `.git`, a default branch the vcs
  stub does not list, an empty identity the vcs stub resolves (`warn`, `config set` fix,
  `apply == 'config-set'` when present), and `fast_checks = []` (`warn`,
  `wuwei config promote`, `apply == 'config-promote'`) each give their row; no
  `calibration.json` is `warn`; a `calibration.drift` event today is `warn` with
  `apply == 'calibrate'`; shadow mode 3 of 7 days is `ok` `shadow, 4 days left`, 8 days is
  `warn` without `apply`. Run `python -m pytest -q tests/test_doctor.py -k "workspace"`
  (fails).
- [X] T008 [US1] Implement `_workspace` and the root and config resolution in `diagnose`,
  `cli/wuwei/commands/doctor.py`. Rerun T007; passes.
- [X] T009 [US1] Test, `tests/test_doctor.py` (`test_gates_rows`): the code host fake's
  protection result for a classic 404 (the #329 shape; before #329, the
  `branch protection absent` result) makes the `config check` row `fail`, `exit 1`, with
  the `acme/widget main: ...` lines as detail; an unreadable protection result makes it
  `unmeasured`; an MCP record for today with `unmeasured: [["docs", <digest>]]` gives a
  `warn` `docs: unmeasured` row with `wuwei mcp decide proceed-unmeasured docs`; a
  `decided` pair is `ok` `proceeding unmeasured by owner decision`; a reason note
  `remote: not attached (unapproved)` is an `ok` row with that note; a pending decision
  makes `mcp gate` `fail`; a record from yesterday with a discoverable `.mcp.json` makes
  `mcp gate` `unmeasured` with `wuwei mcp check`. Run
  `python -m pytest -q tests/test_doctor.py -k gates` (fails).
- [X] T010 [US1] Implement `_gates` in `cli/wuwei/commands/doctor.py`. Rerun T009; passes.
- [X] T011 [US1] Test, `tests/test_doctor.py` (`test_day_rows`): heartbeat `state` probe
  `failed` is `fail` with `wuwei state recover in a host terminal`; `planner` `failed` is
  `fail` with the take-over fix; no watch unit and no clock is `warn` `not installed` with
  `apply == 'watch-install'`; a stale clock is `fail` (dead); inbound `none` gives
  listener `ok` `not used`; a `heartbeat: clock` event with health `degraded` today is
  `fail`; one open page event gives one `fail` row named by its source with fix
  `wuwei nudges`; nudges are an `ok` count. Run
  `python -m pytest -q tests/test_doctor.py -k day` (fails).
- [X] T012 [US1] Implement `_day` in `cli/wuwei/commands/doctor.py`. Rerun T011; passes.
- [X] T013 [US1] Test, `tests/test_doctor.py` (`test_guards_rows`): the four hook probes
  map `ok`, `failed` (`fail` with the reinstall fix) and `unmeasured`; the outside probe
  calls the `Service` fake once with argv `('hook', 'PreToolUse')`, a `cwd` that is not
  under `tmp_path / 'ws'`, and a payload whose `cwd` equals it, whose `session_id` is
  `HEARTBEAT_SESSION` and whose command is a heredoc mentioning `gh`; exit 0 is `ok`,
  exit 2 is `fail` with the upgrade fix, `None` is `unmeasured`. Run
  `python -m pytest -q tests/test_doctor.py -k guards` (fails).
- [X] T014 [US1] Implement `_guards` in `cli/wuwei/commands/doctor.py`. Rerun T013;
  passes.
- [X] T015 [US1] Test, `tests/test_doctor.py`: `test_healthy_workspace_exits_zero`
  (`main(['doctor'])` returns 0, every section header printed in order, no `fix:` line,
  last line `doctor: ok`, and no file under `.wuwei/` changed: compare a listing with
  mtimes before and after, ignoring today's `state.lock`);
  `test_json_rows` (`main(['doctor', '--json'])` prints one object whose `exit` equals the
  return value and whose rows carry `section`, `name`, `status`, `value`, with `fix` and
  `docs` only on non-ok rows); `test_fix_and_json_are_exclusive` (exit 2, nothing
  written). Run `python -m pytest -q tests/test_doctor.py -k "healthy or json"` (fails).
- [X] T016 [US1] Implement `diagnose` (sections in order, one heartbeat call, Gates and
  Day collapsed when config does not load) and the `--json` path of `run`,
  `cli/wuwei/commands/doctor.py`. Rerun T015; passes.
- [X] T017 [US1] Test, `tests/test_doctor.py` (`test_trial_failures_then_clean`, the
  issue's first acceptance): in the fixture, the integrity probe faked with the trial
  reason on a release, `repos = []` above the `[[repos]]` table, today's MCP record with
  an unmeasured approved server, `fast_checks = []`, and the classic 404 protection
  result with no rules. Run 1: exit 1; `integrity` and `config` rows carry
  `wuwei integrity reconfirm` and `wuwei init --upgrade`. Apply the config fix by
  rewriting the file without `repos = []`. Run 2: exit 1; rows carry
  `wuwei mcp decide proceed-unmeasured <server>`, `wuwei config promote`, and the
  `config check` detail lines for the classic 404. Apply the printed fixes by fixture
  (integrity verdict clean, the server moved to `decided`, `fast_checks` filled, a
  protected-branch result). Run 3: exit 0. Also `test_unapproved_server_is_ok` (a record
  whose reason notes `remote: not attached (unapproved)` and nothing else is exit 0). Run
  `python -m pytest -q tests/test_doctor.py -k "trial or unapproved"`; fix any gap in
  T004 to T016 until it passes.

## Phase 3: US2, `--fix`

- [X] T018 [US2] Test, `tests/test_doctor.py` (`test_doctor_fixed_is_reserved`):
  `main(['event', 'doctor.fixed', '{}'])` returns 1 and stderr names
  `owner host wuwei doctor --fix`. Run
  `python -m pytest -q tests/test_doctor.py -k reserved` (fails: generic producer text).
- [X] T019 [US2] Implement, `cli/wuwei/commands/event.py`: the `EVENT_PRODUCERS` entry.
  Rerun T018; passes.
- [X] T020 [US2] Test, `tests/test_doctor.py` (`test_fix_reconfirms_development_checkout`,
  the issue's third acceptance): a checkout fixture whose `integrity.fresh` reports
  `development checkout requires host reconfirmation`; `integrity.check` faked to return
  `Result(1, 'f' * 64, ...)`; `integrity.reconfirm` replaced by a recorder that calls its
  `confirm` with `'f' * 64` and with `'0' * 64` and returns `Result(0)` only when the first
  is True and the second False, and makes `fresh` clean afterwards. Call
  `doctor.run(Namespace(fix=True, json=False), confirm=typed)` where `typed` records the
  digest and returns True. Assert: the batch printed `[integrity-reconfirm] wuwei
  integrity reconfirm` and the fingerprint before `typed` was called; one `doctor.fixed`
  event `{'fix': 'integrity-reconfirm', 'exit': 0}`; the second report has an `ok`
  integrity row; return 0. Run `python -m pytest -q tests/test_doctor.py -k reconfirms`
  (fails).
- [X] T021 [US2] Test, `tests/test_doctor.py`: `test_fix_applies_only_the_allow_list`
  (rows with an MCP `warn`, a shadow `warn`, a state `fail` and a row injected with
  `apply = 'mcp-decide'` through a faked `diagnose`: none is applied, each is printed under
  `Not applied` with its fix, and no event is written);
  `test_fix_dedupes` (two repositories with `fast_checks = []`: one `[config-promote]`
  entry, promote previewed once and applied once);
  `test_fix_wrong_digest_applies_nothing` (`confirm` returns False: exit 1, stderr
  `declined; nothing applied`, no apply call, no event);
  `test_fix_without_terminal` (`integrity._host_confirm` raising
  `OSError(integrity.HOST_TERMINAL)`: exit 2 with that message, nothing applied);
  `test_fix_changed_since_preview` (`init.upgrade` faked so the dry run prints a different
  plan the second time: `init-upgrade: exit 1` with `changed since the preview`, the real
  upgrade never runs, the other fixes in the batch still run);
  `test_fix_binds_promote_digest` (`config.promote` faked to call its `confirm` with a
  digest that differs at apply time: promote declines and writes nothing). Run
  `python -m pytest -q tests/test_doctor.py -k fix_` (fails).
- [X] T022 [US2] Test, `tests/test_doctor.py` (`test_fix_installs_watch`): a fixture
  without the watch unit and `workspace.watch_unit` pointed under `tmp_path`, the
  `Service` fake recording `call`: the batch shows the dry-run unit text, apply writes the
  unit and calls the fake service manager, the event is written, the second report has no
  `watch` `warn`. Run `python -m pytest -q tests/test_doctor.py -k installs_watch`
  (fails).
- [X] T023 [US2] Test, `tests/test_doctor.py` (`test_fix_nothing_to_apply`): a healthy
  fixture with `--fix` prints `Nothing to apply`, never calls `confirm`, returns 0. Run
  `python -m pytest -q tests/test_doctor.py -k nothing_to_apply` (fails).
- [X] T024 [US2] Implement `FIXES` previews and applies, and `fix`,
  `cli/wuwei/commands/doctor.py` (plan section 1, `fix` steps 1 to 8). Rerun T020 to T023
  and T017; all pass.

## Phase 4: US4, docs and setup

- [X] T025 [US4] Test, `tests/test_docs.py`
  (`test_doctor_is_the_first_stop`): `recovery.md` and `daily.md` contain
  `bin/wuwei doctor`; `reference.md` has `## Doctor`, and that section names every
  command in `doctor.FIXES` and the words `/dev/tty` and `doctor.fixed`. The existing
  `test_reference_lists_every_cli_command` already fails without the Commands row. Run
  `python -m pytest -q tests/test_docs.py` (fails).
- [X] T026 [US4] Docs, `docs/site/reference.md`, `docs/site/recovery.md`,
  `docs/site/daily.md` (plan section 4). Rerun T025; passes.
- [ ] T027 (deferred: #327 is not on main) [US4] Only if `cli/wuwei/commands/setup.py` is on main. Test, the setup test
  file #327 added: after a confirmed setup run, stdout ends with the doctor report (its
  last line starts `doctor:`) and setup's exit is unchanged. Run it (fails).
- [ ] T028 (deferred: #327 is not on main) [US4] Only with T027. Implement, `cli/wuwei/commands/setup.py`: the last step
  prints `doctor.render(doctor.diagnose())`. Rerun T027; passes. Without #327 on main,
  record "setup ends by running doctor" under Deferred instead.

## Phase 5: finish

- [X] T029 Run `python -m pytest -q` from the repository root; everything passes. Check
  every file this item touched for em-dashes, emojis and absolute local paths, and
  remove any.
