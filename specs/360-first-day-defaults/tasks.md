# Tasks: the first day works on defaults

**Input**: `specs/360-first-day-defaults/` (spec.md, plan.md)

Test first, always: each test task is written, run with the command given, and seen to fail
for the expected reason before its implementation task starts. Run from the repository
root with the interpreter your task names. No absolute local paths, client, repository or
handle names (use `acme/*`, `pat-example`, `Pat Example`, `example.test`), emojis or
em-dashes in any file. Tests never need the network, the real `gh` or `ziran`: use the
existing SimpleNamespace `host` fake, `PATH` stubs and monkeypatched ports. Repositories in
tests are real `git init` directories under `tmp_path` (the `make_repo` helper).

## Phase 1: setup fixtures (no behaviour change)

- [X] T001 `tests/test_setup.py`: extend the `terminal` fixture with (a) scripted y/N
  replies: monkeypatch `builtins.input` with a function that returns the first value in
  `terminal.replies` (a dict from a prompt keyword such as `ZIRAN`, `tests`, `status line`,
  `watch` to a reply) whose key is in the prompt, else `''`; (b) `doctor.diagnose` stubbed
  to return `terminal.rows` (default `[]`); (c) the fake `interview.ask` records the ids it
  was given in `terminal.ids`. Run `python -m pytest -q tests/test_setup.py`; still passes.

## Phase 2: US1, the default branch from git

- [X] T002 [US1] Test, `tests/test_adapters.py`: add `('vcs', 'default_branch', ('repo',),
  True)` to `CALLS`. Test, `tests/test_vcs.py` (`test_default_branch_from_git`): on a real
  repository with `origin/HEAD` set by `git symbolic-ref refs/remotes/origin/HEAD
  refs/remotes/origin/develop` (after `git update-ref refs/remotes/origin/develop HEAD`),
  `default_branch` returns `{'branch': 'develop', 'source': 'origin/HEAD'}`; without it, on
  branch `trunk`, `{'branch': 'trunk', 'source': 'the checked-out branch'}`; on a detached
  HEAD, exit 2 with a reason. Run `python -m pytest -q tests/test_adapters.py
  tests/test_vcs.py -k "contracts or default_branch"` (fails: no such operation).
- [X] T003 [US1] Implement `default_branch` and the widened `symbolic-ref` case in
  `adapters/vcs/git.py`, and `'default_branch': ('repo',)` in `cli/wuwei/registry.py`
  `PARAMETERS['vcs']`. Rerun T002; passes.
- [X] T004 [US1] Test, `tests/test_setup.py`:
  `test_discovery_falls_back_to_git_when_gh_cannot_read` (host `default_branch` returns
  `Result(2, reason='github.default_branch: could not run: gh exited 1')`: every
  repository is staged with `default_branch == 'main'` and the lines contain
  `alpha: default branch main (from the checked-out branch; gh could not read it:
  github.default_branch: could not run: gh exited 1)`, `found['owed'] == []`);
  rewrite `test_discovery_without_host_auth_owes_every_repository` into
  `test_discovery_without_host_auth_stages_from_git` (staged from git, lines name `gh is
  not signed in`, `host.calls == []`); `test_discovery_names_a_repository_without_remote`
  (a `git init` repository `widget` with no `origin` and login `pat-example` is staged as
  `pat-example/widget` with the line `widget: no GitHub remote; proposed as
  pat-example/widget, default branch main (from the checked-out branch)`; with auth
  missing it is owed); `test_discovery_lists_worktrees_and_owes_other_hosts` still owes
  the `example.test` remote. Run `python -m pytest -q tests/test_setup.py -k discovery`
  (fails).
- [X] T005 [US1] Implement the `discover` changes in `cli/wuwei/commands/setup.py`. Rerun
  T004, then `python -m pytest -q tests/test_setup.py`; passes.

## Phase 3: US2, reviewers, posture skip, owner.name, labels

- [X] T006 [US2] Test, `tests/test_interview.py`: add `reviewers` to the id list in
  `test_question_table_fits_widgets_and_every_choice_validates`, and in the same loop assert
  no choice label matches `\b(I|me|my|mine|myself)\b` (case-sensitive `I`, case-insensitive
  for the rest). New `test_reviewers_question`: `effects('reviewers', 'Owner only') ==
  {'shepherd.min_reviewers': 0}`, `'Code authors'` gives `1`, `'pat-dev'` gives
  `{'shepherd.lead_login': 'pat-dev', 'shepherd.min_reviewers': 1}`, `'not a login!'` is
  refused naming `code-host login`; the row is in `widgets(...)`; `settings({'reviewers':
  'Owner only'}, config)` gives `[(('shepherd',), 'min_reviewers', 0)]`. Run
  `python -m pytest -q tests/test_interview.py -k "table or reviewers"` (fails).
- [X] T007 [US2] Implement `_login` and the `reviewers` row in `cli/wuwei/interview.py`.
  Rerun T006; passes.
- [X] T008 [US2] Test, `tests/test_setup.py`: `test_shadow_skips_the_posture_question`
  (`run_setup(shadow=True)` gives `terminal.ids` without `posture` and with `reviewers`;
  `shadow=False` includes `posture`); `test_teammate_login_wins_over_setup_lead` (the fake
  ask answers `reviewers=pat-dev`; the applied config has `shepherd.lead_login == 'pat-dev'`
  and `min_reviewers == 1`, the digest has no `lead_login = "pat-example"` line);
  `test_identity_settings` gains `('owner', 'name'): 'Pat'` for the repository identity and
  no such key when `owner.name` is already set; `test_setup_proposes_owner_name` (end to
  end: `+name = "Pat Example"` in the digest, `load_config(...)['owner']['name'] == 'Pat
  Example'`). Run `python -m pytest -q tests/test_setup.py -k "posture_question or
  teammate or identity or owner_name"` (fails).
- [X] T009 [US2] Implement in `cli/wuwei/commands/setup.py`: the interview ids under
  `--shadow`, and `owner.name` in `identity`. Rerun T008; passes.

## Phase 4: US3, scanner and the test run are asked

- [X] T010 [US3] Test, `tests/test_setup.py`: replace `test_ziran_on_path_is_proposed`
  with `test_ziran_is_proposed_only_on_yes` (parametrized: reply `y` gives `+scanner =
  "ziran"` in the digest; `''` and `n` do not; the prompt contains `[y/N]`).
  `test_setup_measures_the_test_runner_once`: give `alpha` a `pyproject.toml` with
  `[tool.pytest.ini_options]` committed, stub `registry.load('checks', ...)` with a fake
  whose `run` records calls and returns `Result(0)`; with the default reply the digest has
  `fast_checks = ["python3 -m pytest -q"]` for `acme/alpha`, the runner ran once, there is
  exactly one digest, and the output has `Test runner found: acme/alpha: python3 -m pytest
  -q`; with reply `n` the runner never runs and the digest has `CI only, not proposed as a
  fast check: acme/alpha: python3 -m pytest -q (test runner, unmeasured`; a fake that
  sleeps past a lowered `calibrate.fast_check_seconds` (or returns exit 1) keeps it CI
  only with `measured` in the note. A closed stdin (`input` raises `EOFError`) means no
  run. Run `python -m pytest -q tests/test_setup.py -k "ziran or measures"` (fails).
- [X] T011 [US3] Implement `_yes`, the scanner question and the measure step in
  `cli/wuwei/commands/setup.py`. Rerun T010; passes.
- [X] T012 [US3] Test, `tests/test_doctor.py` `test_workspace_repository_rows`: the
  `fast_checks` fix starts with `bin/wuwei config promote --measure` and contains
  `bin/wuwei config set repos.0.fast_checks`; `apply` stays `config-promote`. Run
  `python -m pytest -q tests/test_doctor.py -k workspace_repository_rows` (fails).
- [X] T013 [US3] Implement the fix text in `cli/wuwei/commands/doctor.py`. Rerun T012;
  passes.

## Phase 5: US4, status line, watch and the one ready line

- [X] T014 [US4] Test, `tests/test_workspace.py` or `tests/test_setup.py`
  (`test_status_line_is_written_once`): `init.status_line(root)` on a workspace whose
  `.claude/settings.json` holds `permissions` adds `statusLine` with the command ending
  ` status --line` and keeps `permissions`; on a missing file it creates it; a symlinked
  file and a workspace at `Path.home()` raise `ValueError` and write nothing.
  `test_setup_writes_the_status_line_on_yes` (default reply: the key is written and
  `Status line: added` printed; reply `n`: no key; an existing `statusLine` is kept and no
  status-line prompt is shown) and `test_setup_init_prints_no_status_json` (setup on a
  fresh project prints no line starting `{"statusLine"`; plain `bin/wuwei init` still
  does, as the existing tests pin). Run `python -m pytest -q tests/test_setup.py -k
  status_line` (fails).
- [X] T015 [US4] Implement in `cli/wuwei/commands/init.py`: `settings(root)`,
  `_status_command`, `status_line(root)`, the `status_line` flag in `run`; and the
  status-line offer in `cli/wuwei/commands/setup.py`. Rerun T014, then
  `python -m pytest -q tests/test_signal_status.py tests/test_records_after_dryrun4.py
  tests/test_workspace.py`; pass.
- [X] T016 [US4] Test, `tests/test_setup.py` (`test_setup_offers_the_watch`): monkeypatch
  `watch.service_platform` to `'linux'` and `registry.watch_service` with a recorder; reply
  `y` writes the unit under the test `HOME` and records `systemctl --user enable --now`;
  the default reply installs nothing; an existing unit asks nothing; a recorder that raises
  `OSError` prints `watch install:` on stderr and setup still exits 0. Run
  `python -m pytest -q tests/test_setup.py -k watch` (fails).
- [X] T017 [US4] Implement the watch offer in `cli/wuwei/commands/setup.py`. Rerun T016;
  passes.
- [X] T018 [US4] Test, `tests/test_setup.py` (`test_ending`, parametrized over the pure
  `setup.ending`): no rows and nothing required gives `Ready: run /wuwei:wuwei-plan`, code
  0; a `warn` Workspace row and a `fail` Gates row give `Optional: 2 more in bin/wuwei
  doctor` then `Ready: ...`, code 0; optional `['bin/wuwei promote']` plus one other row
  gives `Optional: bin/wuwei promote; 1 more in bin/wuwei doctor`; a `fail` Install row
  with fix `wuwei integrity reconfirm` gives last line `Next: wuwei integrity reconfirm`,
  code 1; an `unmeasured` Workspace row gives code 2; required `['set LINEAR_API_KEY in
  .wuwei/env']` comes before a failing row's fix; `gate=2` gives code 2; a non-ok row
  named `mcp gate` is not counted; the text has exactly one line starting `Ready:` or
  `Next:` and it is the last. Run `python -m pytest -q tests/test_setup.py -k ending`
  (fails).
- [X] T019 [US4] Test, `tests/test_setup.py`: update `test_one_command_three_repositories`
  (no `Still owed:`; the output's last line is `Ready: run /wuwei:wuwei-plan`; the line
  before it starts `Optional:` and contains `bin/wuwei promote`; exit 0),
  `test_empty_directory_owes_add_repo` (last line starts `Next: bin/wuwei config add-repo`,
  exit 1), `test_pending_mcp_decision_is_owed_by_command` (last line `Next: bin/wuwei mcp
  decide D-2 proceed`), and add `test_setup_next_names_a_failing_doctor_row`
  (`terminal.rows` holds an Install `fail` row with fix `wuwei integrity reconfirm`: last
  line `Next: wuwei integrity reconfirm`, exit 1). Run `python -m pytest -q
  tests/test_setup.py -k "three_repositories or empty_directory or mcp_decision or
  doctor_row"` (fails).
- [X] T020 [US4] Implement `ending`, the tail of `_setup` (doctor run, required and
  optional lists, removal of `config.run` and `Still owed`) and the early return in
  `cli/wuwei/commands/setup.py`. Rerun T018 and T019, then
  `python -m pytest -q tests/test_setup.py`; all pass, `test_setup_ends_with_the_restart_line`
  unchanged.
- [X] T021 [US4] Test, `tests/test_setup.py` (`test_first_day_on_defaults_without_github_remote`,
  the issue's acceptance test): a project with one `git init -b main` repository `widget`
  (identity set, one commit, no `origin`); the `host` fake signed in as `pat-example`,
  `merged_prs` and `protection` returning exit 2; the real `doctor.diagnose` (undo the
  fixture stub) with `integrity.fresh` returning `Result(0)` and `heartbeat.measure` and
  `registry.watch_service` stubbed as `tests/test_doctor.py` does; every y/N on its
  default. `run_setup(Confirm())` exits 0, the last line is `Ready: run /wuwei:wuwei-plan`,
  `repos[0]` is `pat-example/widget` on `main`; then `main(['plan', 'template'])` output
  written to a file and `main(['plan', 'propose', <file>])` exit 0. Run it; it should pass
  after T020. If it fails, fix the cause in the code above, not in the test.

## Phase 6: US5, host protection fix lines

- [X] T022 [US5] Test, `tests/test_env_credentials.py` (next to the existing protection
  tests): a branch with no classic protection and missing rows prints `acme/widget main:
  fix in https://github.com/acme/widget/settings/branches` and one `or run in your own
  terminal: gh api -X PUT repos/acme/widget/branches/main/protection ...` line whose
  `shlex.split` contains `allow_force_pushes=false`, `allow_deletions=false`,
  `required_pull_request_reviews[required_approving_review_count]=1` and
  `required_status_checks=null` (no `review_required_checks`); with
  `review_required_checks = ["unit"]` it has `required_status_checks[contexts][]=unit`;
  with `shepherd.min_reviewers = 0` it has `required_pull_request_reviews=null`; with
  classic protection present only the URL line prints; a fully protected branch prints
  neither; exit codes are unchanged. Run `python -m pytest -q tests/test_env_credentials.py
  -k protection` (fails).
- [X] T023 [US5] Implement the two lines in `_protection` in `cli/wuwei/commands/config.py`.
  Rerun T022, then `python -m pytest -q tests/test_env_credentials.py tests/test_doctor.py`;
  pass.

## Phase 7: docs and verification

- [X] T024 Docs: `docs/site/daily.md` section 2 and the `docs/site/configuration.md`
  interview table, as plan.md says. Run `python -m pytest -q tests/test_docs.py`; passes
  (update a docs test only where it pinned the removed `Still owed` or solo-owner sentence).
- [X] T025 Run the full suite, `python -m pytest -q`; everything passes. Grep every changed
  file for em-dashes, emojis, absolute local paths and real handles or client names, and
  remove any.
