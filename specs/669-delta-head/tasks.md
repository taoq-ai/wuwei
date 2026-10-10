# Tasks: the delta round refreshes the reviewer's recorded head

**Input**: `specs/669-delta-head/spec.md`, `specs/669-delta-head/plan.md`

**Tests**: required (constitution IV). Each behaviour's test task comes before its
implementation task; run the test and see it fail for the expected reason before the code.
Run tests with `python -m pytest -q` from the repository root.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: User Story 1 - the same reviewer re-reviews the fix (P1)

### Tests first

- [X] T001 [US1] In `tests/test_dispatch.py`, add a module helper `live_head(monkeypatch,
  sha)` that patches `wuwei.registry.load` to return, for `kind == 'vcs'` only, an object
  whose `head(tree, *, root)` returns `Result(0, {'sha': sha})`, and delegates every other
  kind to the real `registry.load` (plan, Test notes).
  Add `test_issue_acceptance_delta_dispatch_records_and_names_the_delta_head`:
  `tree = built(root)`, `gate_fix(root)`, set the `quality-1` seat
  `agent_id='agent-quality-1', head=OLD` (`OLD = 'abc1234' + '0' * 33`),
  `dispatch.next_step` (opens the fix, no fake yet, as today), then the fix round commits:
  `live_head(monkeypatch, NEW)` with `NEW = 'def5678' + '0' * 33`,
  `state.transition('A', 'delta', root)`, then `dispatch.next_step`. Assert: the seat's
  `delta_head == NEW` and its `head` is still `OLD`; the one `continue` action's
  `feedback` contains `NEW` and still starts `Delta review:`; today's events hold exactly
  one `gate.delta_head` event with payload `{'item': 'A', 'seat': 'quality-1', 'head':
  NEW}`. Call `dispatch.next_step` again; still exactly one such event (spec FR-001,
  scenario 1). Run it; it fails (no `delta_head`, and the seats read nothing).
- [X] T002 [US1] In `tests/test_dispatch.py`, add
  `test_issue_acceptance_in_session_reviewer_delta_verdict_is_received_on_the_delta_head`:
  the same setup as T001 through the delta `dispatch.next_step` (factor the shared setup
  into one local helper only if both tests use it verbatim), then rewrite
  `briefs/quality-1.md` to `f'HEAD: {OLD}\nWorktree: {tree}\n'` so the live check runs. The
  seat is not relaunched (its `head` stays `OLD`). Write `decisions/gate-quality-1.md` as
  the delta `PASS` verdict (`PASS + 'Simplicity: none\nDesign: none\n'`) with
  `Head: abc1234`; `receive('A', 'quality', 'quality-1', 'delta', root)` raises
  `dispatch.Refused` whose message contains both `abc1234` and `NEW`, and
  `'A:quality:delta'` is not in `gate_verdicts`. Rewrite the verdict with `Head: def5678`;
  `receive` returns a record with `head == 'def5678'` and `round == 'delta'` (spec
  scenarios 2 and 3, SC-001, SC-002). Run it; it fails (today the new head is refused as
  "differs from dispatched brief").
- [X] T003 [P] [US1] In `tests/test_dispatch.py`,
  `test_continued_sentinel_delta_head_matches_seat_head` (the relaunch path: seat `head`
  rewritten to the new head, no `delta_head`): change the expected refusal match from
  `verdict HEAD differs from dispatched brief` to `is not the delta head` and assert the
  message names both `9999999` and `def5678`. Keep its accepting half unchanged. Run it; it
  fails on the message.
- [X] T004 [P] [US1] In `tests/test_dispatch.py`, add
  `test_delta_head_event_is_reserved_and_silent`: `'gate.delta_head'` is a key of
  `wuwei.commands.event.EVENT_PRODUCERS` (value `'wuwei dispatch next'`) and is in
  `wuwei.signal.SILENT` (FR-005). Run it; it fails.

### Implementation

- [X] T005 [US1] In `cli/wuwei/dispatch.py`, `_delta_feedback(first, light=False,
  head='HEAD')`: end the fix range at `head` and name it on the `Head:` line in both texts,
  keeping the `Re-read:` and `Delta review:` prefixes and the #623 sentence byte-identical
  (plan Design 2). `opinion` reads the worktree head before it launches or continues the
  seat and passes it to `_delta_feedback`, so its delta feedback never says `Head: HEAD`
  (review F2; `opinion_fix_round` in `tests/test_dispatch.py` asserts it).
- [X] T006 [US1] In `cli/wuwei/dispatch.py`, `_seats` delta branch: after
  `if not delta_due(...)`, read the live head of `(root / worktree).resolve()` with
  `brief.read(registry.load('vcs', workspace.load_config(root)).head, ...)['sha']`, write
  `delta_head` on the seat with kind `gate.delta_head` only when it differs, and pass the
  head to `_delta_feedback` (plan Design 1, with a `# #669:` comment). T001 passes.
- [X] T007 [US1] In `cli/wuwei/dispatch.py`, `receive`: in a delta round compare the
  verdict head against `seat.get('delta_head') or seat.get('head')` and refuse with both
  heads named; the initial-round condition and message stay as they are (plan Design 3).
  T002 and T003 pass.
- [X] T008 [P] [US1] Add `'gate.delta_head': 'wuwei dispatch next'` to `EVENT_PRODUCERS` in
  `cli/wuwei/commands/event.py` (beside `gate.tiered`) and `'gate.delta_head'` to `SILENT`
  in `cli/wuwei/signal.py` (beside `gate.tiered`). T004 passes.

### Existing tests follow the live-head read

- [X] T009 [US1] The delta continue now reads the live head, so the tests that reach it
  without a VCS fake need one. Install the T001 helper (import it from `test_dispatch`,
  which these modules already import from) just before the transition to `delta`, with any
  full SHA such as `'def5678' + '0' * 33`:
  `tests/test_dispatch.py::test_delta_offers_one_continuation_of_the_stopped_seat`,
  `tests/test_process_depth.py::test_light_fix_is_re_read_by_the_same_seat`,
  `tests/test_pace.py::test_fast_fix_round_is_re_read` (add the `monkeypatch` argument).
  Leave their assertions as they are. Then run the whole suite and give any other test that
  reaches the delta continue without a fake (an adapter read error naming the vcs head) the
  same helper; `tests/test_path_day.py` runs real git and needs nothing.

## Phase 2: Docs and polish

- [X] T010 [P] In `docs/site/daily.md`, step 5 (Delta), add one sentence: `dispatch next`
  records the delta head on the reviewer's seat and the `continue` feedback names it; the
  planner continues the same seat (in its session or as a fresh Agent) and the delta
  verdict's `Head:` is that delta head (FR-006).
- [X] T011 Run `python -m pytest -q` from the repository root; everything passes. Check
  every file this feature touched for em-dashes and emojis and remove any.

## Dependencies

- T001 before T006; T002 and T003 before T007; T004 before T008; T005 before T006 (T006
  calls the new parameter).
- T009 after T006 (the read it accommodates). T011 last.
- [P] tasks touch different files or independent tests and can run alongside their
  neighbours.
