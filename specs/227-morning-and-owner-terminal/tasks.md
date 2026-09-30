# Tasks: The morning before the first plan, owner actions on a terminal, and operator records

Test first throughout: write the test, run `python -m pytest -q <file>` and see it fail for the stated reason, then write the code. Plan sections are in [plan.md](plan.md).

## Status line before the plan (US1.1, US1.4, FR-001)

- [X] T001 In `tests/test_signal_status.py`, change `test_unreadable_state_fails_closed` to cover only `'{broken'` plus a new case: `state.json` absent while `state.snapshot.json` exists; both exit 2 with stdout `WUWEI ? unmeasured\n`. Add a failing test: a day directory with no `state.json` (and one with state `{'cap': 1, 'items': {}}`, gate not approved) gives `status --line` exit 0 with stdout starting `WUWEI no plan yet | pages 0 | nudges 0`, and `status --json` exit 0 with `gate_approved` false; a state with `gate_approved: true` has no `no plan yet`. Fails because the absent state exits 2.
- [X] T002 In `cli/wuwei/commands/status.py`, delete the two `FileNotFoundError` guards in `scan` and `snapshot`, add `gate_approved` to the snapshot, and prefix the line with `WUWEI no plan yet |` while the gate is not approved (plan section 1).

## Obligations sweep before the first PR (US1.2, US1.3, US1.5, FR-002)

- [X] T003 In `tests/test_obligations.py`, add failing tests using the `case` fixture moved to the next day (`WUWEI_NOW` one day later, no day files): (a) `sweep()` returns 0 and the last `watch: sweep` event has `unreadable == 0` and `owed == 0`; (b) after `state._write_state(lambda d: None, root, kind='plan.session', payload={'session_id': 's'}, reserved=False)` it still returns 0; (c) with `state.json` written directly by `workspace.atomic_write` (defaults, no PRs) and `events.jsonl` holding only a `note` event carrying `{'prs_seen': False}`, it returns 2; (d) with `state.json` absent and `state.snapshot.json` present it returns 2. Existing `test_day_and_closed_pr`, `test_empty_pr_set_cannot_erase_today_history` and `test_empty_pr_set_requires_readable_history` stay green. Fails because (a) prints `day state missing` and (b) prints `no recorded PR state for today`.
- [X] T004 In `cli/wuwei/obligations.py`, remove the `day state missing` guard in `evaluate` and change `_check_empty_day` as in plan section 2 (proof from any non-`note` kind; no proof needed and no events file needed before the first state write).

## No bare `watch: sweep` nudge (US1.3, FR-003)

- [X] T005 In `tests/test_quiet_sweeps.py`, add a failing test next to `test_three_sweep_obligations_make_three_nudges`: a `watch: sweep` event with only `reply_owed: 0, visibility_owed: 0, unreadable: 1, integrity_owed: 0, owed: 1, exit: 2` gives one attention row whose `reason` is `unmeasured` and `source` is `watch: sweep:unmeasured`; the same event with `unreadable: 0, owed: 0, exit: 0` gives `[]`; a payload with `unreadable: 'x'` still gives one row sourced `watch: sweep`. Fails because the row reason is `watch: sweep`.
- [X] T006 In `cli/wuwei/commands/status.py` `scan`, default absent sweep counts to 0 (plan section 1).

## Fresh-day acceptance through the CLI (US1 acceptance)

- [X] T007 In `tests/test_watch.py`, add a test with the `case` fixture moved one day ahead and `steward.run` stubbed (as at line 805): `main(['status', '--line']) == 0` with `no plan yet` in stdout; `main(['sweep', 'watch']) == 0`; `main(['sweep', 'obligations']) == 0`; both `watch: sweep` events have `unreadable == 0` and `owed == 0`; `main(['nudges']) == 0` prints `[]`. Run it after T002, T004 and T006; it must pass without further code. If it fails, fix the shared function it names, never the test's expectations.

## Owner terminal sentence (US2, FR-004)

- [X] T008 In `tests/test_integrity.py`, add a failing table test: with `builtins.open` patched so `'/dev/tty'` raises `OSError(6, 'Device not configured')`, `_host_confirm('a' * 64)` raises `OSError` whose `str` is exactly `this is an owner action: run it in a host terminal`; with `'/dev/tty'` opening a regular temp file (not a tty) it raises the same. `test_host_confirmation_uses_a_nonseekable_terminal` stays green. Add: `reconfirm` without `confirm` on a changed install with `/dev/tty` unavailable returns exit 2 whose reason contains `run it in a host terminal` and no `Errno`.
- [X] T009 In `tests/test_decision.py`, add a failing test on the routed-decision fixture used by the owner outcome tests near line 573, without patching `_host_confirm` but with `/dev/tty` unavailable: `main(['decision', 'outcome', 'D-3', 'A']) == 2`, stderr is one line `wuwei decision: this is an owner action: run it in a host terminal`, and the record's `Outcome:` and `decision_outcomes` are unchanged.
- [X] T010 In `tests/test_state.py`, add a failing case to `test_recover_command_exits` (or a sibling test): no `_host_confirm` patch, `/dev/tty` unavailable, `main(['state', 'recover']) == 2` with stderr containing `run it in a host terminal` and no `Errno`, and `state.json` still corrupt.
- [X] T011 In `cli/wuwei/integrity.py`, add `HOST_TERMINAL` and make `_host_confirm` raise it for a missing or non-tty `/dev/tty` (plan section 3). No caller changes.

## Report metrics as JSON (US3.1, FR-005)

- [X] T012 In `tests/test_report_retro.py`, add a failing test: after a day with state and one `verdict.rejected` event, the line after `## Process metrics` in `main(['report'])` output parses with `json.loads` and equals `json.loads` of `main(['metrics'])` output. Fails because the line is a Python dict repr.
- [X] T013 In `cli/wuwei/report.py`, serialise the metrics with `json.dumps(..., sort_keys=True, allow_nan=False)` (plan section 4).

## Build check prints the failing output (US3.2, FR-006)

- [X] T014 In `tests/test_build_next.py`, extend `test_claude_launch_check_continue_done_idempotent` (or add a sibling on the `seat` fixture): the failing check result `{'test_ids': ['test_one'], 'error': 'failure'}` makes `main(['build', 'check', 'A']) == 1` and stderr contains `failure` and `test_one`. Fails because nothing is printed.
- [X] T015 In `cli/wuwei/commands/build.py` `run`, print the `continue` action's feedback to stderr on exit 1 (plan section 5).

## One rejection per verdict file version (US3.3, FR-007)

- [X] T016 In `tests/test_metrics.py`, add a failing test: write one bad quality verdict file under today's `decisions/`, call `verdict.lint_file(path, role='sentinel-quality')` three times (the lint command, the SubagentStop hook and dispatch receive all route through it), then `metrics.collect(root)['verdict_lint_rejections'] == 1`; rewrite the file with different bad content and lint once more, then it is 2; each `verdict.rejected` event carries a 64-hex `sha256`, and a missing file's event carries `sha256` null. Fails because the first count is 3.
- [X] T017 In `cli/wuwei/verdict.py` `record_rejection`, add the content `sha256`; in `cli/wuwei/metrics.py` `collect`, count distinct `(file, sha256)` pairs (plan section 6).

## Recovery nudge text (US3.4, FR-008)

- [X] T018 In `tests/test_state.py`, add a failing test: `corrupt(workspace)`, `state.recover(confirm=lambda token: True)`, then the last event payload has `reason == 'state recovered from snapshot ' + digest[:12]` and an `error` containing `state.json`, and `attention(day)` (from `wuwei.commands.status`) has one `state.recovered` row whose `reason` does not contain `Unterminated` or `recover in a host terminal`. Fails because the reason is the old error.
- [X] T019 In `cli/wuwei/state.py` `recover`, change the `state.recovered` payload (plan section 7).

## Answered threads are not candidates (US3.5, FR-009)

- [X] T020 In `tests/test_obligations.py`, add a failing unit test for `obligations.answered(thread, me)`: latest human comment by `me` (with a later bot comment) is True; latest human comment by another author is False; no comments is False. Existing `test_absolute_reply_table` thread rows stay green.
- [X] T021 In `cli/wuwei/obligations.py`, extract `answered` from `_replies` and call it there (plan section 2).
- [X] T022 In `tests/test_goals_rank.py`, add a failing test next to the review-bot discovery test near line 160: config with `[owner]\nhandles=["owner"]`, code-host port returning two unresolved threads, `t1` whose latest human comment is by `owner` and `t2` whose latest is by `reviewer`; `discover(...)` candidates contain `x/y#1:thread:t2` and not `...:t1`, and `sources['follow_up_threads'] == 'measured: 1'`. The existing test (no owner handles, thread without comments) stays green. Fails because both threads are candidates.
- [X] T023 In `cli/wuwei/discovery.py` `discover`, skip answered threads (plan section 8).

## SessionStart without draft bodies (US3.6, FR-010)

- [X] T024 In `tests/test_watch.py`, next to `test_session_payload_omits_watch_state`, add a failing test: create one draft through `drafts.create` (or write a valid `drafts` state row the way `tests/test_drafts.py` `queued` does), then `memory.session_payload(root)` content contains the draft id and its destination and does not contain the draft text or the key `inputs`. Fails because the full record is dumped.
- [X] T025 In `cli/wuwei/memory.py` `session_payload`, replace `drafts` with id to destination (plan section 9).

## Rank accepts a lead JSON (US4.1 to US4.3, FR-011)

- [X] T026 In `tests/test_templates_errors.py`, extend `test_plan_template_can_be_proposed_from_stdin`: after `plan propose -`, `cli(workspace, 'rank', '.wuwei/days/2026-09-29/proposal.json')` exits 0 and its stdout parses as a list with one candidate; and add `cli(workspace, 'rank', '-', input=<plan template stdout>)` exits 0; `cli(workspace, 'rank', '-', input='{}')` exits 2 with `candidates must be a list`. Fails because the object input exits 2.
- [X] T027 In `cli/wuwei/commands/rank.py` `run`, rank `candidates` of a JSON object (plan section 10).

## Docs and skill (US2.5, US4.4, FR-012)

- [X] T028 In `tests/test_docs.py`, add a failing test: `reference.md` and `concepts.md` each contain `Host terminal actions` and every one of `decision outcome`, `state recover`, `integrity reconfirm`, `mcp decide`, `drafts approve`, `watch uninstall`; `reference.md` contains `run it in a host terminal`, `no plan yet`, `proposal.json`, and `pr raise` with `--base`, `--title`, `--body-file` and `--item`; `skills/wuwei-plan/SKILL.md` contains `wuwei rank .wuwei/days/`.
- [X] T029 Edit `docs/site/reference.md`, `docs/site/concepts.md` and `skills/wuwei-plan/SKILL.md` as in plan section 11.

## Finish

- [X] T030 Run `python -m pytest -q` from the repository root with the task's interpreter; everything passes. Check every file you wrote for em-dashes, emojis and absolute local paths and remove any.
