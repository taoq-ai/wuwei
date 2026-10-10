# Tasks: tickets from the card

Test first: each test task runs and fails for the expected reason before its implementation
task. Tests are in-process with the fake tracker port behind the real outward wrapper
(`tests/fakes/tracker.py`: `Fake`, `ported`, `registry.load` monkeypatched as in
`tests/test_tracker.py` `ws`); no network, no real adapter. Neutral fixture names only (`A`,
`B`, `C`, `ENG-1`, `Pat Example`). Run the touched files, then the full suite with
`python -m pytest -q` from the repository root.

## Phase 1: the missing-ticket reason by posture (FR-005, FR-006, US4)

- [X] T001 Test in `tests/test_tracker.py`: extend the `config()` helper with `guards` and
  `security` keys and a `posture` argument; parametrize `test_check` so `guarded` returns
  `A has no ticket: the planner proposes one on the item's card ...` with no `bin/wuwei` in
  it, `strict` returns the host terminal commands; the pending-draft case names `drafts show
  draft-1 --widget` below strict and `drafts approve draft-1 ... host terminal` under strict;
  `{'tickets': {'item-1': {'id': None, 'source': 'none'}}}` returns `('skipped', '')`. Fails:
  one wording in every posture, no none.
- [X] T002 Change `tracker.check` in `cli/wuwei/tracker.py` (plan, tracker.py).
- [X] T003 Update the old-wording assertions under the default posture:
  `tests/test_dispatch.py` lines 1457 and 1513, `tests/test_intraday_intake.py` line 238
  (assert the card wording, or set `strict` where the test is about the commands). Run them.

## Phase 2: the proposal shows each ticket (FR-002, US1.1)

- [X] T004 Test in `tests/test_plan.py`: with a three-candidate variant of the `two` helper
  (A `{'ticket': 'ENG-1'}`, B `{'ticket': 'ENG-2'}`, C with no `ticket`) and `tracked(root)`
  written before `plan.propose`, the plan gives
  `plan.md` lines `Ticket: ENG-1 (existing)`, `Ticket: ENG-2 (existing)` and `Ticket: new
  <C scope on one line>`; a `light` candidate under `skip_tiers = ["light"]` has no
  `Ticket:` line; with `tracker = "none"` no `Ticket:` line at all; `"ticket": None` is
  accepted and shows `Ticket: none`; `"ticket": "has space"` still raises `invalid ticket`.
  `plan.gate_widget(root)` Approve description contains `Tickets A ENG-1 (existing), B ENG-2
  (existing), C new <title>` (parts are capitalized) and the Change something description
  names tickets. Fails: no
  ticket lines, `None` refused.
- [X] T005 Add `proposed` and `_tickets`, accept `None` in `_proposal`, add the `Ticket:` line
  in `propose` and the part in `gate_widget` (`cli/wuwei/plan.py`).

## Phase 3: Approve links and opens (FR-003, FR-004, FR-005, US1.2 to US1.4, US2)

- [X] T006 Test in `tests/test_plan.py` (issue acceptance 1): config `[adapters] tracker =
  "linear"` plus `[owner] name`, posture `guarded` then `observe` (parametrize), fake port
  whose `create` returns `ENG-9`; propose A, B (tickets), C (none); `plan.approve(['A', 'B',
  'C'], root, goals_confirmed=True)` succeeds; `tickets` equals `A: {ENG-1, candidate}`,
  `B: {ENG-2, candidate}`, `C: {ENG-9, create}`; the fake saw one `create`, for C; C's draft
  row has status `sent`; `tracker.check` returns `ticket` for A, B and C. A second call
  refuses `already approved` and the fake saw no new call. Fails: approve refuses C today.
- [X] T007 Test in `tests/test_plan.py` (issue acceptance 2): posture `strict`, same setup;
  `main(['plan', 'approve', '--items', 'A', 'B', 'C', '--goals-confirmed'])` returns 1,
  stderr contains `bin/wuwei tracker create C` and `host terminal`, the fake saw no call, no
  draft exists, `approved_items` is empty. Move
  `test_approve_refuses_every_candidate_without_a_ticket` to `strict` (it would reach the
  real Linear adapter below strict).
- [X] T008 Test in `tests/test_plan.py`: candidate `A` with `"ticket": None` and no tier,
  guarded: approve succeeds, the fake saw no call, `tickets['A'] == {'id': None, 'source':
  'none'}`, one `tracker.skipped` event with payload `{'item': 'A', 'ticket': 'none'}`.
  Test: a fake `create` returning `registry.Result(2, reason='linear: unreachable')` makes
  approve refuse naming `C: ` and the reason, with nothing approved. Fails: KeyError on
  `tier`, approve refuses C.
- [X] T009 Implement in `plan.approve` (`cli/wuwei/plan.py`): the `proposed` record loop, the
  below-strict open loop before `update`, the skipped payload.

## Phase 4: plan add drafts an owner item's ticket (FR-008, US5)

- [X] T010 Test in `tests/test_intraday_intake.py`: guarded, fake port, default
  `tracker.auto`: `plan.add('OWN-3', root, goal='G-1', title='Fix the export')` raises
  `StateError` whose text names `drafts show draft-` and not `host terminal`; one pending
  tracker draft whose `inputs.draft.title == 'Fix the export'` and `item == 'OWN-3'`; the
  fake saw no call; `OWN-3` not admitted. Then `drafts.approve(root, <id>)` and the same
  `plan.add` returns `build next`, `tickets['OWN-3']['source'] == 'create'`, still one draft.
  Move `test_owner_named_item_needs_a_ticket_when_a_tracker_is_set` to `strict` and assert no
  draft is created there. Fails: no draft today, `tracker.create` says unknown item.
- [X] T011 Add `row=None` to `tracker.create` (`cli/wuwei/tracker.py`) and the owner-item
  draft step plus `chosen = proposed(candidate)` in `plan.add` (`cli/wuwei/plan.py`).

## Phase 5: the guard (FR-007, US3)

- [X] T012 Test in `tests/test_protect_state.py` with `_planner` and `_seat_hook`, posture
  parametrized over observe, guarded, strict: a seat's `bin/wuwei tracker create A` and
  `bin/wuwei plan set A ticket=ENG-1` are refused (code 2) with `planner` in the reason; the
  planner (`seat=False`) passes both below strict and is refused under strict with `host
  terminal` in the reason; a seat's `bin/wuwei tracker create --bug A Broken --evidence
  cli/x.py:1` passes in every posture; a seat's `bin/wuwei tracker create A -- --bug` and
  `bin/wuwei plan set A ticket=$X` are refused; the planner's `bin/wuwei plan set A
  spec=skipped --reason x` is still refused. Fails: a seat's item create passes and the
  planner's link is refused today.
- [X] T013 Implement in `cli/wuwei/guards/protect_state.py`: the `('tracker', 'create')` row,
  the `('plan', 'set')` reason, `_seat_class_create`, `_planner_ticket` and the two
  conditions in `_owner_action`. Run `tests/test_protect_state.py`, `tests/test_hooks.py` and
  `tests/test_invariants.py` to confirm the wider owner relevance refuses no read.

## Phase 6: invariant I36 (FR-009)

- [X] T014 Test: add `i36` to `tests/test_invariants.py` (plan, I36), `READS['I36'] = (0,)`,
  `INVARIANTS['I36']`, and the I36 row to the design spec 9.2 table in
  `docs/specs/2026-09-24-wuwei-design.md`; run it and see it fail if T013 is reverted.

## Phase 7: charters, agents and docs (FR-001, FR-010)

- [X] T015 Test in `tests/test_charters.py`: `charters/lead.md` contains `"ticket": null`
  and `give each candidate the open ticket`; `charters/planner.md` names tickets in the
  Change something questions and still contains `bin/wuwei tracker create <item>`. Test in
  `tests/test_docs.py`: `docs/site/concepts.md` "Tickets and comments" says Approve opens
  the proposed tickets and that a seat never opens an item ticket. Fails before the edits.
- [X] T016 Edit `charters/lead.md` (1.6.0), `charters/planner.md` (2.1.0), run `bin/wuwei
  agents build` then `bin/wuwei agents check`; edit `docs/site/concepts.md`,
  `docs/site/configuration.md`, `docs/site/reference.md`, `docs/site/daily.md` and the
  `tracker.created` producer text in `cli/wuwei/commands/event.py`.

## Phase 8: verify

- [X] T017 Full suite `python -m pytest -q` green; grep the files written for em-dashes,
  emojis and absolute local paths and remove any.
