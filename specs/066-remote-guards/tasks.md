# Tasks: remote-command guards (pinned identity, second factor, stop all)

**Input**: `specs/066-remote-guards/` (spec.md, plan.md)

Test first, always: each test task is written, run with the command given, and seen to
fail for the expected reason before its implementation task starts. Run from the
repository root with the interpreter your task names.

## Phase 1: Foundation (config, credential, fixtures)

- [X] T001 Test, `tests/test_remote.py`: `workspace.load_config` returns
  `control_plane.owner == ''` by default and the configured string when set; and
  `'WUWEI_TOTP_SECRET' in env.CREDENTIALS`. Run `python -m pytest -q tests/test_remote.py -k config_and_credential`.
- [X] T002 Implement, `cli/wuwei/workspace.py` (SCHEMA `control_plane.owner`, `(str, "")`)
  and `cli/wuwei/env.py` (`WUWEI_TOTP_SECRET` in `CREDENTIALS`). Add the commented key to
  `templates/workspace/config.toml` `[control_plane]` and a row to
  `docs/site/configuration.md` so `tests/test_docs.py` stays green.
- [X] T003 Fixtures, `tests/test_remote.py`: `OWNER` pins `T1/U1`, `event()` sender
  `'T1/U1'`, `ws` patches `agent_launch.free_memory` to `2**40`. No behaviour yet; the
  existing suite for the file still passes.

## Phase 2: US1 pinned identity (P1)

- [X] T004 Test, `tests/test_reference_adapters.py`: Slack inbound rows with `team`
  produce `sender == 'T1/U0OWNER'`; a row without `team` produces `'/U0OWNER'`; a
  non-string `team` fails the poll. Run `python -m pytest -q tests/test_reference_adapters.py -k inbound`.
- [X] T005 Implement, `adapters/inbound/slack.py`: `team = row.get('team', '')`, string
  check, `'sender': f'{team}/{user}'`.
- [X] T006 Test, `tests/test_remote.py`: `sender(config, event)` table: pin equal is
  `owner`, `T9/U1` and `/U1` are `changed`, `T1/U2` is `other`; empty or malformed pin
  raises `ValueError` naming `control_plane.owner` and the sender.
- [X] T007 Test, `tests/test_remote.py` (issue acceptance 1):
  `test_issue_acceptance_changed_identity_is_refused_and_alerted`: `plan today` from
  `T9/U1` returns 1, no runtime call, events `remote.refused {id}` only, sent is
  `[CHANGED]`. Same for `status`.
- [X] T008 Test, `tests/test_remote.py`: messages from `T1/U2` return 0 and send nothing;
  two messages from the same stranger record one `remote.ignored {sender}`; a second
  stranger records a second one.
- [X] T009 Test, `tests/test_remote.py`: with the pin unset, `status` returns 2, sends
  `FAILED`, and the printed reason names `control_plane.owner` and the sender id.
- [X] T010 Implement, `cli/wuwei/remote.py`: `sender`, `_today`, `CHANGED`, and the
  `other`/`changed` branches in `handle` per plan.md section 5.
- [X] T011 Test, `tests/test_signal_status.py` and `tests/test_remote.py`:
  `remote.ignored` silent, `remote.refused` page, both reserved to `wuwei listen`
  (`main(['event', kind]) == 1`).
- [X] T012 Implement, `cli/wuwei/signal.py` and `cli/wuwei/commands/event.py`.

## Phase 3: US2 second factor (P1)

- [X] T013 Test, `tests/test_remote.py`: `totp(b'12345678901234567890', t // 30)`
  equals the last six digits of the RFC 6238 SHA1 vectors for t = 59, 1111111109,
  1111111111, 1234567890, 2000000000 (`287082`, `081804`, `050471`, `005924`, `279037`).
- [X] T014 Implement, `cli/wuwei/remote.py`: `totp`.
- [X] T015 Test, `tests/test_remote.py`: `split` table (`'plan today 123456'` gives
  `('plan today', '123456')`; `'plan'`, `'stop 12345678'`, `'ask about 123456?'` keep
  the text and no code); `parse('Confirm.') == ('confirm', '')`.
- [X] T016 Implement, `cli/wuwei/remote.py`: `split`, `confirm` in `parse`.
- [X] T017 Test, `tests/test_remote.py` (issue acceptance 2):
  `test_issue_acceptance_plan_without_a_second_factor_starts_nothing`: `plan today`,
  `plan today 000000` (wrong code) and `ask what changed` with no secret set each return
  1, make no runtime call, write no session row, record `remote.pending {id, command}`,
  and send `[CONFIRM]`.
- [X] T018 Test, `tests/test_remote.py`: with `WUWEI_TOTP_SECRET` set (base32 of the RFC
  key) and a fresh message ts, `plan today <code>` starts the session;
  `remote.confirmed {id, factor: 'code', step}` precedes `remote.started`; the same code
  again (new message id) is pending; a code in a message 121 s old is pending; a
  non-base32 secret is exit 2 and the secret text is not in the output.
- [X] T019 Implement, `cli/wuwei/remote.py`: `code_step` (with the ponytail comment),
  `CONFIRM`, the `FACTOR` branch in `handle`; delete `EXECUTABLE`, `GUARDED` and the
  pending gate. Replace `test_gate_records_guarded_commands_as_pending` and
  `test_gate_records_a_reply_that_would_resume_a_session`; turn `open_gate` into a
  fixture that patches `remote.code_step` to return a step.
- [X] T020 Test, `tests/test_remote.py`: `ask what changed` then `confirm` (new id)
  runs the ask with prompt `ASK_PROMPT + 'what changed'` and thread = the ask's inbox id
  (the line stored with `inbox.store` in the test); records
  `remote.confirmed {id, factor: 'reply'}`; a second `confirm` sends `[NOTHING]`;
  `confirm` with nothing pending, with the pending event 121 s old (`WUWEI_NOW`
  advanced), or with only a #65-era `remote.pending` for `stop` sends `[NOTHING]` and
  runs nothing. Two pending commands: `confirm` runs only the latest.
- [X] T021 Implement, `cli/wuwei/remote.py`: `confirmation`, `NOTHING`, the confirm branch
  in `handle`.
- [X] T022 Test, `tests/test_remote.py`: `status`, `report`, `stop 0f8fad5b` and a
  decision reply that resumes a session run without a factor (no `remote.pending`).
- [X] T023 Test, `tests/test_signal_status.py`, `tests/test_remote.py`:
  `remote.confirmed` silent and reserved. Implement in `cli/wuwei/signal.py` and
  `cli/wuwei/commands/event.py`.

## Phase 4: US3 stop all (P1)

- [X] T024 Test, `tests/test_listen.py` (issue acceptance 3):
  `test_issue_acceptance_stop_all_stops_every_session_in_one_tick`: pin `T1/U1`,
  `SLACK_OWNER_DM_CHANNEL=D1`, two live remote rows, the fake inbound returns one
  `stop all` event from `T1/U1`; after one `listen.tick` both rows carry `stopped`, no
  runtime call, no `remote.pending`. Patch `remote.TRANSPORT.dm` to record sends.
- [X] T025 Test, `tests/test_remote.py`: `stop all` from `T9/U1` (changed identity)
  stops every live remote session and records no `remote.refused`; `stop 0f8fad5b` from
  `T9/U1` is refused.
- [X] T026 Implement: nothing new if T010 and T019 are right; fix `handle` until T024 and
  T025 pass.

## Phase 5: US4 host limits (P2)

- [X] T027 Test, `tests/test_remote.py`: with `free_memory` below the floor, `start` and
  `resume` return 1, send `[LOW_MEMORY]`, make no runtime call and register nothing;
  with `free_memory` raising `ValueError('free memory unmeasured')`, `handle` returns 2.
- [X] T028 Implement, `cli/wuwei/remote.py`: `memory_floor`, `LOW_MEMORY`, first line of
  `_turn`.
- [X] T029 Test, `tests/test_runtime.py`: the headless argv ends the flag list with
  `--strict-mcp-config` and has no `--mcp-config`.
- [X] T030 Implement, `adapters/runtime/claude.py`: the flag and the updated comment.

## Phase 6: US5 mutation tests (P1)

- [X] T031 Test, `tests/test_guard_mutation.py`: add `('wuwei.remote', 'sender')`,
  `('wuwei.remote', 'code_step')`, `('wuwei.remote', 'confirmation')` and
  `('wuwei.remote', 'memory_floor')` to `required` in
  `test_special_policies_have_mutation_probes` and to `SPECIAL_TESTS`; run it and see it
  fail (no tests yet).
- [X] T032 Test, `tests/test_guard_mutation.py`: one `test_disabling_remote_<name>_makes_its_probe_red`
  per function, in the `assert_refused` style: the probe (a changed-identity `plan`
  returns 1; a codeless `plan` records pending; a stale `confirm` sends `NOTHING`; a
  low-memory `start` returns 1 with no runtime call) passes, then with the function
  patched permissive (`lambda *a: 'owner'`, `lambda *a: 1`, returning the pending line,
  `lambda *a: True`) `pytest.raises(AssertionError)`.

## Phase 7: Docs and finish

- [X] T033 [P] Docs, `docs/site/configuration.md` "Commands from the owner DM" and
  `docs/site/adapters.md` line 61, per plan.md section 6. Run
  `python -m pytest -q tests/test_docs.py`.
- [X] T034 Test, `tests/test_remote.py::test_fixed_lines_pass_the_outward_lint`: lists
  `VOCABULARY`, `UNAVAILABLE`, `FAILED`, `CONFIRM`, `NOTHING`, `CHANGED`, `LOW_MEMORY`.
- [X] T035 Run `python -m pytest -q` from the repository root: everything passes. Check
  every file written for em-dashes, emojis, absolute local paths and secrets; remove any.
