# Tasks: phone answers to two-way decisions are outcomes, and `wuwei setup slack` connects the DM in one command

**Input**: `specs/364-phone-outcomes-slack-setup/` (spec.md, plan.md)

Test first, always: each test task is written, run with the command given, and seen to fail
for the expected reason before its implementation task starts. Run from the repository
root with the interpreter your task names. No absolute local paths, client, repository or
handle names (use `acme/*`, `T0103ABC`, `U0123ABC`, `D0123ABC`, `example.test`), no real
tokens (a fake value such as `xoxb-test-1` built in the test), no emojis or em-dashes in
any file. Tests never need the network, Slack, `launchctl` or `systemctl`: use the existing
`Transport`, `Runtime`, `routed` and `remote_row` helpers in `tests/test_remote.py`, the
`project`, `host` and `terminal` fixtures in `tests/test_setup.py`, and monkeypatched
`getpass.getpass`, `registry.load` for `inbound`, `wuwei.commands.watch.service` and
`service_platform`. Read plan.md "Build order and #354" first: if #354 is on the base,
apply its swaps in every task below.

## Phase 1: US1, a DM answer to a two-way decision is the outcome

- [X] T001 [US1] Test, `tests/test_decision.py`: `test_owner_outcome_takes_a_root_and_a_confirmation`:
  in a workspace other than the working directory, route a decision and call
  `owner_outcome(SimpleNamespace(id='D-1', option='A'), root=ws, confirm=lambda *a, **k: True)`;
  it returns `(0, 'A')`, writes `decision_outcomes.D-1.decided_by == 'owner'` and
  `Outcome: A`, and `_host_confirm` (monkeypatched to raise) is never called; with
  `confirm=lambda *a, **k: False` it returns `(1, 'decision: owner confirmation declined')`.
  Run `python -m pytest -q tests/test_decision.py -k takes_a_root` (fails: unexpected
  keyword).
- [X] T002 [US1] Implement the `root` and `confirm` keywords in `owner_outcome`,
  `cli/wuwei/commands/decision.py`. Rerun T001, then `python -m pytest -q
  tests/test_decision.py`; passes.
- [X] T003 [US1] Test, `tests/test_remote.py`: add `TWO_WAY = VALID.replace('Reversibility:
  one-way', 'Reversibility: two-way').replace('Blast radius: own branch', 'Blast radius:
  workspace')` and:
  - `test_two_way_answer_is_the_outcome`: `routed(ws, TWO_WAY)`, `handled(ws, 'option B on
    D-1')` is `(0, [remote().RECORDED.format(identifier='D-1', option='B')])`; state
    `decision_outcomes['D-1']` has `option == 'B'`, `decided_by == 'owner'`,
    `reversibility == 'two-way'`; `payloads(ws, 'decision.decided')` has one row with
    `decided_by: owner`; one `decision.replied` event; the record has `Outcome: B`;
    `status.line(status.snapshot(day))` has no `phone answers`.
  - `test_two_way_answer_resumes_a_parked_item`: an item `X` with `phase: parked`,
    `status: blocked`, `resume_phase: planned`, `decision: D-1`; after the answer it is
    `planned` and `queued`.
  - parametrized `test_two_way_approve_and_drop_it_record` for `approve D-1` (records `A`)
    and `drop it` (records `B`, the Defer option).
  - `test_two_way_answer_with_a_live_session_records_then_resumes`: `remote_row(ws, S,
    ['D-1'])`, a `Runtime(ran())`; the first DM is `RECORDED`, the runtime prompt is
    `Decision D-1: option B.`, the outcome is recorded.
  - parametrized `test_one_way_answer_is_noted_with_the_host_command` for `one-way` and
    `unsure`: no `decision_outcomes`, one `decision.replied`, DM
    `Noted D-1 option B. D-1 cannot be undone, so confirm it on the host: decision outcome D-1 B.`
  - `test_two_way_writer_refusal_is_unrun`: monkeypatch `owner_outcome` to return
    `(1, 'decision: record changed during confirmation')`; exit 2, DM `[FAILED]`, the log
    line `listen remote unmeasured: decision: record changed during confirmation`.
  - add `RECORDED` and `NOTED` (formatted) to `test_fixed_lines_pass_the_outward_lint`.
  - update the three one-way expectations `Recorded D-1 option ... Confirm it on the host.`
    (`test_reply_without_a_remote_session_is_recorded_evidence`, the one at the end of
    `test_stop_marks_remote_sessions_and_blocks_resumes` and
    `test_issue_acceptance_a_conflicting_second_answer_is_refused`) to the `NOTED` text.
  - `test_listen_is_a_named_outcome_producer`: `EVENT_PRODUCERS['decision.decided']`,
    `EVENT_PRODUCERS['decision.reversed']` and `state.STATE_PRODUCERS['decision_outcomes']`
    each contain `wuwei listen`.
  Run `python -m pytest -q tests/test_remote.py` (fails: no `RECORDED`, nothing recorded).
- [X] T004 [US1] Implement `RECORDED`, `NOTED` and the `handle` branch in
  `cli/wuwei/remote.py` as plan.md describes, and the producer strings in
  `cli/wuwei/commands/event.py` (`EVENT_PRODUCERS`) and `cli/wuwei/state.py`
  (`STATE_PRODUCERS`). Rerun T003, then `python -m pytest -q tests/test_remote.py
  tests/test_listen.py tests/test_signal_status.py tests/test_decision.py`; passes.

## Phase 2: US2, `bin/wuwei setup slack`

- [X] T005 [US2] Test, `tests/test_env_credentials.py`: `test_env_write_sets_lines_and_keeps_the_rest`:
  a `.wuwei/env` (0600) with a comment, `LINEAR_API_KEY=a` and `SLACK_BOT_TOKEN=old`;
  `env.write(root, {'SLACK_BOT_TOKEN': 'xoxb-test-1', 'SLACK_OWNER_DM_CHANNEL': 'D0123ABC'})`
  leaves the comment and `LINEAR_API_KEY=a`, one `SLACK_BOT_TOKEN=xoxb-test-1` line, mode
  `0o600`, and `env.load` reads it back; a missing file is created 0600; an unknown name,
  a value with a space, a quote or a newline, and a symlinked `.wuwei/env` each raise
  `ValueError` and write nothing. Run `python -m pytest -q tests/test_env_credentials.py -k
  write` (fails: no `write`).
- [X] T006 [US2] Implement `env.write` in `cli/wuwei/env.py`. Rerun T005; passes.
- [X] T007 [US2] Test, `tests/test_setup.py`: a `slack` fixture on top of `project`,
  `host` and `terminal` that writes an initialized workspace config, sets
  `WUWEI_WORKSPACE`, clears the four Slack and TOTP variables with `monkeypatch.delenv`,
  monkeypatches `getpass.getpass` (returns `slack.token`, default `'xoxb-test-1'`),
  `registry.load` for `inbound` (a fake whose `poll` returns `slack.polls.pop(0)`, default
  one `Result(0, [event from T0103ABC/U0123ABC in D0123ABC with ts after WUWEI_NOW])`),
  `wuwei.commands.watch.service` (records `(action, name)`), `service_platform`
  (`'darwin'`) and `config.run` (records the call, returns 0); `terminal.replies` answers
  the channel prompt with `D0123ABC`. Tests:
  - `test_setup_slack_connects_the_dm`: `setup().run(SimpleNamespace(target='slack'),
    confirm=lambda *a, **k: True)` exits 0; `.wuwei/env` is 0600 with the token, the
    channel and a `WUWEI_TOTP_SECRET` whose base32 decodes to 20 bytes; config has both
    adapters `slack` and `control_plane.owner == 'T0103ABC/U0123ABC'`; output contains
    `T0103ABC/U0123ABC`, `otpauth://totp/WUWEI:owner?secret=<that secret>&issuer=WUWEI&algorithm=SHA1&digits=6&period=30`;
    `watch.service` saw `('install', 'listen')` only; `config.run` was called; the token is
    not in the output.
  - parametrized `test_setup_slack_refuses_a_bad_or_empty_token` (`''`, `'xoxp-user'`,
    `'not a token'`): exit 1, the output names `OAuth & Permissions` and
    `bin/wuwei setup slack`, does not contain the typed value, and `.wuwei/env` and
    `config.toml` are unchanged.
  - `test_setup_slack_refuses_an_empty_or_bad_channel` (`''`, `'C0123ABC'`): exit 1,
    nothing written.
  - `test_setup_slack_declined_writes_no_pin`: `confirm=lambda *a, **k: False`; exit 1,
    `config.toml` unchanged, no `WUWEI_TOTP_SECRET`, `watch.service` not called.
  - `test_setup_slack_waits_then_gives_up`: polls return `Result(0, [])` (and an old
    message with `ts` before the start); `time.sleep` monkeypatched to a counter; exit 1 after
    `WAIT_SECONDS // POLL_SECONDS` polls, output names `Messages Tab` and `im:history`,
    no pin.
  - `test_setup_slack_poll_failure_is_unrun`: poll returns `Result(2, None, 'slack.poll:
    could not run: invalid_auth')`; exit 2, the reason is printed with the same hint.
  - `test_setup_slack_second_run_keeps_and_restarts`: everything already set and the unit
    file present (`workspace.watch_unit(root, 'darwin', name='listen')[1]` created under a
    monkeypatched unit directory or `HOME`); `getpass` and the inbound fake raise if
    called; output names each kept value; `watch.service` saw `uninstall` then `install`;
    `config.toml` and `.wuwei/env` unchanged.
  - `test_setup_slack_without_a_terminal_is_an_owner_action`: `sys.stdin.isatty` false;
    exit 2 with the host-terminal reason; add `'slack'` to the words that
    `test_commands_are_wired` expects from `['setup', '--help']`.
  Run `python -m pytest -q tests/test_setup.py -k slack` (fails: no target).
- [X] T008 [US2] Implement the `target` argument, `run` dispatch, `slack`, `connect` and
  `_first_dm` in `cli/wuwei/commands/setup.py`. Rerun T007, then `python -m pytest -q
  tests/test_setup.py`; passes.
- [X] T009 [US2] Test, `tests/test_setup.py`: `test_setup_leads_into_slack_when_chosen`:
  the fake interview answers `chat='Slack'`, `getpass` returns `''`; `run_setup` applies the
  config, the output contains `Slack: connecting your DM now` and the `Optional:` line
  contains `bin/wuwei setup slack`; with `chat='None'` neither appears and `getpass` is not
  called. Run `python -m pytest -q tests/test_setup.py -k leads_into_slack` (fails).
- [X] T010 [US2] Implement the `_setup` lead-in in `cli/wuwei/commands/setup.py`. Rerun
  T009, then `python -m pytest -q tests/test_setup.py`; passes.

## Phase 3: US3, the interview asks which tools the team uses

- [X] T011 [US3] Test, `tests/test_interview.py`: `test_communication_tools`:
  `effects('chat', 'Microsoft Teams')`, `('chat', 'discord')`, `('tracker', 'GitHub
  Issues')`, `('tracker', 'JIRA')` set their adapter to `none`, and each matching choice's
  description contains `not supported yet` and `interview().BACKLOG`, which is
  `https://github.com/taoq-ai/wuwei/issues/370`; `effects('chat', 'Email')` is
  `{'adapters.chat': 'none'}`; `effects('chat', 'C0123ABCD')` is unchanged; `effects('chat',
  'c-lower!')` raises naming `Slack channel ID` and `another tool`; the Slack choice
  description names `bin/wuwei setup slack`. Change the existing `c-lower` refusal at line
  151 to `c-lower!`. The table test keeps its 2-to-4 rule unchanged. Run `python -m pytest
  -q tests/test_interview.py -k "tools or table or effects"` (fails).
- [X] T012 [US3] Implement `BACKLOG`, `LATER`, the tracker and chat rows and `_chat` in
  `cli/wuwei/interview.py`. Rerun T011, then `python -m pytest -q tests/test_interview.py`;
  passes.
- [X] T013 [US3] Test, `tests/test_setup.py`: extend
  `test_discovery_lists_worktrees_and_owes_other_hosts` with a second repository whose
  origin is `git@gitlab.example.test:acme/app.git`: the lines contain
  `other: example.test is not GitHub` and `app: gitlab.example.test is not GitHub`, each with
  the backlog URL; no line contains `git@` or `https://example.test`; the owed lines are
  unchanged. Run `python -m pytest -q tests/test_setup.py -k other_hosts` (fails).
- [X] T014 [US3] Implement the non-GitHub line in `discover`,
  `cli/wuwei/commands/setup.py`. Rerun T013; passes.

## Phase 4: US4, docs

- [X] T015 [US4] Test, `tests/test_docs.py` (the remote operation test near line 451):
  headings list starts with `## Connect Slack in one command` before `## 1. Remote
  Control, no setup`; the lead section contains `bin/wuwei setup slack`; the pinned strings
  replace `Recorded D-3 option B. Confirm it on the host.` with
  `remote.RECORDED.format(identifier='D-3', option='B')` and
  `remote.NOTED.format(identifier='D-3', option='B')`; `A phone answer is not yet your
  outcome` is absent from remote.md and daily.md. The Python one-liner, `otpauth://totp/`
  and the command-module check stay, and so does the check that the page holds no
  `xox?-` token prefix (describe the token by where it is shown, not by its prefix). Run
  `python -m pytest -q tests/test_docs.py` (fails).
- [X] T016 [US4] Edit `docs/site/remote.md`, `docs/site/daily.md` and
  `docs/site/configuration.md` as plan.md describes. Rerun T015; passes.

## Phase 5: finish

- [X] T017 Run `python -m pytest -q` from the repository root; everything passes. Grep the
  changed files for em-dashes, emojis, `xox` tokens other than the test fakes, and absolute
  local paths; remove any.
