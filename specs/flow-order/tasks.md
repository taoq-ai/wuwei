# Tasks: flow-order

## Phase 1: Tests first

- [x] T001 [US1] `test_the_item_closest_to_done_lists_first_and_age_orders_ties` in tests/test_flow.py
- [x] T002 [US2] `test_an_expedite_item_lists_above_every_class_and_a_second_is_sent_back`
- [x] T003 [US3] `test_an_item_that_waits_shows_waiting_and_adds_its_cost_of_delay_to_what_it_waits_on`
- [x] T004 `test_time_criticality_rises_one_fibonacci_step_per_day_in_progress`
- [x] T005 [US4] `test_in_progress_work_idle_four_hours_with_no_live_seat_shows_stale_at_the_top_of_its_class`
- [x] T006 `test_running_reads_the_items_of_live_seats`
- [x] T007 Run them red: 6 failed

## Phase 2: Implementation

- [x] T008 plan.py: `CLASSES`, `delay`, `score(waiting)`, `cost`, `save` stores `cost`, `add(cls, after)`
- [x] T009 board.py: `running(key)`, `when`, `stage`, `flow`, the row head in `text`
- [x] T010 __main__.py: `--class`, `--after`; `test_the_cli_and_the_lead_file_name_a_class_and_what_an_item_waits_on` red on the main CLI
- [x] T011 docs/design.md, docs/site/concepts/the-day.md, docs/site/reference.md
- [x] T012 `setup.vendor('.')`; full suite green; runtime 3,481 lines
- [x] T013 Route differential main against head

## Phase 3: Merge of main at b9522fc7

- [x] T014 Merge #1238 (multi-session `running`, `changed` stamp), #1240 (smart tier) and #1241; `flow` reads live seats of any session
- [x] T015 `test_an_item_never_waits_on_itself` red, then the self-wait refusal in `plan.add`
- [x] T016 Full suite green; runtime 3,528 lines (+80 over main); route differential at the merged head

## Phase 4: Fix round at f834999 (quality and arch FIX)

- [x] T017 Tests: a rescore never stamps (plan.merge, two clones), a restore or re-add of a second expedite, a done expedite frees the class, a wait cycle, closed waiters, the stage from the row's own gaps, days from the first PR; run red: 6 failed
- [x] T018 `save` compares items without `score`; `expedite` checked in `add` and in `mark` when an item reopens; `add` refuses an `after` id that is the item or waits on it; the stage read before flow's gaps; `days` from the oldest PR
- [x] T019 docs/design.md, the-day.md, reference.md; `setup.vendor('.')`; full suite green; runtime 3,535 (+87 over main)
