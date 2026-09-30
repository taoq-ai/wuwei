# Tasks: decisions and health are visible on both ends

**Input**: `specs/273-remote-visibility/` (spec.md, plan.md)

Test first, always: each test task is written, run with the command given, and seen to
fail for the expected reason before its implementation task starts. Run from the
repository root with the interpreter your task names. No absolute local paths, emojis or
em-dashes in any file.

## Phase 1: US4 stopped sessions are not live (P1)

- [X] T001 Test, `tests/test_sessions.py`: a registry row with `stopped` is listed by
  `wuwei sessions` with that `stopped` value; a row without it has no `stopped` key. Run
  `python -m pytest -q tests/test_sessions.py -k stopped`.
- [X] T002 Test, `tests/test_remote.py`
  (`test_issue_acceptance_stop_all_drops_the_live_session_count`): two remote rows and one
  adhoc row, all fresh; `status --line` has `sessions 3`; after `remote.stop(ws, 'all',
  ...)` it has `sessions 1` and `status --json` `sessions == 1`. Run
  `python -m pytest -q tests/test_remote.py -k live_session_count`.
- [X] T003 Implement, `cli/wuwei/sessions.py` (`rows`: carry `stopped`) and
  `cli/wuwei/commands/status.py` (`snapshot`: count rows neither stale nor stopped).

## Phase 2: US5 the status line carries the listener (P1)

- [X] T004 Test, `tests/test_listen.py`
  (`test_issue_acceptance_dead_listener_shows_in_the_status_line`): a `listen: clock`
  today, then `later(monkeypatch, 300)`; `status --line` contains `listen dead`,
  `wuwei nudges` has one row `{'tier': 'page', 'source': 'listen: health', ...}` with the
  reason `listen dead: no clock line within deadline`, and `status --json` has
  `listen == 'dead'`. Run `python -m pytest -q tests/test_listen.py -k status`.
- [X] T005 Test, `tests/test_listen.py`: table over the listener states with the `case`
  fixture (`adapters.inbound = "fake"`): fresh clock gives no `listen` part and
  `listen == 'alive'`; installed unit (`workspace.watch_unit(root, name='listen')`) with
  no clock gives `listen dead`; no clock and no unit gives `listen off` and no row;
  with `adapters.inbound = "none"` (config without the inbound line) no clock gives no
  `listen` part and `listen == 'none'`; a clock line in the future gives a
  `listen: health` nudge and `listen unmeasured`. Run
  `python -m pytest -q tests/test_listen.py -k status`.
- [X] T006 Implement, `cli/wuwei/commands/status.py`: collect `listen: clock` in the scan
  loop, run the watch rule for both names in one loop, return the listener state,
  `snapshot` sets `listen` (and `none` for off without an inbound adapter), `line` shows
  it. Keep the existing watch tests green (`python -m pytest -q tests/test_quiet_sweeps.py tests/test_watch.py tests/test_signal_status.py`).

## Phase 3: US1 every owner decision reaches the DM once (P1)

- [X] T007 Test, `tests/test_listen.py`: `'decision.escalated'` is refused by
  `wuwei event` naming `wuwei listen`, and is in `signal.SILENT` (extend
  `test_listener_kinds_are_reserved_and_silent`). Run
  `python -m pytest -q tests/test_listen.py -k reserved`.
- [X] T008 Implement, `cli/wuwei/signal.py` (`SILENT`) and `cli/wuwei/commands/event.py`
  (`EVENT_PRODUCERS`).
- [X] T009 Test, `tests/test_remote.py`: `escalate_new(ws, transport)` with a decision
  routed on the host (`routed(ws)`) sends `[escalation(ws, 'D-1')]`, records one
  `decision.escalated {'id': 'D-1'}`, returns 0; a second call sends nothing; with a
  transport whose `dm` returns exit 2, nothing is recorded and it returns 2, and the next
  call with a working transport sends it; a question the lint refuses sends
  `D-1 is waiting in the workspace.` and records it. Run
  `python -m pytest -q tests/test_remote.py -k escalate_new`.
- [X] T010 Test, `tests/test_remote.py`: a `plan` turn that routes D-1 still sends
  `[escalation(ws, 'D-1'), 'Session ...: turn ended, 1 decisions waiting.']` (the existing
  acceptance test), and afterwards `escalate_new` sends nothing; a host decision routed
  before a turn is sent by that turn too (before the `Session` line). Run
  `python -m pytest -q tests/test_remote.py -k "escalate or plan_starts"`.
- [X] T011 Implement, `cli/wuwei/remote.py`: `escalate_new`; `_turn` uses it in place of
  the `for identifier in new:` loop.
- [X] T012 Test, `tests/test_listen.py`
  (`test_issue_acceptance_host_decision_reaches_the_dm`): with `SLACK_OWNER_DM_CHANNEL`
  set and `remote.TRANSPORT.dm` monkeypatched to record, a decision written with
  `decision.write` and routed with `decision.route_owner` on the host is sent by the next
  `listen.tick` (text starts with `D-1: `), once across two ticks. With
  `responder.enabled = false`, or without `SLACK_OWNER_DM_CHANNEL`, nothing is sent and no
  `decision.escalated` is recorded. A `dm` that returns exit 2 makes the tick return 2;
  a corrupt decision record prints `listen escalate unmeasured:` and the tick returns 2.
  Run `python -m pytest -q tests/test_listen.py -k "host_decision or escalat"`.
- [X] T013 Implement, `cli/wuwei/listen.py` (`tick`: call `remote.escalate_new` inside
  the responder branch when the DM channel is set; `import os`).

## Phase 4: US2 a phone answer is visible on the host and never stored twice (P1)

- [X] T014 Test, `tests/test_remote.py`: `remote.ANSWERED` filled with `D-1`/`A` passes
  the outward lint (extend `test_fixed_lines_pass_the_outward_lint`). Run
  `python -m pytest -q tests/test_remote.py -k fixed_lines`.
- [X] T015 Test, `tests/test_remote.py`
  (`test_issue_acceptance_a_conflicting_second_answer_is_refused`): `routed(ws)`;
  `option A on D-1` returns 0 with `Recorded D-1 option A. Confirm it on the host.`;
  `option B on D-1` returns 1 with the `ANSWERED` line quoting A; `drop it` (resolving to
  the Do nothing option) is refused the same way; `option A on D-1` again returns 0 with
  the `Recorded` line; `decision.replied` events stay exactly `[{'id': 'D-1', 'option':
  'A'}]`. With a live remote session holding D-1 (`remote_row`), the second answer calls
  no runtime. Run `python -m pytest -q tests/test_remote.py -k conflicting`.
- [X] T016 Implement, `cli/wuwei/remote.py`: `ANSWERED`, `replied`, and the check in
  `handle` before recording.
- [X] T017 Test, `tests/test_signal_status.py`
  (`test_issue_acceptance_a_phone_answer_shows_on_the_host`): a day with `ROUTED` D-2 and
  a `decision.replied {D-2, A}` event (plus a later `{D-2, B}` written as legacy
  evidence): `wuwei nudges` has exactly one D-2 row, `{'tier': 'nudge', 'source':
  'decision.answered', 'lane': 'Decisions', 'reason': 'D-2 answered from the phone:
  option A, confirm with decision outcome D-2 A'}`; `status --line` contains that reason
  and `nudges 1`; `status --json` `answered` is `[that reason]`; with an owner outcome for
  D-2 the row and the part disappear. Run
  `python -m pytest -q tests/test_signal_status.py -k phone_answer`.
- [X] T018 Implement, `cli/wuwei/commands/status.py`: collect the first
  `decision.replied` per id in the scan loop, render `decision.answered`, `snapshot`
  `answered`, `line` parts.
- [X] T019 Test, `tests/test_listen.py`: with a routed decision and a `decision.replied`
  event today, `lifecycle.session_start({'cwd': str(root)})` returns the same code as
  without the reply and its message contains `answered from the phone: option`. Run
  `python -m pytest -q tests/test_listen.py -k session_start`.
- [X] T020 Implement, `cli/wuwei/guards/lifecycle.py` (`session_start`: add the answered
  lines from `status.attention`).

## Phase 5: US3 a refused-sender page clears when the pin is re-confirmed (P2)

- [X] T021 Test, `tests/test_remote.py`: update
  `test_issue_acceptance_changed_identity_is_refused_and_alerted` so the refused payload
  is `{'id': 'D1/1.000001', 'pin': 'T1/U1'}`. New test
  `test_refused_page_clears_when_the_pin_is_edited`: after a refusal, `wuwei nudges` has
  one `remote.refused` page; with the config unchanged it stays; after rewriting
  `.wuwei/config.toml` with `owner = "T9/U1"` it is gone and `status --json` `pages == 0`.
  A `remote.refused {id}` event without `pin` still pages after the edit. Run
  `python -m pytest -q tests/test_remote.py -k refused`.
- [X] T022 Implement, `cli/wuwei/remote.py` (`handle`: record the pin) and
  `cli/wuwei/commands/status.py` (`scan`: skip a refused event whose pin differs from the
  current one, pin loaded once).

## Phase 6: US6 `config check` reports the pin and the TOTP secret (P2)

- [X] T023 Test, `tests/test_env_credentials.py`
  (`test_issue_acceptance_empty_pin_is_a_config_finding`): with `adapters.inbound =
  "slack"`, the Slack credentials set and an empty pin, `config check` exits 1 and prints
  `control_plane.owner: missing`; a malformed pin (`U1`) prints `control_plane.owner:
  invalid` and exits 1; a valid pin prints `control_plane.owner: set`, never the pin
  value; `WUWEI_TOTP_SECRET` set or unset prints `set` or `missing (confirm replies are
  the only second factor)` without changing the exit code and never prints the value;
  with `adapters.inbound = "none"` there is no `Control plane:` section. Keep
  `code_host="none"` as the `case` fixture does so only these lines decide the exit.
  Update the `inbound="slack"` row of `test_config_reports_missing_and_set` to carry
  `[control_plane]\nowner="T1/U1"` in its settings, or its exit-0 half turns red. Run
  `python -m pytest -q tests/test_env_credentials.py -k "pin or missing_and_set"`.
- [X] T024 Implement, `cli/wuwei/remote.py` (`PIN`, used by `sender`) and
  `cli/wuwei/commands/config.py` (`Control plane:` section; `import re`).

## Phase 7: Docs and polish

- [X] T025 Test, `tests/test_docs.py` (`test_remote_runbook_matches_the_code`): add
  `answered from the phone`, `already has option`, `control_plane.owner: missing`,
  `WUWEI_TOTP_SECRET: set` and `listen dead` in the status line context to the checked
  phrases; assert section 7 no longer contains `for decisions a \`plan\` session raises`.
  Run `python -m pytest -q tests/test_docs.py -k remote`.
- [X] T026 Docs, `docs/site/remote.md` sections 3, 4, 5, 6, 7 and 8 and
  `docs/site/configuration.md` (the `listen.dead_seconds` and `control_plane.owner` rows,
  the listener section, the `config check` paragraph) as in plan.md section 8.
- [X] T027 Run the full suite, `python -m pytest -q`, and fix any existing test that
  asserts an exact event list now containing `decision.escalated`. Check every file you
  wrote for em-dashes, emojis and absolute local paths.
