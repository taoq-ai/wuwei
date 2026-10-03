# Tasks: the registry gate warns by default, scans only servers that attach, one server at a time, and never launches unpinned third-party code

**Input**: `specs/325-mcp-attached-servers/` (spec.md, plan.md, data-model.md)

Test first, always: each test task is written, run with the command given, and seen to fail
for the expected reason before its implementation task starts. Run from the repository root
with the interpreter your task names. No absolute local paths, client names, emojis or
em-dashes in any file. Tests build workspaces under `tmp_path`, use the autouse `HOME`
sandbox in `tests/conftest.py` for `~/.claude.json` and `~/.claude/settings.json`, set
`WUWEI_NOW`, and never need the real ZIRAN, network or package launchers (localhost port 9
refuses immediately).

## Phase 1: test helpers (no behaviour change)

- [X] T001 Helper, `tests/test_mcp.py`: `approve(root, *names, key=None)` merges
  `{'projects': {str(key or root): {'enabledMcpjsonServers': [...names]}}}` into
  `Path.home() / '.claude.json'` (keeping any `mcpServers` already there). The `configured`
  fixture calls `approve(root, 'docs')`. Run `python -m pytest -q tests/test_mcp.py`; still
  green (approval is not read yet).
- [X] T002 Helper, `tests/test_mcp.py`: `exec_stub(tmp_path, monkeypatch)` installs a PATH
  ZIRAN stub (same pattern as `ziran_stub`, `'#!' + sys.executable`) that for
  `watch-registry`: appends the config's server names as one JSON line to
  `tmp_path / 'ziran-calls.jsonl'`; for an entry with `url`, tries a TCP connect to its
  host and port and exits 2 without a report when refused; for an entry with `command`,
  runs `[command, *args]` (timeout 5), writes `<snapshot-dir>/<name>.json`, and writes a
  report with one `tool_poisoning` finding for that server when the entry's `description`
  is a severity, exiting 1 for high or critical, else 0. Not used yet.

## Phase 2: configuration keys

- [X] T003 Test, `tests/test_workspace.py`: the defaults dict asserts
  `scanner.mcp.timeout_seconds == 60` and `scanner.mcp.block == ['critical']`; a new
  parametrized case refuses `block = ["severe"]` and `timeout_seconds = 0` with
  `ConfigError` naming the key. Run `python -m pytest -q tests/test_workspace.py` (fails:
  keys unknown).
- [X] T004 Implement, `cli/wuwei/workspace.py` (plan change 1). Rerun T003; passes.

## Phase 3: US1, one server per call and the warn-by-default gate

- [X] T005 [US1] Test, `tests/test_mcp.py`
  (`test_issue_acceptance_two_server_one_unreachable`, parametrized severity `high`,
  `critical`): workspace with goals as in `test_morning_check_before_launch`, scanner
  `ziran`, `exec_stub`, root `.mcp.json` with `docs` (`command` = `sys.executable`,
  `args` = `['-c', 'pass']`, `description` = severity) and `remote`
  (`{'type': 'http', 'url': 'http://127.0.0.1:9/mcp'}`), `approve(root, 'docs', 'remote')`.
  Assert `check(root).exit == 2`, its reason contains `remote:`, `ziran-calls.jsonl` has two
  lines with one server each, today's events hold an `mcp.finding` for `docs`. For `high`:
  `plan.propose` writes `plan.md` whose `- mcp:` line names `remote` and the `D-` decision,
  and `cached(root).exit == 0`. For `critical`: `plan.propose` raises `StateError` matching
  `MCP` and `cached(root).exit == 1`. Run
  `python -m pytest -q tests/test_mcp.py -k two_server` (fails: one call for both servers,
  exit 2 without the name, `propose` raises `OSError`).
- [X] T006 [US1] Test, `tests/test_mcp.py` (`test_posture_block_table`, parametrized):
  with `fake_scanner` (now called once per server) and `[scanner.mcp] block = ...`:
  default plus scanner exit 2 gives `check` 2 and `cached` 0; `["unmeasured"]` plus exit 2
  gives `cached` 2; `[]` plus a critical finding gives `cached` 0 and `check` 1;
  `["high", "critical"]` plus a high finding gives `cached` 1. Could-not-run rows give
  `cached` 2 under `block = []`: a scanner returning a non-`Result`, a stale day, a
  hand-written v0.11.0 `status.json` with `exit` 2 and no new fields; and a v0.11.0 record
  with `pending` gives `cached` 1 under the default. Run
  `python -m pytest -q tests/test_mcp.py -k posture` (fails: every non-zero record blocks).
- [X] T007 [US1] Test, `tests/test_mcp.py` (`test_adapter_failed_run_restores_only_its_snapshot`):
  ZIRAN adapter with `subprocess.run` monkeypatched to write `changed` into the snapshot
  directory it is given and then raise `TimeoutExpired`: that directory's prior content is
  back afterwards (and a directory that did not exist is gone); a run that exits 1 keeps
  `changed`. And core (`test_measured_baseline_kept_while_another_server_unmeasured`):
  with `exec_stub` and the two servers of T005 and no prior snapshots, after `check` (exit 2,
  `remote` unmeasured) the `docs` baseline `snapshots/*/docs.json` still exists. Run
  `python -m pytest -q tests/test_mcp.py -k "restores_only or baseline_kept"` (fails:
  whole-tree restore discards the `docs` baseline).
- [X] T008 [US1] Test, `tests/test_mcp.py` (`test_invalid_server_name_fail_closed`,
  parametrized name `bad name`, `-x`, `a/b`): `check` exit 2, `cached` exit 2 under
  `block = []`. Run `python -m pytest -q tests/test_mcp.py -k invalid_server_name`
  (fails: the name is accepted).
- [X] T009 [US1] Update existing tests in `tests/test_mcp.py` to the per-server contract
  (keep each test's intent): `test_init_registers_and_reports_poisoning` expects one call
  with one `.wuwei/ziran/servers/*.json` file whose `mcpServers` is `{'docs': ...}`;
  `test_morning_check_before_launch` code 2 now writes the plan and the launch refusal is
  the brief one (1); `test_snapshot_recovery_after_timeout_preserves_drift` and
  `test_unmeasured_cannot_be_owner_cleared` use the could-not-run case (a scanner
  returning a non-`Result`); `test_issue_acceptance_inline_plugin_server_registered_expanded_and_drift`
  and `test_only_plugin_manifest_sources_are_expanded` read the expanded server from
  `.wuwei/ziran/servers/` instead of `plugins/`. Confirm these fail now for the expected
  reason.
- [X] T010 [US1] Implement, `cli/wuwei/mcp.py` (plan change 2 without `_approval`,
  `_unpinned` and the `servers` path of `decide`): `NAME`, `SEVERITIES`, `_servers`,
  `_server_file`, `_accepted`, `_read` defaults and validation, `_recover` condition,
  `_gate`, `cached`, the per-server loop in `check`, the decide guard and final update;
  `cli/wuwei/plan.py` (plan change 5); `adapters/scanner/ziran.py` per-file snapshot
  rollback (plan change 3; the timeout is T021). Run
  `python -m pytest -q tests/test_mcp.py tests/test_plan.py tests/test_board_mcp.py`:
  T005 to T009 pass.

## Phase 4: US2, only servers that attach

- [X] T011 [US2] Test, `tests/test_mcp.py` (`test_issue_acceptance_unapproved_never_executed`):
  `exec_stub`; root `.mcp.json` server `writer` with `command` = `sys.executable` and args
  that create `tmp_path / 'sentinel'`; no approval. `check(root).exit == 0`, reason contains
  `writer: not attached (unapproved)`, no sentinel, no line in `ziran-calls.jsonl`. Then
  `approve(root, 'writer')`: `check` runs it and the sentinel exists. Run
  `python -m pytest -q tests/test_mcp.py -k unapproved` (fails: the sentinel is written).
- [X] T012 [US2] Test, `tests/test_mcp.py` (`test_approval_sources`, parametrized, observed
  through `fake_scanner` calls): user `projects[root]` enabled list; user
  `projects[root].enableAllProjectMcpServers` true; `~/.claude/settings.json` enabled list;
  `<root>/.claude/settings.json` `enableAllProjectMcpServers`; `<root>/.claude/settings.local.json`
  enabled list; a configured repo approved under its own path; an item worktree
  `root / 'worktrees' / 'ITEM-1'` approved in user `projects`; all scanned. Not scanned:
  nothing approved; name in `disabledMcpjsonServers` with `enableAllProjectMcpServers`
  true under the same key. A user-scope server in `~/.claude.json` `mcpServers` is scanned
  without approval. Run `python -m pytest -q tests/test_mcp.py -k approval_sources` (fails:
  unapproved servers are scanned).
- [X] T013 [US2] Test, `tests/test_mcp.py` (`test_invalid_approval_state_fail_closed`,
  parametrized: `.claude/settings.local.json` = `{`, `enabledMcpjsonServers` = `"docs"`,
  `enableAllProjectMcpServers` = `"yes"`, user `projects` = `[]`): `check` exit 2 and
  `cached` exit 2 under `block = []`. Run
  `python -m pytest -q tests/test_mcp.py -k invalid_approval` (fails: approval not read).
- [X] T014 [US2] Implement, `cli/wuwei/mcp.py`: `discover(..., projects=None)`, `_approval`,
  step 1 of the `check` loop. Run `python -m pytest -q tests/test_mcp.py`; T011 to T013 pass.

## Phase 5: US3, unpinned launchers

- [X] T015 [US3] Test, `tests/test_mcp.py` (`test_issue_acceptance_unpinned_launcher_never_run`,
  parametrized command and args): unpinned `npx -y pkg@latest`, `npx -y pkg`,
  `uvx awslabs.example@latest`, `uvx pkg`, `pipx run pkg`, command `tools/npx` with
  `pkg@latest`; pinned `npx -y pkg@1.2.3`, `npx -y @scope/pkg@1.2.3`, `uvx pkg==1.2.3`,
  `pipx run pkg==1.2.3`. Put `npx`, `uvx` and `pipx` stubs on `PATH` (and at `tools/npx`)
  that write a sentinel, plus `exec_stub`; approve the server. Unpinned: `check` exit 2,
  reason contains `<name>: unpinned launcher`, no `ziran-calls.jsonl` line, no sentinel.
  Pinned: one `ziran-calls.jsonl` line for the server. Also `args = "pkg"` (not a list) on
  an `npx` server: `check` exit 2 (invalid entry, fail closed). Run
  `python -m pytest -q tests/test_mcp.py -k unpinned` (fails: unpinned servers reach the
  scanner).
- [X] T016 [US3] Implement, `cli/wuwei/mcp.py`: `PINNED`, `_unpinned`, step 2 of the
  `check` loop. Rerun T015; passes.

## Phase 6: US4, proceed-unmeasured

- [X] T017 [US4] Test, `tests/test_mcp.py` (`test_issue_acceptance_proceed_unmeasured`):
  approved `aws` server `uvx awslabs.example@latest`; `check` exit 2;
  `decide(root, servers=['aws'], confirm=lambda digest: True).exit == 0`; a `D-*.md` with
  `Decided-by: owner`, `Outcome: proceed-unmeasured` and `aws`; an `mcp.decided` event with
  outcome `proceed-unmeasured` and servers `['aws']`; an `accepted-*.json` listing the
  `['aws', digest]` pair; next `check` exit 0 with `aws: proceeding unmeasured by owner
  decision` in the reason. Changing the args to `awslabs.other@latest` makes `check` exit
  2 again. Negatives record nothing: declined confirmation (1), `servers=['nope']` (1), a
  could-not-run or stale record (2). A findings `decide` (no servers) succeeds while another
  server is unmeasured and leaves `check`'s record at exit 2. Run
  `python -m pytest -q tests/test_mcp.py -k proceed_unmeasured` (fails: `decide` takes no
  servers).
- [X] T018 [US4] Test, `tests/test_mcp.py` (`test_mcp_cli_forms`): through
  `wuwei.__main__.main` in the workspace: `mcp decide proceed-unmeasured` (no server) and
  `mcp check proceed-unmeasured aws` return 2; `mcp decide proceed-unmeasured aws` with
  `wuwei.integrity._host_confirm` monkeypatched to accept returns 0. Add
  `'bin/wuwei mcp decide proceed-unmeasured aws'` to the commands of
  `test_owner_command_not_available_to_seats` (refused). Run
  `python -m pytest -q tests/test_mcp.py -k "cli_forms or owner_command"` (fails: argparse
  rejects the words).
- [X] T019 [US4] Implement, `cli/wuwei/mcp.py` (`decide` servers path, `unmeasured`) and
  `cli/wuwei/commands/mcp.py` (plan change 4). Rerun T017 and T018; pass.

## Phase 7: US6, per-server timeout

- [X] T020 [US6] Test, `tests/test_mcp.py`: `test_adapter_fixed_argv_and_metadata` asserts
  `timeout == 60` for `watch-registry` with a three-server file (was `>= 60`); a new case
  with `[scanner.mcp]\ntimeout_seconds = 5` asserts 5. Run
  `python -m pytest -q tests/test_mcp.py -k "fixed_argv or timeout"` (fails: 150 and 150).
- [X] T021 [US6] Implement, `adapters/scanner/ziran.py`: read `timeout_seconds` once in
  `mcp`. Rerun T020; passes.

## Phase 8: US5, briefs name unmeasured servers

- [X] T022 [US5] Test, `tests/test_brief.py` (`test_mcp_unmeasured_in_brief_header`): with
  the `day` fixture, write today's record through `wuwei.mcp._write` with
  `unmeasured=[['remote', '0' * 64]]`, `decided=[['aws', '1' * 64]]` and the other fields
  valid; a written brief's header contains `MCP unmeasured: aws, remote`. Without a record
  there is no `MCP unmeasured` line. Run
  `python -m pytest -q tests/test_brief.py -k mcp_unmeasured` (fails: no line).
- [X] T023 [US5] Implement, `cli/wuwei/brief.py` (plan change 6). Rerun T022; passes.

## Phase 9: docs and finish

- [X] T024 Docs (plan change 7): `templates/workspace/config.toml`,
  `docs/site/configuration.md`, `docs/site/security.md`, `skills/wuwei-plan/SKILL.md` step 1,
  `docs/specs/2026-09-24-wuwei-design.md` S3 amendment. Run
  `python -m pytest -q tests/test_docs.py tests/test_workspace.py`; passes.
- [X] T025 Run the full suite `python -m pytest -q`; everything passes, including the
  `WUWEI_BENCH=1` hook budget tests. Check every file written for em-dashes, emojis,
  client names and absolute local paths and remove any.

## Phase 10: review fixes

- [X] T026 [US2] Test `test_worktree_approval_only_counts_for_its_own_repo` (sentinel, two
  repos): an approval at a worktree of another repo does not start repo `b`'s server; an
  approval at a worktree of `b` does. Implement `_worktree_of` (the worktree's `.git` file
  points into `repo/.git`); `test_approval_sources` worktree case writes that `.git` file.
- [X] T027 [US3] `env` wrapper: `env npx -y pkg@latest` is unpinned, `env A=1 npx pkg@1.2.3`
  is pinned (cases in `test_issue_acceptance_unpinned_launcher_never_run`).
- [X] T028 [US2] Test `test_user_settings_follow_configured_user_file`: user settings are
  read from `.claude/settings.json` next to `scanner.mcp.user_file`.
- [X] T029 [US4] Test `test_proceed_unmeasured_keeps_exit_while_findings_pending`: deciding
  the last unmeasured server leaves status exit 1 while a high finding is pending.
