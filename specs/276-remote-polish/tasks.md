# Tasks: phone answers as one status segment, an ack for a refused-sender page, and the section 3 quote

**Input**: `specs/276-remote-polish/` (spec.md, plan.md)

Test first, always: each test task is written, run with the command given, and seen to
fail for the expected reason before its implementation task starts. Run from the
repository root with the interpreter your task names. No absolute local paths, emojis or
em-dashes in any file.

## Phase 1: US1 phone answers take one status segment (P1)

- [X] T001 Test, `tests/test_signal_status.py`
  (`test_issue_acceptance_four_phone_answers_are_one_status_segment`): `day(...)` with
  `decision_routes` D-1 to D-4 (each `{'reversibility': 'two-way', 'recommendation': 'A'}`)
  and one `decision.replied` event per id (options A, B, A, A); `status --line` output
  contains `phone answers 4`, does not contain `answered from the phone`, and
  `len(line) < 160`; `wuwei nudges` has exactly four `decision.answered` rows whose
  reasons are `D-n answered from the phone: option X, confirm with decision outcome D-n X`;
  `status --json` `answered` still lists the four reasons. Run
  `python -m pytest -q tests/test_signal_status.py -k phone_answer`.
- [X] T002 Test, `tests/test_signal_status.py`: update
  `test_issue_acceptance_a_phone_answer_shows_on_the_host` so the `status --line` check is
  `('phone answers 1' in text) == bool(expected)` and `reason not in text`; the `nudges`
  and `--json` checks stay as they are. Run the same command as T001.
- [X] T003 Implement, `cli/wuwei/commands/status.py` (`line`: one `phone answers N` part
  in place of `parts.extend(data['answered'])`). Then run
  `python -m pytest -q tests/test_remote.py tests/test_listen.py -k "status_sends or session_start"`
  to confirm the DM reply and SessionStart tests stay green.

## Phase 2: US2 the owner acknowledges a refused-sender page (P1)

- [X] T004 Test, `tests/test_state_allowlist.py`: add
  `('remote.acknowledged', 'wuwei remote ack')` to the
  `test_nonfree_events_refuse_without_append` parameters. Test, `tests/test_remote.py`
  (`test_acknowledged_kind_is_reserved_and_silent`): `main(['event', 'remote.acknowledged'])`
  returns 1 naming `wuwei remote ack`, and `signal.classify({'kind': 'remote.acknowledged',
  'payload': {}}, {})[0] == 'silent'`. Run
  `python -m pytest -q tests/test_state_allowlist.py tests/test_remote.py -k "acknowledged or nonfree"`.
- [X] T005 Implement, `cli/wuwei/signal.py` (`SILENT`) and `cli/wuwei/commands/event.py`
  (`EVENT_PRODUCERS['remote.acknowledged'] = 'owner host wuwei remote ack'`).
- [X] T006 Test, `tests/test_remote.py`
  (`test_issue_acceptance_remote_ack_clears_a_refused_page`): with `ws`, a refusal from
  `T9/U1` via `remote().handle(ws, event('D1/1.000001', 'status', sender='T9/U1'),
  transport=Transport())`; `refused_pages(capsys)` has one page. Monkeypatch
  `integrity._host_confirm` with a recorder that returns True and keeps
  `(fingerprint, prompt)`. `main(['remote', 'ack'])` returns 0; the recorded fingerprint
  is `sha256(b'D1/1.000001').hexdigest()[:12]` and the prompt contains `D1/1.000001`;
  `payloads(ws, 'remote.acknowledged') == [{'ids': ['D1/1.000001']}]`;
  `refused_pages(capsys) == []` and `status --json` `pages == 0`. A second refusal
  (`D1/2.000001`) then pages again, and the next `remote ack` confirms only
  `['D1/2.000001']`. With no unacknowledged refusal, `remote ack` returns 0, prints
  `remote ack: no refused sender message today`, never calls the recorder, and records
  nothing. With a recorder returning False, it returns 1, prints
  `remote ack: owner confirmation declined` on stderr, records nothing, and the page
  stays. Run `python -m pytest -q tests/test_remote.py -k remote_ack`.
- [X] T007 Test, `tests/test_remote.py`
  (`test_issue_acceptance_remote_ack_without_a_terminal_is_an_owner_action`): a refusal,
  then `builtins.open` monkeypatched to raise `OSError(6, 'Device not configured')` for
  `/dev/tty` (as in `tests/test_decision.py::test_owner_outcome_without_a_terminal_names_the_owner_action`);
  `main(['remote', 'ack'])` returns 2, stderr is exactly
  `wuwei remote: this is an owner action: run it in a host terminal\n`, no
  `remote.acknowledged` event exists, and the page stays. Run
  `python -m pytest -q tests/test_remote.py -k remote_ack`.
- [X] T008 Implement, `cli/wuwei/remote.py` (`acknowledge(root)`), the new
  `cli/wuwei/commands/remote.py` (`register`, `run`), and `cli/wuwei/commands/status.py`
  (`scan`: the `remote.acknowledged` branch before the `SILENT` check; `remote.refused`
  joins the id-keyed kinds). Keep `python -m pytest -q tests/test_remote.py -k refused`
  green (the #273 pin rule).
- [X] T009 Test, `tests/test_owner_actions.py`: add `('remote', 'ack')` to `ACTIONS`; add
  `'git remote -v'` and `'bin/wuwei steward ack remote-fix-3'` to the
  `test_ordinary_work_passes` table. Test, `tests/test_protect_state.py`
  (`test_seat_cannot_acknowledge_refusals`, mirroring `test_seat_cannot_recover_state`):
  `bin/wuwei remote ack` and `python3 -P -m wuwei remote ack` inside the workspace give
  `(1, 'Remote acknowledgements require the owner terminal, outside agent tools.')`, and
  `(0, '')` outside it. Run
  `python -m pytest -q tests/test_owner_actions.py tests/test_protect_state.py -k "pair9 or ordinary or acknowledge"`.
- [X] T010 Implement, `cli/wuwei/guards/protect_state.py` (`_OWNER_ACTIONS`: the
  `('remote', 'ack')` row with its comment). Then run
  `python -m pytest -q tests/test_owner_actions.py tests/test_protect_state.py tests/test_launcher_relevance.py tests/test_shell.py`.

## Phase 3: US3 section 3 quotes the line as printed (P2)

- [X] T011 Test, `tests/test_env_credentials.py`
  (`test_issue_acceptance_empty_pin_is_a_config_finding`): the empty-pin row asserts
  `'Control plane:\n  ' + PIN_MISSING` in the output, with `PIN_MISSING` imported from
  `wuwei.commands.config`. Run
  `python -m pytest -q tests/test_env_credentials.py -k pin` (fails on the import).
- [X] T012 Implement, `cli/wuwei/commands/config.py` (`PIN_MISSING` constant, used by the
  missing branch; output unchanged).
- [X] T013 Test, `tests/test_docs.py` (`test_remote_runbook_matches_the_code`): replace
  the `'control_plane.owner: missing'` phrase with `PIN_MISSING` asserted inside the
  section 3 slice (`pin`, whitespace-flattened); add `'phone answers 1'`,
  `'bin/wuwei remote ack'` and `'remote.acknowledged'` to the checked phrases; assert
  `'stays paged until the day ends'` is gone from section 3. Run
  `python -m pytest -q tests/test_docs.py -k remote` (fails on the page).
- [X] T014 Docs, `docs/site/remote.md` sections 3 and 7, `docs/site/configuration.md`
  (listener section closing paragraph), `docs/site/reference.md` (host terminal actions
  table row `bin/wuwei remote ack`, digest yes) and `docs/site/concepts.md` (owner
  command list), as in plan.md section 7. Run `python -m pytest -q tests/test_docs.py`.

## Phase 4: Polish

- [X] T015 Run the full suite, `python -m pytest -q`, and fix any existing test that
  asserts a status line containing `answered from the phone` or a `remote.refused` row
  key. Check every file you wrote for em-dashes, emojis and absolute local paths.
