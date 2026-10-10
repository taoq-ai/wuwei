# Tasks: Two installs named, traces warns below strict, one credential reader, every backlog discovered

Test first: each test task runs and fails for the expected reason before its implementation
task. While building, run only the touched test files:
`python -m pytest -q tests/test_traces.py tests/test_guard_mutation.py tests/test_invariants.py
tests/test_integrity.py tests/test_canary.py tests/test_workspace.py tests/test_doctor.py
tests/test_heartbeat.py tests/test_env_credentials.py tests/test_tracker_adapters.py
tests/test_linear_loop.py tests/test_plan.py tests/test_quiet_sweeps.py tests/test_agents.py
tests/test_charters.py`.

## Phase 1: traces guard (US1; FR-001 to FR-004, FR-012)

- [X] T001 Test in `tests/test_traces.py`: `test_traces_failure_warns_below_strict`,
  parametrised over observe, guarded and strict, in a security-enabled workspace (config
  `[security]\nrequired = true\nposture = "<p>"`, `security.initialize(root / '.wuwei')`)
  with `security.record` patched to raise `OSError('private details')`. Through
  `run_hook`: exit 0 under observe and guarded, 2 under strict; stderr names
  `events.jsonl` and `OSError`, never `private details`. Patch only `security.record`, so
  `state.append_event` still writes: one `traces.gap` whose reason is in stderr. Add a
  second case without a mock: a Bash payload `cat credentials/backup.env "x` (the
  reproduced trigger) gives exit 0 under observe, stderr naming `the tool call for canary
  and honeytoken findings`, and one `traces.gap`. Run: fails (exit 2 in every posture,
  generic sentence, no gap).
- [X] T002 Test in `tests/test_traces.py`:
  `test_traces_failure_names_the_executable_mismatch`: `.wuwei/executable` names a
  `tmp_path` launcher other than `integrity.PLUGIN / 'bin/wuwei'`; the reason names both
  launchers and ends with `run bin/wuwei doctor, which names the fix`; with the record
  naming this launcher, the reason has no mismatch clause. Run: fails.
- [X] T003 Regression test in `tests/test_traces.py`: an unreadable config
  (`config.toml` holding invalid TOML such as `[security`) with a failing `security.record` keeps exit 2
  (fail closed). It passes today through the early return and guards T006 from turning an
  unreadable config into a pass.
- [X] T004 Test in `tests/test_invariants.py`: `i54`, `READS['I54'] = (0,)` and the
  `INVARIANTS` key (plan 8: own workspace beside `rules.root`, `.wuwei/security.json`
  holding `{}`, memo per posture, no mock). Add the I54 row to
  `docs/specs/2026-09-24-wuwei-design.md` section 9.2. Run `tests/test_invariants.py`:
  fails on I54 (exit 2 under observe and guarded); the walk stays under its budget.
- [X] T005 Implement `integrity.recorded(root)` in `cli/wuwei/integrity.py` (plan 2) and
  the traces changes in `cli/wuwei/guards/traces.py` `check` (plan 1: step label, common
  tail, `_strict`, mismatch clause). Run `tests/test_traces.py
  tests/test_traces_seats_only.py tests/test_guard_mutation.py tests/test_invariants.py`:
  green, with the existing `test_post_tool_failures_report_without_refusing` and
  `test_recorder_owns_failures` unchanged.

## Phase 2: install helpers, init, doctor (US2; FR-005, FR-006)

- [X] T006 Test in `tests/test_integrity.py`: `test_launcher_prefers_the_registered_install`:
  `integrity.PLUGIN` set to a release-shaped `tmp_path` install B (`bin/wuwei`,
  `MANIFEST.sha256.sig`, no `.git`); `HOME/.claude/plugins/installed_plugins.json`
  registers install A under `wuwei@wuwei`. `integrity.launcher(root)` is `<A>/bin/wuwei`;
  with no plugins file, with `{"version": 2, "plugins": {}}`, with an entry whose install
  has no `bin/wuwei`, and with a malformed file it is `<B>/bin/wuwei`; with B given a
  `.git` directory (a development checkout) it is `<B>/bin/wuwei` although A is registered.
  `integrity.registered` raises on the malformed file and returns None without the file.
  Run: fails (no helpers).
- [X] T007 Test in `tests/test_canary.py` (in-process `init.run`, as its tests do):
  `test_init_writes_the_registered_install`: the T006 setup; `init.run` writes
  `<A>/bin/wuwei` to `.wuwei/executable`; `init --upgrade` from B keeps it and
  `init --upgrade --dry-run` prints no `executable pointer` line. The existing
  `tests/test_workspace.py` assertions at `:646` and `:697` (a checkout, no registration)
  stay as they are. Run: fails.
- [X] T008 Implement `integrity.development`, `integrity.registered` and
  `integrity.launcher` (plan 2) and use `launcher` in `cli/wuwei/commands/init.py` create
  and upgrade (plan 3). Run `tests/test_integrity.py tests/test_canary.py
  tests/test_workspace.py tests/test_env_credentials.py`: green.
- [X] T009 Test in `tests/test_doctor.py`:
  `test_hooks_row_reads_the_registration_from_either_launcher`: the `ws` fixture registers
  its plugin A; `integrity.PLUGIN` is then set to a second release-shaped install B (its
  own `bin/wuwei`, `hooks/hooks.json`, `.claude-plugin/plugin.json`,
  `MANIFEST.sha256.sig`); the hooks row is ok ("registered in Claude Code"). Run: fails
  ("not listed").
- [X] T010 Test in `tests/test_doctor.py`: `test_two_installs_named_with_the_fix`: the T009
  setup with `.wuwei/executable` naming B: an `installs` warn row names A with
  "registered" and B with "this launcher" and "named by .wuwei/executable"; its fix starts
  with `<A>/bin/wuwei init --upgrade`; the executable row fails naming A. With the record
  naming A the executable row is ok. With one install the row is absent
  (`test_workspace_rows_healthy` and the install section's row names unchanged). Run:
  fails.
- [X] T011 Implement in `cli/wuwei/commands/doctor.py`: `_checkout = integrity.development`,
  `_hooks` through `integrity.registered`, `_installs` appended in `_install`, the
  executable row through `integrity.recorded` and `integrity.launcher` (plan 4). Run
  `tests/test_doctor.py`: green, `test_workspace_executable_pointer` included.

## Phase 3: one credential reader (US3; FR-007, FR-008)

- [X] T012 Test in `tests/test_heartbeat.py`:
  `test_config_probe_reads_the_env_file_at_each_beat`: `GITHUB_TRACKER_TOKEN` absent from
  the environment (`monkeypatch.delenv`), a config needing it; a first
  `heartbeat.measure(root)['config']` fails with `missing GITHUB_TRACKER_TOKEN`; the token
  is then written to `.wuwei/env` (mode 0600) and the second measure is `ok`. Clean the
  loaded name with `monkeypatch` or `env.session()`. Run: fails (still missing).
- [X] T013 Implement `env.load(root)` in `cli/wuwei/heartbeat.py` `_config` (plan 5). Run
  `tests/test_heartbeat.py tests/test_env_credentials.py`: green.
- [X] T014 Test in `tests/test_doctor.py`:
  `test_credentials_row_when_watch_and_doctor_disagree`: `watch.save(root, {'heartbeat':
  {'probes': {'config': {'result': 'failed', 'value': 'missing GITHUB_TRACKER_TOKEN'}}}})`
  with doctor's own config probe ok: a `credentials` warn row carries both readings and the
  fix; with equal readings, with no saved beat, or with saved probes lacking `config`, no
  row. Run: fails.
- [X] T015 Implement the credentials row in `cli/wuwei/commands/doctor.py` `_day`
  (plan 4). Run `tests/test_doctor.py tests/test_traces.py`: green.

## Phase 4: every backlog (US4; FR-009 to FR-011)

- [X] T016 Test in `tests/test_tracker_adapters.py`:
  `test_github_backlog_reads_every_configured_repository`: config with
  `tracker.project = "acme/app"` and `[[repos]]` `acme/app` and `acme/gadget`; two replayed
  responses; two GraphQL calls with `name` `app` then `gadget`; ids `acme/app#1` and
  `acme/gadget#1`; a failing second response makes the result exit 2; a repository name
  that is not `<owner>/<repo>` fails naming it. `test_tracker_port_contract` stays
  unchanged. Run: fails (one call).
- [X] T017 Implement `_repos` and the backlog loop in `adapters/tracker/github.py`
  (plan 6). Run `tests/test_tracker_adapters.py tests/test_tracker.py`: green.
- [X] T018 Test in `tests/test_linear_loop.py`:
  `test_discover_lists_every_repository_and_narrows_with_repo`: two configured
  repositories `acme/app` and `acme/app-docs`, a fake tracker port returning
  `acme/app#1`, `acme/app-docs#2` and `ENG-3`; `main(['discover'])` lists all three with
  `source`, the first two with their `repo` (no prefix confusion) and `ENG-3` without;
  `main(['discover', '--repo', 'acme/app-docs'])` keeps `acme/app-docs#2` and `ENG-3`;
  `--repo acme/unknown` exits 2 naming the configured repositories. Run: fails (no
  `--repo`, no `repo`).
- [X] T019 Implement `repo` in `cli/wuwei/discovery.py` `discover` and `--repo` in
  `cli/wuwei/commands/discover.py` (plan 6). Run `tests/test_linear_loop.py
  tests/test_plan.py tests/test_quiet_sweeps.py`: green.
- [X] T020 Edit `charters/lead.md` (plan 7, version 1.5.1), run `bin/wuwei agents build`,
  add the sentence to `docs/site/configuration.md`. Run `tests/test_agents.py
  tests/test_charters.py tests/test_docs.py`: green (the generated-agent drift test fails
  before the rebuild).
- [X] T020a Review fixes: the `--repo` error names a next step (`pass one of:`); the lead
  charter's discovery step is split under the 35-word tone budget; a GitHub
  `tracker.project` outside `[[repos]]` is tagged and selectable with `--repo`
  (`test_discover_repo_counts_a_github_tracker_project`). Run `tests/test_reasons.py
  tests/test_tone.py tests/test_linear_loop.py`: green.

## Phase 5: close

- [X] T021 Run every test file listed at the top, then the full suite. Grep the changed
  files for em-dashes, emojis and absolute local paths; remove any.
