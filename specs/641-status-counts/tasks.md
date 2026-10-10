# Tasks: the status line counts items in words, not a planned N/M ratio

**Input**: `specs/641-status-counts/spec.md`, `specs/641-status-counts/plan.md`

**Tests**: required (constitution IV). Each behaviour's test task comes before its
implementation task; run the test and see it fail for the expected reason before the code.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: User Story 1 - the owner reads the day's items at a glance (P1)

### Tests first

- [X] T001 [US1] In `tests/test_signal_status.py`, add a sample-day test: a snapshot dict
  with cap 3, `gate_approved` true, phases `planned 5, spec 1, implement 1, gate 1, raised 1,
  merged 3` and one running builder seat; assert `status.line(data)` equals exactly
  `WUWEI 5 planned · 2 building · 2 in review · 3 shipped · seats 1/3 (builder) | pages 0 · nudges 0`
  (spec scenario 1, SC-001). Run it; it fails with `planned 5/3 ...`.
- [X] T002 [US1] In the same test (or a sibling in `tests/test_signal_status.py`), assert that
  every `\d+/\d+` match in `status.line(data)` and in `status.full(data)` is preceded by
  `seats ` (scenario 2, SC-002). Build the `full` input with the keys `full` reads
  (`watch`, `listen`, `sessions`, `next_meeting`, ...) or reuse the `four_seats` fixture
  with the sample phases. Run it; it fails on `planned 5/3`.
- [X] T003 [US1] In `tests/test_signal_status.py`, add phases `parked 1, escalated 1` to the
  sample and assert the work group ends `3 shipped · 1 parked · 1 escalated · seats ...`
  (scenario 3, order from the Clarifications). Run it; it fails.

### Implementation

- [X] T004 [US1] In `cli/wuwei/commands/status.py`, add the `WORDS` constant next to `WIDTH`
  and replace the `work = [...]` line in `_groups` (line 367) with the summed
  `<count> <word>` tokens from `plan.md` Design, reusing `state.BUILD_PHASES`. Leave the
  seats token, `snapshot`, `line` and `full` as they are. T001 to T003 pass.

## Phase 2: Pinned tokens elsewhere (old assertions follow the new renderer)

- [X] T005 [US1] Update the old `phase n/cap` assertions in `tests/test_signal_status.py`:
  line 135 (`2 building`), line 192 (`1 in review`, `1 shipped`; the `phases` JSON assertion
  on line 194 stays), lines 963, 979, 988 to 995 (narrow-line cut sequence: recompute each
  width from the new string length, the cut order must stay roles, then work tokens, then
  attention), 1015, 1021, 1038 (`1 building` for `implement 1/1`).
- [X] T006 [P] [US1] `tests/test_e2e_day.py` line 176: `merged 1/4` becomes `1 shipped`.
- [X] T007 [P] [US1] `tests/test_docs.py` line 106: the daily section 3 marker `planned 1/1`
  becomes `1 planned`. Run it; it fails until T008.

## Phase 3: Docs (FR-005, FR-006)

- [X] T008 [P] [US1] `docs/site/daily.md` lines 248, 253 to 256 and 295 to 296: the new
  tokens and wording from `plan.md` Docs. T007 passes.
- [X] T009 [P] [US1] `docs/site/remote.md` line 270: the `status` reply as `line` prints it
  now, for example `1 building · seats 1/1 (builder) | pages 0 · nudges 1`.
- [X] T010 [P] [US1] `docs/specs/2026-09-24-wuwei-design.md` 5.9 Status line (line 1022):
  "items per phase against CAP" becomes the day's items counted in words, CAP only on the
  seats token (wording in `plan.md` Docs).

## Phase 4: Verify

- [X] T011 Run the full suite (`python -m pytest -q` from the repository root with the
  interpreter the task names); all green. Grep the changed files for em-dashes and emojis.

## Dependencies

- T001 to T003 before T004. T005 to T007 after T004. T007 before T008. T010 and T009 are
  independent. T011 last.
