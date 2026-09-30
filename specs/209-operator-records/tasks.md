# Tasks: Records the operator reads are correct

Test first throughout: write the test, run `python -m pytest -q <file>` and see it fail for the stated reason, then write the code.

## Reply drafts reach the owner queue (US1, FR-001, FR-002)

- [X] T001 In `tests/test_pr_actions.py`, add a failing test: one unanswered thread `T17` (root comment id 3), draft tier, `main(['pr', 'act', REF, '--reply', text]) == 1`, the printed action has a `draft` id, and `main(['drafts'])` lists exactly one pending row with `channel == 'code_host'`, `operation == 'comment'`, `destination == REF`, `inputs == {'ref': REF, 'text': text, 'thread': 3}` and `item == 'A'`. Switch the existing assertions at lines 86, 157 and 169 from `pr_reply_drafts` to `drafts.read(state.read_state(root))` (no pending drafts; one pending draft on the unmeasured tier; still one after the repeat). Fails because `wuwei drafts` prints `[]`.
- [X] T002 In `cli/wuwei/pr_actions.py` `_thread`, replace the `pr_reply_drafts` write with the duplicate check plus `drafts.create(...)` described in plan section 1.

## Briefs never create items (US2, FR-003)

- [X] T003 In `tests/test_brief.py`, add a failing test: with items `{'X'}`, `brief lead DISCOVERY lead-1` and `brief.write('steward', 'day', ...)` both exit 0 and write their files, and `state.read_state(root)['items']` keys stay `{'X'}`. Existing `X` track and worktree tests stay green. Fails because `DISCOVERY` is created.
- [X] T004 In `cli/wuwei/brief.py` `write`, record track and worktree only when `item in fresh['items']` (plan section 2).

## Report lists merged items (FR-004, FR-010)

- [X] T005 In `tests/test_report_retro.py`, add a failing test: items `A` merged with `pr` `org/repo#1` and `B` in `delta`; the report has `## Merged` with `- A (org/repo#1)`, `B` under Open at close and Carry, and `A` in neither.
- [X] T006 In `cli/wuwei/report.py`, extract `decisions(day, data)` from `build` and add the `## Merged` section (plan section 3). `tests/test_decision.py` and `tests/test_outcome_metrics.py` report assertions must stay green.

## Status line counts real phases (US3.1, FR-005)

- [X] T007 In `tests/test_signal_status.py`, add a failing test: cap 2, items in `delta` and `merged`; `status --line` contains `delta 1/2` and `merged 1/2`, and `status --json` `phases` equals `{'delta': 1, 'merged': 1}`. Keep `test_status_line_and_json_share_snapshot` green.
- [X] T008 In `cli/wuwei/commands/status.py` `snapshot`, count every phase in `state.PHASES` order and keep nonzero ones (plan section 4).

## Routine events are not nudges (US3.2, US3.3, FR-006)

- [X] T009 In `tests/test_signal_status.py`, add failing assertions: `plan.approved`, `state.import`, `build.started`, `build.launched`, `build.checked`, `verdict.rejected` classify `silent`; `tracker.call` with `{'exit': 2, 'reason': 'tracker adapter is none'}` is `silent`, with `{'exit': 2, 'reason': 'tracker call unmeasured: OSError'}` is `nudge`. Change the tier table entry `'verdict.rejected'` to `'silent'`.
- [X] T010 In `cli/wuwei/signal.py`, extend `SILENT` and the `tracker.call` rule (plan section 5).

## Nudges clear with their cause (US3.4, US3.5, FR-007, FR-008)

- [X] T011 In `tests/test_pr_ownership.py`, add a failing test: after `wuwei pr state` observes a merged PR, the last `pr.action` event payload has `state == 'merged'`.
- [X] T012 In `cli/wuwei/pr_actions.py` `observe`, add `'state': current` to the event payload (plan section 1).
- [X] T013 In `tests/test_quiet_sweeps.py`, add failing tests next to `test_nudges_clear_pr_action_and_mcp_finding`: (a) `draft.created` for ids `d1` and `d2` gives two nudges; `draft.sent` for `d1` and `draft.dropped` for `d2` leave `attention(day) == []`; a `draft.failed` for a third created id leaves exactly one nudge sourced `draft.failed`. (b) two `merge.policy_blocked` events for `x/y#1` give one nudge; a `pr.action` event `{'pr': 'x/y#1', 'tier': 'silent', 'state': 'merged'}` clears it; a `pr.action` with state `approved` does not.
- [X] T014 In `cli/wuwei/commands/status.py` `attention`, add the two clearing rules and the two key rules (plan section 4).

## Pack reads items, decisions and PRs (US4, FR-009)

- [X] T015 In `tests/test_brief_pack.py`, rebuild the `root` fixture from state (an item parked for the risk, a merged item with a PR, decision record `D-1` with `Outcome: Delay release`) instead of `note` and `decision.decided` events, keeping the intent of the answer, streak, metric and escape tests (answers name a word of the parked item's risk line; escape now uses a decision outcome containing `<script>`). Add a failing test with its own state (DIVIDE-1 merged with PR `org/repo#1`, D-1 `Outcome: defer`, nothing parked): with events carrying `reason: 'tracker adapter is none'` and a `hook.refusal` reason, the pack has Headline and Changed naming `DIVIDE-1: merged (org/repo#1)`, Decided `D-1: defer`, At risk `No recorded risks`, and neither message appears. Add one for At risk listing a pending decision and an owned PR with an open action episode.
- [X] T016 In `cli/wuwei/brief_pack.py`, rewrite `_evidence` on top of `state.read_state` and `report.decisions` and drop the `watch` import (plan section 6).

## Steward queue only lintable candidates (US5, FR-011)

- [X] T017 In `tests/test_intraday_intake.py`, add a failing test: discovery returns `org/repo#1:thread:PRRT_1` and `PARTIAL`; after `discovery.intake`, `intraday_proposals` has only `PARTIAL`, no `plan.proposed` event names the unsafe id, and `steward.decision_queue(root)` ids are `['PARTIAL']`.
- [X] T018 In `cli/wuwei/discovery.py` `intake`, skip ids failing `steward.SAFE_ID` (plan section 7).

## Issue acceptance (end to end)

- [X] T019 Create `tests/test_operator_records.py` with the issue acceptance day, in-process through `main`: propose and approve DIVIDE-1, write a lead brief for `DISCOVERY` and a steward brief, transition DIVIDE-1 `implement`, `gate`, `raised`, `merged` and set its `pr` (with `state._write_state(..., reserved=False)` as other tests do), write `D-1` with `Outcome: defer`, append `build.started`, `build.checked`, `verdict.rejected`, `tracker.call` (tracker none), `draft.created` then `draft.sent`, `merge.policy_blocked`, then `pr.action` with state `merged`. Assert: report has `- DIVIDE-1` under Merged, `- D-1: defer`, Open at close and Carry `none`, no `DISCOVERY`; `status --line` has `pages 0 | nudges 0` and `merged 1/`; the pack headline names `DIVIDE-1: merged` and Decided names `D-1: defer`; `nudges` prints `[]`. Run it after T002 to T018; it must pass without further code. If it fails, fix the owning function, not the test.

## Docs and verification

- [X] T020 Update the pack and nudges paragraphs in `docs/site/configuration.md` (plan section 8).
- [X] T021 Run `python -m pytest -q` from the repository root; all pass. Scan changed files for em-dashes, emojis and absolute local paths.
