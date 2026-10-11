# Tasks: delete the remote control plane, the listener and the inbox

**Input**: [spec.md](spec.md), [plan.md](plan.md). Line numbers are at main `221f1f2`.

Rules: test before each behaviour change (see it fail, then change the code). For a pure
deletion the task is "delete the tests with the code, then run the touched test files". Never
relax an assertion that covers kept code. Run only the test files you touch; CI is the gate.
No commits, no pushes, no `gh`.

## Phase 0: setup

- [ ] T001 (skipped: the lead rebases) Rebase onto main after the parts that merge first (#798, #799, #800, #801, #808,
  #809); recheck every line in plan.md; mark the "Owned by earlier parts" edits that are
  already gone.

## Phase 1: move the kept tests out of `tests/test_listen.py`

- [X] T002 Move into `tests/test_watch.py`, adapted to its fixture and with no inbound config:
  the three wake cases (summaries kept while unseen, summary-only mark not covered without an
  inbox mark, PR-only marker unchanged), `test_session_start_reads_the_day_once` (with a
  `watch: clock` line), `test_session_start_reports_a_broken_events_file`, and the torn-line
  half of `test_session_start_decodes_a_day_without_routes_once`. Run `tests/test_watch.py`;
  green on the current code.

## Phase 2: behaviour changes, test first (US2, US3, US4)

- [X] T003 [US2] Test first in `tests/test_watch.py`: replace
  `test_watch_skips_pr_poll_while_the_listener_lives` with
  `test_watch_polls_prs_even_with_a_listen_clock_line` (a `listen: clock` today, `poll_at`
  due, `watch.tick` calls `poll_prs`). See it fail.
- [X] T004 [US2] `cli/wuwei/watch.py`: delete `listening`; `tick` polls when due. T003 green.
- [X] T005 [US3] Test first in `tests/test_watch.py`: a stored wake `{'at', 'prs': [], 'inbox': 3}`
  (written before the upgrade) makes `watch.wake(root)` return `''` without raising. See it
  fail.
- [X] T006 [US3] `cli/wuwei/watch.py`: `mark_wake` and `wake` without the inbox count; a marker
  with no PRs and no summaries is no wake. Comments 85 and 564. T005 and T002 green.
- [X] T007 [US3] Test first in `tests/test_config_transition.py`: with a fake
  `registry.watch_service` and a `wuwei-listen-<hash>` unit file under the test
  `XDG_CONFIG_HOME` (linux) or `HOME` (darwin), `init --upgrade` deletes the unit, calls the
  stop command and prints `Removed the listener service (no longer shipped)`; with
  `--dry-run` it prints `Would remove the listener service (no longer shipped)` and the file
  stays. See it fail.
- [X] T008 [US3] `cli/wuwei/commands/init.py` `upgrade`: the unit removal through
  `commands.watch._remove`. T007 green.
- [X] T009 [US3] Test first in `tests/test_interview.py`: a day `interview.json` with `phone`
  loads through `_recorded`; replace `phone` with another workspace question in the record,
  widget and answer cases; drop the `control_plane.content` placement cases. See the new case
  fail.
- [X] T010 [US3] `cli/wuwei/interview.py`: delete the `phone` question; add `phone` to
  `RETIRED`. T009 green.
- [X] T011 [US4] Test first in `tests/test_setup.py`: the slack fixture has no inbound port and
  no service install; `setup slack` with token and channel typed writes both to `.wuwei/env`,
  sets `adapters.chat = "slack"`, writes no TOTP and no `control_plane`, installs nothing, and
  prints the `config set outbound.owner.slack.user` step when the key is empty. Delete the pin,
  TOTP and listener reinstall cases. See it fail.
- [X] T012 [US4] `cli/wuwei/commands/setup.py`: slim `connect`, delete `_first_dm`,
  `WAIT_SECONDS`, `POLL_SECONDS`, `DM_HINT`; `TOKEN_HINT`, help text and the `_setup`
  condition per plan. T011 green.

## Phase 3: delete the units (US1)

- [X] T013 [US1] Delete `cli/wuwei/control_plane.py`, `inbox.py`, `listen.py`, `remote.py`,
  `commands/listen.py`, `commands/remote.py`, `adapters/inbound/`; delete
  `tests/test_control_plane.py`, `tests/test_inbox.py`, `tests/test_remote.py`,
  `tests/test_listen.py`.
- [X] T014 [US1] `cli/wuwei/shepherd.py`: delete `_STOP`, `_TRIAGE`, `HEADLESS`, `pending`,
  `headless`. `adapters/runtime/claude.py`: delete `SESSION`, `TIMEOUT`, `headless`; in
  `tests/test_runtime.py` delete `headless_case` and the six headless tests. Run
  `tests/test_runtime.py tests/test_headless_shepherd.py`.
- [X] T015 [US1] Config: `workspace.py` (SCHEMA, SURFACES), `registry.py`, `telemetry.py`
  (ADAPTERS, OWNER_KINDS, the two `remote.` prefixes), `templates/workspace/config.toml`,
  `profiles.py`, `env.py`. Tests with them: `tests/test_workspace.py`,
  `tests/test_calibrate.py`, `tests/test_adapters.py`, `tests/test_telemetry.py`,
  `tests/test_env_credentials.py` (TOTP line). Run those files.
- [X] T016 [US1] Health: `guards/lifecycle.py`, `heartbeat.py`, `commands/status.py`
  (scan returns four values), `commands/next.py:306`, `commands/doctor.py` (claude row,
  service manager text, day rows, FIXES). Tests: `tests/test_signal_status.py`,
  `tests/test_doctor.py`, `tests/test_heartbeat.py`, `tests/test_watch.py` (the
  `name='listen'` health assertion). Run them.
- [X] T017 [US1] Records and events: `signal.py`, `commands/event.py`, `state.py`,
  `sessions.py`, `commands/decision.py`, `commands/outbound.py` docstring, `cruise.py`
  comment, `adapters/redactor/builtin.py` docstring. Tests: `tests/test_signal_status.py`
  classification tables, `tests/test_decision.py`, `tests/test_sessions.py`,
  `tests/test_state_allowlist.py`. Run them.
- [X] T018 [US1] Config check: `commands/config.py`. Tests: `tests/test_env_credentials.py`,
  `tests/test_workspace.py` (`missing` cases). Run them.
- [X] T019 [US1] Mutation probes and lints: `tests/test_guard_mutation.py` (remote entries
  and probes), `tests/test_outward.py`, `tests/test_reasons.py`,
  `tests/test_reference_adapters.py`, `tests/test_report_retro.py`, `tests/test_hooks.py`
  (`name='shepherd'`), `tests/conftest.py` comment. Run them.
- [X] T020 [US1] Earlier-part leftovers, only if still present: `__main__.py` GROUPS,
  `commands/__init__.py` WRITES, `guards/protect_state.py` owner actions and the `inbox`
  tail, `commands/nudges.py` row; `tests/test_protect_state.py`, `tests/test_quiet_sweeps.py`.
  Run the touched files.
- [X] T021 Grep `cli adapters tests` for `control_plane|wuwei.remote|wuwei.listen|wuwei.inbox|
  'inbound'|listen:|listening|TOTP|responder|decision.replied|role='remote'`; fix any hit.
  Run every file touched in phases 2 and 3 together.

## Phase 4: charter, docs, spec (US5)

- [X] T022 [US5] `charters/_common.md` item 2; run `bin/wuwei agents build`; run
  `tests/test_charters.py` and `tests/test_tone.py`.
- [X] T023 [US5] Delete `docs/site/remote.md`; edit README, `mkdocs.yml`, `docs/site/index.md`,
  `concepts.md`, `daily.md`, `configuration.md`, `reference.md`, `adapters.md`, `agent.md`,
  `security.md`, `integrity.md` per plan. In `tests/test_docs.py` delete the remote runbook
  tests and lines per plan (skip what part 1 removed). Run `tests/test_docs.py`.
- [X] T024 [US5] Design spec section 15 heading and note, and the marked passages;
  constitution constraint, version and date.
- [X] T025 [US5] Run the acceptance grep from spec US5 over `charters skills hooks agents
  docs/site README.md templates`; only the `inbox` mail vocabulary word in
  `docs/site/security.md` may remain.

## Phase 5: close

- [ ] T026 (for the lead: no PR is raised here) List the RETIRED keys from plan.md in the PR description for the lead.
- [X] T027 Run every touched test file once more; leave the tree uncommitted.

## Dependencies

T001 first. T013 to T020 leave imports broken in between (for example `config.py` imports
`remote.PIN`); finish them before running the files. T002 before T013 (it moves tests out of a file T013 deletes). T003-T012 before
T013 so each behaviour test sees the old code fail. T014-T020 in any order after T013. T022-T025
after T013. T027 last.
