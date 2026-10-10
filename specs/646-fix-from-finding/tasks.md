# Tasks: a seat's small fix becomes an item without a ticket

Test first: each test task runs and fails for the expected reason before its implementation
task. Tests are in-process; the tracker is the fake port behind the real outward wrapper
(`tests/fakes/tracker.py` `Fake` and `ported`, `registry.load` monkeypatched as in
`tests/test_plan.py` `opening`). Neutral fixture names only (`A`, `B`, `ENG-1`, `Pat
Example`, `Pin ruff in CI`). Run the touched files after each phase, then the full suite with
`python -m pytest -q` from the repository root.

## Phase 1: the ticket rule reads a small item as `later` (FR-004, SC-002)

- [X] T001 Test in `tests/test_tracker.py`: add cases to the `test_check` table (or a new
  parametrized test over `observe`, `guarded`, `strict`) with `skip_tiers = []`:
  `{'tier': 'light'}` returns `('later', '')`; `{'gates': {'tier': 'light'}}` returns
  `('later', '')`; `{'tier': 'light', 'gates': {'tier': 'standard'}}` returns `missing` with
  the posture's reason; `{'tier': 'standard'}` and `{}` return `missing`; a ticketed light item
  returns `ticket`; `skip_tiers = ["light"]` with `{'tier': 'light'}` still returns
  `('skipped', '')`. Fails: light returns `missing`.
- [X] T002 Change `tracker.check` in `cli/wuwei/tracker.py` (plan section 1).
- [X] T003 Run `tests/test_dispatch.py`, `tests/test_build_next.py`,
  `tests/test_agent_launch.py`, `tests/test_intraday_intake.py`, `tests/test_plan.py`. For a
  test whose intent is the missing-ticket refusal and whose item now ends up light, give the
  item a standard tier in that test (plan, Tests to revisit); never change the rule.
- [X] T004 Test in `tests/test_invariants.py`: add `i56` and its `INVARIANTS` and `READS`
  entries (plan section 10); `test_table_matches_the_checks` fails until the design row
  exists.
- [X] T005 Add the I56 row after I38 in `docs/specs/2026-09-24-wuwei-design.md` section 9.2.
  Run `tests/test_invariants.py`.

## Phase 2: a seat records a finding (FR-001, US1.1)

- [X] T006 Test in `tests/test_notes.py` with an approved-day workspace (reuse a helper from
  `tests/test_intraday_intake.py` or `tests/test_next.py`): `main(['note', '--fix', 'Pin ruff
  in CI'])` exits 0 and prints `fix-pin-ruff-in-ci`; `state.read_state(root)['seat_findings']`
  holds `{'scope': 'Pin ruff in CI', 'evidence': 'seat finding', 'track': 'SLICE', 'at': ...}`;
  the last event is `finding.noted` with `{'id': 'fix-pin-ruff-in-ci', 'title': 'Pin ruff in
  CI'}`. A second identical call exits 1 naming the id. Parametrized refusals exit 1 and write
  nothing: `''`, `'a\nb'`, 121 characters, `'!!! ???'`, `'Fix /etc/hosts/x reader'`. A title
  whose id is a day item (`A`-shaped id via a title `A`, giving `fix-a`, with `fix-a` seeded
  in `items`) exits 1. `main(['note'])` exits 2. The existing `note add` tests stay green.
  Fails: `--fix` unknown.
- [X] T007 Test in `tests/test_notes.py`: `main(['event', 'finding.noted', '{}'])` exits 1
  with `finding.noted: reserved; written by wuwei note --fix` (pattern:
  `tests/test_next.py` `test_path_events_are_reserved`), and
  `state.set_state('seat_findings', '{}', root)` raises `reserved; written by wuwei note
  --fix` (pattern: `tests/test_plan.py` line 490). Fails: the generic producer text.
- [X] T008 Implement `--fix` and `run_fix` in `cli/wuwei/commands/note.py`; add the producer
  entries in `cli/wuwei/state.py` and `cli/wuwei/commands/event.py` (plan section 5). Run
  `tests/test_notes.py`, `tests/test_cli_known_command.py`.

## Phase 3: next proposes it and plan add admits it (FR-002, FR-003, US1.2 to US1.5)

- [X] T009 Test in `tests/test_next.py`: on an approved day with no items in flight and a
  finding written by `note --fix`, `step(root)` returns `state: finding`, `item:
  fix-pin-ruff-in-ci`, command `wuwei plan add fix-pin-ruff-in-ci --from-finding`, and its
  `why` contains the title. With the finding id in `items`, or with `('finding',
  'fix-pin-ruff-in-ci')` done through a `next.action` event as the decision tests do, the row
  is not returned. With no findings, the rows of the existing tests are unchanged. Fails: no
  finding row.
- [X] T010 Add the row in `cli/wuwei/commands/next.py` `step` (plan section 6).
- [X] T011 Test in `tests/test_intraday_intake.py` (issue Acceptance 1): tracker `linear`
  with `required` on, posture guarded, the fake tracker recording calls; `note --fix "Pin ruff
  in CI"`, then `main(['plan', 'add', '--from-finding', 'fix-pin-ruff-in-ci'])` exits 0 and
  prints `{"action": "build next", "item": "fix-pin-ruff-in-ci"}`; the item is in
  `approved_items` with `tier: light`, `source: finding`, `title: Pin ruff in CI`, the day's
  first goal, `budget_size` 1; the fake tracker saw no `create`; no draft exists; the
  `plan.added` event has `source: finding`; `next.step(root)` then returns the `dispatch` row;
  `tracker.check` for the item is `later` and `build.next_action` does not raise the
  missing-ticket refusal (stub what the build needs as the existing `build next` tests do).
  Also: `plan add fix-pin-ruff-in-ci --from-finding --goal G-2` records `G-2` when G-2 is
  approved; `--from-finding` on an unknown id exits 1 naming `wuwei next`; before the gate it
  exits 1 with the existing gate reason; an owner-named item without `--from-finding` keeps its
  #636 draft (`test_owner_named_item_gets_a_ticket_draft_for_its_card` unchanged). Fails:
  `--from-finding` unknown.
- [X] T012 Implement the finding path in `cli/wuwei/plan.py` `add` and the flag in
  `cli/wuwei/commands/plan.py` (plan section 4).

## Phase 4: approve does not refuse a small item (FR-005, US2)

- [X] T013 Test in `tests/test_plan.py` (issue Acceptance 2), using `opening`-style setup with
  `two(A={'tier': 'light'}, B={'ticket': 'ENG-4'})`: under `guarded`, `plan.approve(['A',
  'B'])` exits clean, the fake `create` was called once for A, and `tickets` records A's
  opened ticket (`source: create`); with `create` refused (`Result(1, reason='refused')`),
  approve succeeds, A is in `approved_items` and `tickets` has no A; with the same refusal
  and A at tier `standard`, approve raises naming A as today; under `strict` with A light and
  no ticket, approve succeeds and `create` is never called. Fails: the refused create
  refuses the approve.
- [X] T014 Change the create loop in `cli/wuwei/plan.py` `approve` (plan section 3).

## Phase 5: the ticket after it ships (FR-006, FR-007, US3)

- [X] T015 Test in `tests/test_tracker.py`: with a day item `fix-pin-ruff-in-ci` (goal `G-1`,
  track `SLICE`) and its `seat_findings` record, not in the proposal or discovery,
  `main(['tracker', 'create', 'fix-pin-ruff-in-ci'])` sends a draft with title `Pin ruff in CI`
  and a description holding `Evidence: seat finding`, `Goal: G-1`, `Track: SLICE`. Fails:
  unknown item.
- [X] T016 Add the fallback in `cli/wuwei/tracker.py` `_candidate` (plan section 2).
- [X] T017 Test in `tests/test_stop.py` next to the done-line test: a merged light item `A`
  without a ticket, tracker `linear`: `closing.unresolved(root, rows)` returns `(1, 'A: shipped
  without a ticket: bin/wuwei tracker create A')`; with `strict_close = false` it returns `(0,
  '')` and prints the line to stderr; a merged standard item without a ticket gives no such
  line (unchanged); with the tracker `none` no line. Fails: no line.
- [X] T018 Change `cli/wuwei/closing.py` `unresolved` (plan section 7).

## Phase 6: the retro lists findings (FR-008, US4)

- [X] T019 Test in `tests/test_report_retro.py` (extend the compile fixture): two findings,
  one also a day item at phase `merged`, the other not an item; the compiled retro has `##
  Seat findings` with `- fix-a: A (item merged)` and `- fix-b: B (not added)` in id order;
  with no findings the section body is `none`; `closing.retro` raises no duplicate-section
  finding. Fails: no section.
- [X] T020 Add the section in `cli/wuwei/retro.py` `compile` (plan section 8).

## Phase 7: charters, agents, docs (FR-009)

- [X] T021 Test in `tests/test_charters.py`: `charters/builder.md` names `wuwei note --fix`,
  `charters/lead.md` names `wuwei note --fix` and that a light candidate starts without a
  ticket, `charters/planner.md` names `plan add <id> --from-finding` and `tracker create
  <item>` after it ships; the generated `agents/` files match their charters (the existing
  generation test). Fails: text absent.
- [X] T022 Edit the three charters (plan section 9), run `bin/wuwei agents build`, edit the two
  `docs/site/reference.md` rows. Run `tests/test_charters.py` and `tests/test_docs.py`.

## Phase 8: verify

- [X] T023 Run `python -m pytest -q` from the repository root; everything passes. Check every
  file written for em-dashes, emojis and absolute local paths and remove any.
