# Tasks: an unfinished build whose worktree moved past its brief takes a new brief

**Input**: [spec.md](spec.md), [plan.md](plan.md)

## Phase 1: tests first (red)

- [x] T001 [US1] `tests/test_build_next.py`:
  `test_a_new_brief_replaces_an_unlaunched_build_past_its_brief_head` (FR-001, FR-002, FR-003,
  SC-001, SC-002); run it, see "cannot replace an unfinished build" for the moved case.
- [x] T002 [US1] add the legacy case (no start head); run it, see the start head missing.

## Phase 2: implementation (green)

- [x] T003 [US1] `next_action` stale condition and record spread (FR-001, FR-002, FR-003).

## Phase 3: verification

- [x] T004 Every test file importing a changed module under 3.12; build, brief, hooks,
  agent_launch and next files under 3.11.

## Phase 4: review fix round

- [x] T005 F1: headless case in the same test (red: no refusal); `stale` needs an unlogged brief
  or a logged HEAD that differs.
- [x] T006 F2: feedback and CI tail asserted in the moved cases (red: KeyError); carried.
- [x] T007 F4: `test_a_fresh_build_starts_at_the_brief_merge_base` (red: start at HEAD); the
  fresh record reads the brief's `Merge-base:` header line.

## Phase 5: delta fix round

- [x] T008 D1: `test_an_unmeasured_seat_on_the_recorded_brief_takes_a_fresh_brief` (red:
  "cannot replace an unfinished build"); a record whose brief another seat ran is stale.
- [x] T009 D2: `test_build_next_never_adopts_another_items_seat` (red: continue); the seat
  lookup matches the item.
- [x] T010 D3: the merge-base test's non-ancestor case (red: start at the stale base); the base
  is the start only when `merge_base(HEAD, base)` is the base.
