# Tasks: a launch whose brief does not exist is refused

**Input**: `specs/725-brief-must-exist/spec.md`, `specs/725-brief-must-exist/plan.md`
**Tests**: required (constitution IV); each test task runs and fails before its
implementation task.

## Phase 1: the guard names the missing brief (US1, FR-001, FR-002)

- [X] T001 [US1] Test in `tests/test_agent_launch.py`: with the `launch` fixture, two cases,
  the brief file removed after it was logged, and a prompt naming a brief never written
  (`WUWEI brief: ./.wuwei/days/<day>/briefs/never.md`, with the `./` to cover
  normalisation). `check(payload)` returns exactly
  `(2, 'brief .wuwei/days/<day>/briefs/<name>.md does not exist; run bin/wuwei brief sentinel-arch <item> <name> first')`;
  the day's `seats` are unchanged and no `seat launched` event was appended. Change the
  existing `missing-file` row of `test_guard_table` to hint `does not exist`. Run it: it
  fails (today exit 1 `no brief logged` and exit 2 `agent launch could not run`).
- [X] T002 [US1] Implement in `cli/wuwei/guards/agent_launch.py` `_check`: the existence
  check after the brief path validation, before the events read (plan.md, Design 1). Run
  T001 and the whole `tests/test_agent_launch.py`: green, including the `clean`,
  `unlogged` and `traversal` rows unchanged.

## Phase 2: the records floor blocks in every posture (US1, FR-003, FR-004)

- [X] T003 [US1] Test in `tests/test_posture.py`, next to `test_owner_only_line_below_strict`:
  for `observe`, `guarded` and `strict`, and once more under `guarded` with
  `security.areas.seats = "off"`, `hook.posture({}, [(agent_launch.check, reason, 2)], root)`
  with the T001 reason returns
  `[('agent_launch', reason, 'posture: records = block (floor; no setting lowers it)', 2)]`.
  Run it: it fails (today an empty list below strict, the seats line under strict).
- [X] T004 [US1] Test in `tests/test_agent_launch.py`: the whole hook,
  `main(['hook', 'PreToolUse'])` with a session id and the never-written launch payload,
  under `observe` and `guarded`: exit 2, `permissionDecision` is `deny`, the reason starts
  with `brief .wuwei/days/` and contains the records floor line; seats unchanged and no
  `seat launched` event. Patch `agent_launch.free_memory` as the other tests do. Run it:
  it fails (observe exits 0).
- [X] T005 [US1] Implement: add `'brief .wuwei/days/'` to `RECORDS_FLOOR` in
  `cli/wuwei/guards/__init__.py` with its comment, and set `decided = 'block'` in the
  records floor branch of `posture` in `cli/wuwei/commands/hook.py` (plan.md, Design 2
  and 3). Run T003, T004, `tests/test_posture.py`, `tests/test_hooks.py` and
  `tests/test_invariants.py::test_reason_corpus_has_no_wall`: green, with
  `test_owner_only_line_below_strict` and `test_held_draft_posture_line_names_the_card`
  unchanged.

## Phase 3: today's registration is unchanged (US1 scenario 3, FR-005)

- [X] T006 [US1] Test in `tests/test_agent_launch.py`: the `launch` fixture with its brief
  present under `observe`: the hook exits 0 (or `check` returns `(0, '')`), the seat `gate`
  is recorded `running` with its brief path, and exactly one `seat launched` event names it.
  If an existing test already pins this (`test_reservation_stop_and_reuse`,
  `test_memory_floor_equality_and_completed_seats`), cite it in the task note instead of
  adding one. It passes before and after T002 and T005 (a regression guard, not a red test).
  Note: covered by `test_reservation_stop_and_reuse` (seat `gate` running with its brief) and
  `test_seat_launched_records_free_mib_and_running` (the `seat launched` event); `check` does
  not read the posture, so no new test was added.

## Phase 4: invariant and docs (FR-006)

- [X] T007 Test in `tests/test_invariants.py`: `i61` (the number reserved for this item) reading posture
  only, registered last in `INVARIANTS` and `READS` (plan.md, Design 4). Add the matching
  row last in the 9.2 table of `docs/specs/2026-09-24-wuwei-design.md` in the same task, so
  `test_table_matches_the_checks` holds. Run `test_invariants_hold` with T005 reverted
  locally (or before T005 if done in order): it fails under `observe` and `guarded`; with
  T005 in place it passes.
- [X] T008 Docs: add "a seat launch naming a brief that does not exist" to the records floor
  cases in `docs/specs/2026-09-24-wuwei-design.md` (the `records` bullet),
  `docs/site/security.md` (the `records` bullet), `docs/site/reference.md` (the canary and
  markers sentence) and `docs/site/concepts.md` (the records sentence). No em-dashes, no
  emojis.

## Phase 5: verification

- [X] T009 Run the full suite with the interpreter the task names, `python -m pytest -q`
  from the repository root: all green. Check every file written for em-dashes and emojis.
  Note: per the owner (2026-10-10) only the changed test files were run; CI runs the full suite.

## Dependencies

T001 before T002; T003 and T004 before T005; T002 before T004 (the reason must exist for the
hook test to reach the floor); T005 before T007 passes; T009 last.
