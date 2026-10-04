# Tasks: A background hand-back is read from the transcript, no seat is left running, traces redact only secrets, failed spans record a gap

Test first: run each test task, see it fail for the stated reason, then do the
implementation task that follows it. Run tests with `python -m pytest -q` from the
repository root using the interpreter the task names. Design details are in plan.md.

## Fixtures

- [X] T001 Add `tests/payloads/SubagentStop/handback.json` (`example.json` without
  `last_assistant_message`) and `tests/payloads/SubagentStop/handback-transcript.jsonl`
  (the recorded assistant SubagentHandback row with `input.message` ending in `Blocked:
  none`, `Gap: none`, `Change: none`, then the user tool result row with `toolEndsTurn:
  true`; neutral ids). One line each in `tests/payloads/README.md`. No test yet.

## The shared helper (US1, US2)

- [X] T002 Create `tests/test_handback.py` with `test_last_turn_shapes`: over files in
  `tmp_path`, `brief.last_turn` returns the hand-back's `input.message` with `handback`
  True for the fixture transcript; the joined text blocks with `handback` False for a text
  row; a string content as is; `completion == [index, sha256(line)]` of the assistant row;
  raises `ValueError` for a torn last line, for a transcript with no assistant row and for a
  row with no `message`; raises `OSError` for a missing file. Add `test_stop_text`: a
  non-blank message wins; a blank or absent one reads the transcript; a missing
  `agent_transcript_path` raises `ValueError`. Fails today: `last_turn` and `stop_text` do
  not exist.
- [X] T003 Add `HANDBACK`, `last_turn` and `stop_text` to `cli/wuwei/brief.py` (plan.md
  section 1). T002 passes.

## The builder records a hand-back (US1)

- [X] T004 In `tests/test_handback.py` import the `seat` fixture and `launch` from
  `tests/test_build_next.py`; add `test_builder_handback_records_result`: launch, append
  the fixture rows to `agent.jsonl`, call `agent_launch.stop` without
  `last_assistant_message`. Assert `(0, '')`, seat `stopped`, build `check` with
  `result['text']` equal to the hand-back message, and the event kinds after
  `seat launched` equal to those of the plain-text `stop()` helper run in a second `seat`
  fixture (`seat.usage`, `seat stopped`). Add `test_mismatched_message_still_refused`: a
  message that differs from the transcript's last turn still fails as today. Fails today
  with `SubagentStop omitted builder result`.
- [X] T005 Replace lines 283 to 295 of `build.stopped` in `cli/wuwei/commands/build.py`
  with the `last_turn` binding (plan.md section 4). T004 passes; `tests/test_build_next.py`
  and `tests/test_build.py` stay green.

## No seat left running (US2)

- [X] T006 In `tests/test_handback.py` add `test_unreadable_transcript_stops_unmeasured`:
  launch, then `agent_launch.stop` with no message and an `agent_transcript_path` whose
  brief reference reads but whose last line is torn (the seat binds, the report does not
  read). Assert exit 2 with `seat builder stopped unmeasured:` and `wuwei seat stop` in the
  reason; seat `status == 'unmeasured'` with a `reason`; one `seat stopped` event with
  `status: 'unmeasured'` and the reason; `next.step(root)` is not the `wait` row naming the
  seat; `main(['status', '--line'])` exits 0. Add `test_sentinel_unreadable_report`: the
  same for a sentinel seat (non-builder branch). Add `test_stop_seat_reason` for
  `state.stop_seat(..., reason=..., by='owner')` (status, fields, event payload) and that a
  later plain stop clears them. Fails today: the builder stays `running`; the sentinel
  stops as `stopped`; `stop_seat` takes no `reason`.
- [X] T007 Extend `state.stop_seat` in `cli/wuwei/state.py`, let `brief.seats` accept
  `'unmeasured'` in `cli/wuwei/brief.py`, add the `stop_text` check and the unmeasured
  `except` branch to `agent_launch.stop` in `cli/wuwei/guards/agent_launch.py`, and pop a
  stale `reason` in `build.record_result` (plan.md sections 3 and 4). T006 passes.

## The hook fills the message once (US1)

- [X] T008 In `tests/test_handback.py` add `test_hook_fills_message_for_every_guard`:
  through `wuwei.__main__.main(['hook', 'SubagentStop'])` with stdin from
  `handback.json` (cwd, agent type `wuwei:builder`, agent id and transcript set to the
  launched seat), assert exit 0, a `retro.captured` event whose fields come from the
  hand-back, no `decision question:` or `retro capture:` error, and the seat `stopped`.
  Add `test_hook_reads_nothing_for_other_agents`: an `Explore` payload without a message
  and a transcript path that does not exist exits 0 and `wuwei.brief` is not imported
  (subprocess as in `tests/test_hooks.py` `test_subagent_stop_skips_watch_and_memory`).
  Fails today: retro
  capture and the decision guard exit 2 with `missing or invalid last_assistant_message`.
- [X] T009 Add `fill_stop_text` to `cli/wuwei/commands/hook.py` and call it from `run` for
  SubagentStop inside a workspace (plan.md section 2). T008 passes;
  `tests/test_hooks.py` stays green.

## The background day end to end (US1, SC-001)

- [X] T010 Add the `handback` flag to `Runtime` in `tests/fakes/day.py` (plan.md
  Fixtures) and `test_background_handback_day` to `tests/test_e2e_day.py`: plan, approve,
  `plan session planner`, `build('builder-initial')` and the three initial gates with
  `day.runtime.handback = True`, in one `Day`, and the same with the flag off in a second
  `Day` (separate `tmp_path` subdirectories). Assert equal seat statuses, equal
  `builds['A']['result']['text']`, and equal sequences of `(kind, payload['name'])` for
  `seat launched`, `seat stopped`, `seat.usage` and `retro.captured`. Passes after T009;
  run it with T009 reverted locally to see it fail with the builder still `running`.

## Stuck seats (US3)

- [X] T011 In `tests/test_traces.py` add `test_bind_records_seat_transcript`: a subagent
  PostToolUse whose agent transcript carries the seat's brief reference sets
  `seats[name]['transcript']` to that path. Fails today: no `transcript` key.
- [X] T012 Set `seat['transcript']` in `bind` in `cli/wuwei/guards/traces.py` (plan.md
  section 5). T011 passes.
- [X] T013 In `tests/test_handback.py` add `test_stuck`: `brief.stuck` lists a running seat
  whose `transcript` ends in the hand-back and a seat `unmeasured` without `by`; not a
  running seat whose transcript ends in text, not one with no `transcript`, not one whose
  transcript is missing or torn, not one `unmeasured` with `by: owner`, not a `stopped`
  one. Add `test_next_names_stuck_seat` (`next.step` returns state `stuck` with command
  `wuwei seat stop <name> --verdict <file>` while the item is in `implement`) and
  `test_heartbeat_seats_probe` (`heartbeat._seats` is `failed` with `dead:` and the command,
  `ok` when none). In `tests/test_heartbeat.py` add `test_seats_probe` over the `ws`
  fixture (a stuck seat fails the probe and `measure` lists `seats` last, as `PROBES`
  orders it); in `tests/test_doctor.py` assert the `stuck seats` row (`fail` with the
  command, `ok` with none). Fails today: `stuck`, `_seats` and the rows do not exist.
- [X] T014 Add `stuck` to `cli/wuwei/brief.py`, the `seats` probe to
  `cli/wuwei/heartbeat.py`, the `stuck` row to `cli/wuwei/commands/next.py` and the
  `stuck seats` row to `cli/wuwei/commands/doctor.py` (plan.md sections 1 and 8). T013
  passes.

## The recovery command (US3)

- [X] T015 In `tests/test_handback.py` add, over the `seat` fixture with a stuck builder:
  `test_seat_stop_verdict_builder` (`main(['seat', 'stop', 'builder', '--verdict',
  report])` exits 0, build `check` with the file text as result, seat `stopped`, events as
  a hook stop); `test_seat_stop_verdict_after_unmeasured` (the same from a hook-unmeasured
  seat); `test_seat_stop_verdict_sentinel_lint` (a sentinel seat and a verdict file without
  `Verdict:` exits 1 with the lint finding, seat unchanged);
  `test_seat_stop_unmeasured_parks_builder` (exit 0, seat `unmeasured` with `by: owner`,
  build `parked` with the reason, `brief.stuck` empty); `test_seat_stop_refusals` (a
  `stopped` seat and an unknown name exit 1; an empty and a two-line reason exit 2; under
  `guarded` with `WUWEI_SESSION_ID` set to a non-planner id exit 1; under `strict` with
  `integrity._host_confirm` raising `OSError(HOST_TERMINAL)` exit 2 and declining exit 1; in
  every refusal state is unchanged); `test_seat_stop_planner_session_allowed` (guarded,
  `WUWEI_SESSION_ID` equal to `planner_session_id`, exit 0). Fails today: no `seat` command.
- [X] T016 Create `cli/wuwei/commands/seat.py`, add `'seat stop'` to `WRITES` in
  `cli/wuwei/commands/__init__.py` and `seat` to the `Recovery` group in
  `cli/wuwei/__main__.py` (plan.md section 9). T015 passes;
  `tests/test_cli_known_command.py` and `tests/test_cli.py` stay green.

## Redaction (US4)

- [X] T017 In `tests/test_traces.py` add `test_redaction_corpus`: twenty ordinary commands
  (the `gh` set with `--json` field lists, `gh issue view`, `gh api`, `gh pr checks`,
  `gh auth status`, `gh run list --limit 5`, `gh pr merge 12 --squash --auto`; `git status
  --short`, `git log --oneline -5`, `git diff --stat main...HEAD`, `git push origin
  <branch>`, `git branch -d old-branch`, `git rev-parse HEAD`; two `pytest` forms including
  `-k "text and redact"`; two `curl` calls without tokens; `ls -la .wuwei/days/<date>`)
  equal `redact(command)`; ten secret shapes (Bearer header, `ghp_` assignment, URL with
  user and password, `AKIA` key, `sk-` key, Slack webhook, `--token` flag, `xoxb-`, `glpat-`,
  a JWT) lose their secret text. Add `test_body_keeps_command_words`:
  `redact('gh pr comment 12 --body "looks good"')` starts with `gh pr comment 12 --body
  [BODY `. In `test_review_redaction_cases` keep exact `'[REDACTED]'` for key-redacted
  values and assert `'private' not in actual[key]` and `actual[key].endswith('[REDACTED]')`
  for the two `command` entries. Fails today: the `--json` and `git branch -d` commands
  become `[REDACTED]`, and the body loses its command words.
- [X] T018 Change `SECRET`, the body substitution and the final match branch of `redact`
  in `cli/wuwei/redact.py` (plan.md section 7). T017 passes, and so do
  `test_redacts_messages_and_credential_flags_in_strings`, `test_review_command_bodies`,
  `test_truncated_command_body_stays_private` and `tests/test_env_credentials.py`.

## Gap events (US5)

- [X] T019 In `tests/test_traces.py` change the `hook.post_tool_use_error` assertions in
  `test_post_tool_failures_report_without_refusing`, `test_error_logging_uses_payload_workspace`
  and `test_recorder_owns_failures` to `traces.gap`, and assert the payload has `reason`,
  `span` (the tool name) and `session`. In `tests/test_steward.py` line 164 and
  `tests/test_signal_status.py` (tier map) rename the kind. Add
  `test_trace_gap_on_status_line_and_doctor`: with `state.append_jsonl` raising, run the
  PostToolUse hook through `run_hook`; exit 0, one `traces.gap`, `status --line` contains
  `traces: 1 gaps`, and the doctor `_day` rows include `traces` with `warn` and `1 gaps
  today`. Add a `traces.gap` refusal check for `wuwei event traces.gap` (reserved kind).
  Fails today: the kind is `hook.post_tool_use_error`, no status part, no doctor row, the
  kind is not reserved.
- [X] T020 Record `traces.gap` in `check` in `cli/wuwei/guards/traces.py`, add the
  producers in `cli/wuwei/commands/event.py`, the count in `snapshot` and `line` in
  `cli/wuwei/commands/status.py`, and the `traces` row in `cli/wuwei/commands/doctor.py`
  (plan.md sections 6 and 8). T019 passes.

## Docs

- [X] T021 Update `docs/site/reference.md` (plan.md section 10). Tests that pin the docs
  (command table, help groups) stay green.

## Review fixes

- [X] T023 A missing transcript binds the stop through the seat's recorded `transcript` and
  stops it unmeasured (`stopping_seat` in `cli/wuwei/guards/agent_launch.py`); a blank
  transcript report raises in `brief.stop_text`; `-d`/`--json` with a value holding `=`,
  `&` or `:` stays a body in `cli/wuwei/redact.py`. Tests first in `tests/test_handback.py`
  and `tests/test_traces.py`.

## Verification

- [X] T022 Run the full suite with `python -m pytest -q` from the repository root. Check
  every file written for em-dashes and emojis. Confirm no file of #469 to #472 and no
  `guards/lifecycle.py` change in `git status`.
