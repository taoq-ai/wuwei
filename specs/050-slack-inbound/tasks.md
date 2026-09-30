# Tasks: Slack inbound by polling mentions and DMs

Test first: every implementation task follows the test task that must fail before it.
Run tests with `python -m pytest -q <file>` from the repository root.

## Setup

- [X] T001 Probe read-only on main: `[adapters] inbound = "slack"` makes `config check`
  exit 1 and `listen --once` exit 2 with `unknown adapter 'slack'` (spec, Root cause).
- [X] T002 Write spec.md, plan.md and tasks.md.
- [X] T003 Run the full suite and confirm it is green before any change.

## Shared page loop (FR-004, FR-005)

- [X] T004 Test: in `tests/test_reference_adapters.py` add `test_slack_sent_replay`:
  one replayed `conversations.history` page with an owner row, a bot row and another
  user's row; `slack.sent('C1', ['U0OWNER'])` returns only the owner row (pins `sent`'s behaviour;
  on main it fails too, because `sent` binds `urlopen` at import and `replay` cannot
  intercept it); then a replayed `HTTPError` 429 with
  `Retry-After: 30` returns exit 2 with `rate limited` and `30` in the reason. Run and see
  the 429 half fail (`HTTPError` today).
- [X] T005 Implement `history(channel, **params)` in `adapters/chat/slack.py` per plan
  section 1 (call-time `urllib.request.urlopen`, 429 to `Failure` with the `ponytail:`
  comment) and make `sent` loop over `history(channel)` with its row checks unchanged.
  T004 passes; `tests/test_voice.py` still passes.

## US1: mentions and DMs reach the inbox once

- [X] T006 Test: add `slack_history` (two bodies, plan Test plan) to
  `tests/fixtures/reference_adapters/recordings.json`; in
  `tests/test_reference_adapters.py` add the `slack_case` fixture and
  `test_slack_inbound_two_mentions_once` (issue acceptance through `listen.tick`),
  `test_slack_inbound_events` and `test_slack_inbound_dm_only`.

## US2: cursor, order and rate limits fail closed

- [X] T007 Test: in `tests/test_reference_adapters.py` add the parametrised
  `test_slack_inbound_fails_closed` (429, `ok: false`, row without `user`, bad `ts`,
  bad cursor, ten full pages, work channels without an owner Slack id) and
  `test_slack_inbound_missing_credentials_never_calls_network`.
- [X] T008 Run T006 and T007 and see every test fail with `unknown adapter 'slack'` or
  `No module named 'adapters.inbound.slack'`.
- [X] T009 Implement `adapters/inbound/slack.py` per plan section 2 (`poll`, `LOOKBACK`
  with its `ponytail:` comment, `TS`; check order cursor, config, owner id, DM channel,
  then `history`). T006 and T007 pass; `tests/test_adapters.py`
  (`test_module_contracts`) and `tests/test_listen.py` pass unedited.

## US3: `config check` names the credentials

- [X] T010 Test: in `tests/test_env_credentials.py` add
  `('inbound="slack"', '', ('SLACK_BOT_TOKEN', 'SLACK_USER_TOKEN', 'SLACK_OWNER_DM_CHANNEL'))`
  to the `test_config_reports_missing_and_set` table. Run and see it fail (exit 0,
  `no credential variables required`).
- [X] T011 Implement the `('inbound', 'slack')` row in `requirements` in
  `cli/wuwei/commands/config.py`. T010 passes.

## Docs and finish

- [X] T012 Update `docs/site/adapters.md` (port row, credentials row) and
  `docs/site/configuration.md` (`adapters.inbound` row, one paragraph in "Running the
  listener") per plan section 4. `python -m pytest -q tests/test_docs.py` passes.
- [X] T013 Run the full suite: `python -m pytest -q`. Check every file written for
  em-dashes, emojis and absolute local paths; remove any.

## Review fixes

- [X] T014 Test (F1): `test_slack_inbound_quiet_week_moves_the_cursor` in
  `tests/test_reference_adapters.py` (an empty poll a week later moves the cursor to the
  poll start and the next `oldest` is that minus 300) and updated cursor expectations in
  `tests/test_listen.py`; they fail before the fix.
- [X] T015 Fix (F1): `listen.tick` saves the cursor on every successful poll as the newer
  of the last event's `ts` and the poll start epoch; `ponytail:` note on the ten-page
  ceiling in `chat.slack.history`; spec and configuration docs updated.
