# Tasks: The DM path works from the runbook alone

**Input**: `specs/272-remote-dm-path/spec.md` and `plan.md`

**Tests**: required (constitution IV). Each behaviour has a test task that is written,
run and seen failing for the stated reason before its implementation task.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- Run tests with `python -m pytest -q <file>::<test>` from the repository root.

## Phase 1: Setup

- [X] T001 [P] In `tests/conftest.py`, also `monkeypatch.delenv('SLACK_API_BASE', raising=False)` in the autouse fixture.

## Phase 2: User Story 1, the channel survives storage (P1)

- [X] T002 [US1] Test in `tests/test_env_credentials.py`: `test_owner_dm_channel_is_not_redacted`. With a real `0600` `.wuwei/env` holding `SLACK_BOT_TOKEN=<KEY>`, `SLACK_OWNER_DM_CHANNEL=D0123ABC` and `WUWEI_TOTP_SECRET=<other>`, inside `env.session()` after `env.load(case)`: `redact.known_values('D0123ABC/1.000001')` is unchanged while both secrets become `[REDACTED]`; a second case sets `SLACK_OWNER_DM_CHANNEL` and `SLACK_BOT_TOKEN` with `monkeypatch.setenv` and enters `env.session()` without a file, same result. Fails today: the channel is redacted.
- [X] T003 [US1] Implement in `cli/wuwei/env.py`: `PUBLIC = ('SLACK_OWNER_DM_CHANNEL',)` and skip it in `session()` (line 33) and both redaction updates in `load()` (lines 79 and 85). T002 passes; `test_seat_children_do_not_inherit_credentials` still passes.
- [X] T004 [US1] Test in `tests/test_remote.py`: `test_unmatched_channel_logs_and_is_not_a_command`. `remote().handle(ws, event('C9/1790769590.000100', 'status', channel='C9'))` returns 0, sends nothing, and captured stdout has exactly one line containing `remote.unmatched` and `C9/1790769590.000100` and not the text `status`. Fails today: no output.
- [X] T005 [US1] Implement in `cli/wuwei/remote.py:handle` (line 200): print `listen remote.unmatched: {event.get("id")} is not in the owner DM channel` with `flush=True` before `return 0`. T004 passes.

## Phase 3: User Story 2, replies to the owner without `owner.name` (P1)

- [X] T006 [US2] Test in `tests/test_outward.py`: `test_owner_addressed_lint_skips_third_person_rules_only`. With a config whose `owner.name` is `""`: `outward.lint('Report ready.', 'chat', config)` is still exit 2 and `lint(..., to_owner=True)` is 0. With `owner.name = "Dry Run Operator"` and pronouns `they/them`: `lint(remote.CONFIRM, 'chat', config)` is 1 and with `to_owner=True` is 0; `lint('They look done.', ..., to_owner=True)` is 0; `lint('wuwei is busy.', ..., to_owner=True)` is still 1 (patterns stay on); `outward.check_lint({'text': remote.CONFIRM, 'channel': 'D1'}, root, config, {'chat'}, to_owner=True)` is 0 and without the keyword is 1. Fails today: unknown keyword.
- [X] T007 [US2] Implement in `cli/wuwei/outward.py`: `to_owner=False` keyword on `lint` (skip lines 39-40 and the loop at 59-62 when set) and on `check_lint` (passed through); add the `OWNER_UNSET` constant from plan.md. T006 passes; `tests/test_outward.py` stays green.
- [X] T008 [US2] Tests in `tests/test_remote.py`: `test_owner_dm_reply_needs_no_owner_name`, parametrized over `OWNER` without the `[owner]` table and with `name = "Dry Run Operator"`: `remote().dm(remote().CONFIRM, root=ws)` and `remote().dm(remote().FAILED, root=ws)` both exit 0 and reach the `chat` fixture. Change `test_dm_lint_finding_sends_nothing` (line 138) to send `'wuwei is busy.'`. Fails today: exit 2 and exit 1.
- [X] T009 [US2] Implement in `cli/wuwei/remote.py:dm` (lines 153-155): pass `to_owner=True` to `outward.check_lint`; update the comment at line 16. T008 passes.
- [X] T009a [US2] Review fix F1: test `test_owner_dm_channel_that_is_not_a_dm_gets_the_full_lint` in `tests/test_remote.py` (with `SLACK_OWNER_DM_CHANNEL` set to `C0123ABC` or `G0123ABC`, a reply naming the owner is refused and nothing is sent), then in `remote.dm` pass `to_owner` only when `SLACK_OWNER_DM_CHANNEL` starts with `D`.
- [X] T010 [P] [US2] Test in `tests/test_env_credentials.py`: `test_config_check_reports_owner_name`. With the `case` config (no owner name) `main(['config', 'check'])` output contains `Owner:` and `outward.OWNER_UNSET` once, and the exit code equals the one before this change (0 with `LINEAR_API_KEY` set in `.wuwei/env`); after adding `[owner]\nname = "Robin Example"\n` the output has `owner.name: set`. Fails today: no Owner section.
- [X] T011 [US2] Implement in `cli/wuwei/commands/config.py:run`: print `Owner:` and the set or `OWNER_UNSET` line after the Credentials loop, status unchanged. T010 passes.
- [X] T012 [P] [US2] Test in `tests/test_listen.py`: `test_unset_owner_name_is_logged_once`. With the `case` fixture (no owner name), two stored events and `main(['listen', '--once'])`, `capsys` stdout contains `outward.OWNER_UNSET` exactly once; with `[owner]\nname = "Robin Example"\n` added to the config it is absent. Fails today: never printed.
- [X] T013 [US2] Implement in `cli/wuwei/listen.py:run`: load the config once and print `'listen ' + outward.OWNER_UNSET` (flushed) when `owner.name` is blank, before `watch.serve`. T012 passes.

## Phase 4: User Story 3, `listen --once` exit codes (P2)

- [X] T014 [US3] Tests in `tests/test_listen.py`: change `test_once_returns_the_tick_code` (line 343) to expect 0 and 0; change every stored-batch `tick(root) == 1` (lines 102, 111, 153, 193, 209, 379, 404) to `== 0`; add `test_refused_command_is_a_normal_poll_and_unrun_is_2`: with `remote.handle` monkeypatched to return 1 then 2 for two events, `listen().tick(root)` returns 0 for the first poll and 2 for the second. In `tests/test_reference_adapters.py` change lines 347 and 359 to `== 0`. Fail today: 1 is returned.
- [X] T015 [US3] Implement in `cli/wuwei/listen.py:tick`: delete `code = int(bool(stored.data))` (line 51) and replace line 70 with `if remote.handle(root, rows[index]) == 2: code = 2`. T014 passes; `test_failing_source_or_store_leaves_the_cursor` still returns 2.

## Phase 5: User Story 4, `SLACK_API_BASE` (P2)

- [X] T016 [P] [US4] Tests in `tests/test_reference_adapters.py`: `test_slack_api_base_override` sets `SLACK_API_BASE=http://127.0.0.1:9/fake` (no trailing slash) with `SLACK_BOT_TOKEN`, replays one post and one history page, and asserts the URLs are `http://127.0.0.1:9/fake/chat.postMessage` and start with `http://127.0.0.1:9/fake/conversations.history?`. `test_slack_api_base_must_be_https_or_loopback`, parametrized over `http://example.test/api/` and `ftp://example.test/api/`: `slack.dm('x')` (`importlib.import_module('adapters.chat.slack')`, with `SLACK_OWNER_DM_CHANNEL` set) returns exit 2, the reason does not contain the value, and `replay` recorded no call. `test_slack_inbound_events` keeps asserting the default `https://slack.com/api/`. Fail today: the base is ignored.
- [X] T017 [US4] Implement in `adapters/chat/slack.py`: the `_url(method)` helper from plan.md, used by `_send` (line 22) and `history` (line 52). Add `SLACK_API_BASE` to `CREDENTIALS` in `cli/wuwei/env.py`. T016 passes.

## Phase 6: The runbook, end to end through the real `.wuwei/env` (US1, US2, US4 acceptance)

- [X] T018 [US1] Test in `tests/test_remote.py`: `test_runbook_hello_through_real_env` (FR-010). Delete `SLACK_BOT_TOKEN`, `SLACK_USER_TOKEN`, `SLACK_API_BASE`, `WUWEI_TOTP_SECRET` and `WUWEI_WORKSPACE` from the environment; `monkeypatch.chdir(tmp_path)`; `monkeypatch.setattr(init, '_register_mcp', lambda root: 0)`; `main(['init', str(tmp_path)]) == 0`. In `.wuwei/config.toml` replace `chat = "none"` with `chat = "slack"` plus `inbound = "slack"` (section 2); leave `owner.name` and `control_plane.owner` empty. Write `.wuwei/env` with mode `0600`: `SLACK_BOT_TOKEN=<fake token>`, `SLACK_OWNER_DM_CHANNEL=D0123ABC`, `SLACK_API_BASE=http://127.0.0.1:9/fake/`. Monkeypatch `urllib.request.urlopen` with a fake Slack that asserts every URL starts with the base, returns queued DM messages once from `conversations.history` (`{'user': 'U0123ABC', 'team': 'T0123ABC', 'text': 'hello', 'ts': '<now>.000100'}`) and records `chat.postMessage` texts (reply objects need `status = 200`, `read(n)` and context-manager support; `io.BytesIO` subclass is enough). Then: `main(['listen', '--once']) == 2`, stdout has `this message came from T0123ABC/U0123ABC` and `OWNER_UNSET` once, the posts are `[remote.FAILED]`; set `control_plane.owner = "T0123ABC/U0123ABC"`, queue a second `hello`, `main(['listen', '--once']) == 0` and the posts end with `remote.VOCABULARY`. Assert the inbox lines carry `D0123ABC` in `channel` and `id`, and that neither the token nor the base appears in captured output, `inbox.jsonl` or today's `events.jsonl`. Fails on main at the first reply (F1, then F2).
- [X] T019 [US1] Run T018; it must pass with T003 to T017 in place and no further production change. If it does not, fix the root cause in the shared function named by the failure, not in the test.

## Phase 7: Docs (US5 and FR-009)

- [X] T020 [US5] Test in `tests/test_docs.py:test_remote_runbook_matches_the_code`: add `SLACK_API_BASE` to the credential tuple (in `env.CREDENTIALS` and on the page); assert `'owner.name: not set'` appears and `` '`owner.name`' `` appears inside section 3; assert section 5 contains `listen --once` with `exit 0` and `exit 2`. Add to `test_implemented_protections_are_not_planned` (or a one-line new test) that `docs/site/adapters.md` does not contain `including control planes` and does contain `[control_plane]`. Fails today.
- [X] T021 [US5] Edit `docs/site/remote.md` sections 2, 3 and 5, `docs/site/configuration.md:299-300` and `docs/site/adapters.md` (line 25 sentence, config check paragraph, `chat.slack` and `inbound.slack` rows) as plan.md describes. No em-dashes, no real Slack ids (the docs test allows only `T0123ABC`, `U0123ABC`, `D0123ABC`). T020 passes.

## Phase 8: Polish

- [X] T022 Run `python -m pytest -q` from the repository root; everything passes.
- [X] T023 Check every changed file for em-dashes, emojis and absolute local paths and remove any.

## Dependencies

- T001 first. Within each story the test task precedes its implementation task.
- T007 before T008 (T008 relies on the keyword), T011 and T013 use `OWNER_UNSET` from T007.
- T018 depends on T003, T005, T009, T013, T015 and T017.
- T020 and T021 can run after T017 (the docs test reads `env.CREDENTIALS`).
