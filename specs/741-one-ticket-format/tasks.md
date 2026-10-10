# Tasks: one ticket id format

Test first: each test task runs and fails for the expected reason before its implementation
task. No test reaches the network: tracker calls go through `tests/fakes/tracker.py` with
`registry.load` monkeypatched, as the existing tests in each file do. Test workspaces set
`[adapters] tracker = "github"` and, where a repository is needed, a `[[repos]]` table
(`name = "acme/app"`, `path = "app"`, `default_branch = "main"`). Run only the touched test
files after each pair, then the full suite (`python -m pytest -q`).

## Phase 1: the shared helper (FR-001, US1, US2)

- [X] T001 Test in `tests/test_tracker.py`: a table for `tracker.full_id(config, ticket)` built
  from `workspace.load_config` on small configs: github with one repo `acme/app`: `'24'` to
  `'acme/app#24'`; github with `tracker.project = "acme/tracker"` and two repos: `'24'` to
  `'acme/tracker#24'`; github with no project and repos `acme/app`, `acme/lib`: `'24'` to
  `'acme/app#24'`; unchanged values: `'acme/other#24'`, `'0'`, `'024'`, `'ENG-24'` on github,
  `'24'` on linear and on `none`; refusals (`ValueError` whose text contains `owner/repo#24`
  and `tracker.project`): github with no project and no repos, github with
  `tracker.project = "TEAM"`.
- [X] T002 Implement `full_id` in `cli/wuwei/tracker.py` as the plan gives it.

## Phase 2: plan add stores the full id (FR-002, US1 scenarios 1-3, US2)

- [X] T003 Test in `tests/test_intraday_intake.py`, beside
  `test_owner_named_item_needs_a_ticket_when_a_tracker_is_set`: with the github tracker and one
  repo `acme/app`, `plan.add('OWN-3', root, goal='G-1', ticket='24')` returns `build next` and
  stores `tickets.OWN-3 == {'id': 'acme/app#24', 'source': 'candidate'}`; then
  `dispatch.tracker_call('OWN-3', 'claim', root)` with a fake tracker port records a `claim`
  call with `'acme/app#24'` and the `tracker.call` event names that ticket. Parametrize the
  config for `tracker.project` (stores `acme/tracker#24`) and two repos without a project
  (stores the first repo's id).
- [X] T004 Test in `tests/test_intraday_intake.py`: github tracker, no project, no repos:
  `plan.add('OWN-4', root, goal='G-1', ticket='24')` raises `ValueError` naming
  `owner/repo#24`; `OWN-4` is not in `items`, `tickets` and `intraday_proposals`, and no
  `plan.added` event and no draft were written. Through `main(['plan', 'add', 'OWN-4',
  '--goal', 'G-1', '--ticket', '24'])` the exit is 2.
- [X] T005 Implement the `full_id` call in `plan.add` in `cli/wuwei/plan.py` (before
  `chosen = proposed(candidate)`).

## Phase 3: plan set ticket= stores and prints the full id (FR-003, US1 scenario 4, US2)

- [X] T006 Test in `tests/test_plan.py`, beside `test_plan_set_records_a_confirmed_ticket`:
  with the github tracker and repo `acme/app`, `main(['plan', 'set', 'A', 'ticket=24'])` exits
  0, the fake's last call is `('created', ('acme/app#24',))`, the stored ticket is
  `{'id': 'acme/app#24', 'source': 'set'}`, the `plan.set` payload ticket is `acme/app#24`,
  and stdout is `A: ticket acme/app#24`. With no project and no repos it exits 2, names
  `owner/repo#24`, never calls `created`, and writes no `tickets`.
- [X] T007 Implement the `full_id` call and the return value in `plan.set_ticket`
  (`cli/wuwei/plan.py`) and print the returned id in `cli/wuwei/commands/plan.py`.

## Phase 4: plan propose stores the full id (FR-004, US1 scenario 5)

- [X] T008 Test in `tests/test_plan.py`, beside `test_light_candidate_is_approved_without_a_ticket`:
  a proposal whose candidate `B` has `'ticket': '24'` on the github tracker with repo
  `acme/app`: after `plan.propose`, `proposal.json` holds `'acme/app#24'` for `B`; after
  `plan.approve(['B'], ...)`, `tickets.B == {'id': 'acme/app#24', 'source': 'candidate'}`.
  With no repository, `plan.propose` raises `ValueError` naming `owner/repo#24` and writes no
  `proposal.json`.
- [X] T009 Implement the candidate loop after `_proposal` in `plan.propose`
  (`cli/wuwei/plan.py`).

## Phase 5: a sent draft prints the ticket it opened (FR-005, US3)

- [X] T010 Test in `tests/test_drafts.py`: extend `test_approved_ticket_creation_is_recorded`
  (or add a sibling using `fake_tracker` with `{'id': 'acme/app#24', 'url':
  'https://example.test/24'}`): `main(['drafts', 'approve', <id>])` prints
  `drafts: <id> sent; ticket acme/app#24 https://example.test/24`; the comment approval in
  `test_tracker_comment_drafts_and_approves_through_comment` still prints `drafts: <id> sent`
  with no ticket part.
- [X] T011 Implement the reason string in `drafts.approve` (`cli/wuwei/drafts.py`).

## Phase 6: init --upgrade normalises stored bare ids (FR-006, US4)

- [X] T012 Test in `tests/test_tracker.py`: `tracker.upgrade(root, config)` on today's state
  with `tickets = {'X': {'id': '24', 'source': 'candidate'}, 'Y': {'id': 'acme/app#2',
  'source': 'set'}, 'Z': {'id': None, 'source': 'none'}}` and repo `acme/app` returns one line
  naming `X 24 to acme/app#24`, stores `acme/app#24` for X only, appends one `plan.set` event
  `{item: X, ticket: acme/app#24, was: '24'}`; a second call returns `[]`; with
  `write=False` it returns the line and changes nothing; with no repository it returns the
  `unchanged` line naming `owner/repo#24` and writes nothing; on linear it returns `[]`; with
  no day directory it returns `[]`; when only yesterday's directory has a `state.json`, that
  one is normalised.
- [X] T013 Implement `upgrade` in `cli/wuwei/tracker.py` (reuse `watch.days`,
  `state.read_state(directory=...)`, `state._write_state(..., directory=...)`).
- [X] T014 Test in `tests/test_workspace.py`, beside `test_upgrade_is_idempotent`: an
  initialised workspace whose config sets the github tracker and a `[[repos]]` table, with a
  `state.json` for the pinned day (pass `WUWEI_NOW` as an env keyword to `cli`, which clears
  it otherwise) holding `tickets.X = {'id': '24', ...}`:
  `cli(tmp_path, 'init', '--upgrade', '--dry-run')` prints `Would upgrade` and the ticket line
  and leaves the state bytes unchanged; `cli(tmp_path, 'init', '--upgrade')` exits 0, prints
  `Upgraded` and the line, stores `acme/app#24`; a second `init --upgrade` prints
  `No workspace changes needed`.
- [X] T015 Implement the call, the printed lines and the no-change condition in `upgrade()`
  in `cli/wuwei/commands/init.py`, and the `plan.set` producer text in
  `cli/wuwei/commands/event.py`.

## Phase 7: the planner may link the ticket (FR-007, US5)

- [X] T016 Regression test in `tests/test_protect_state.py`, in
  `test_item_tickets_are_the_planners`: add `bin/wuwei plan set A ticket=24` and
  `bin/wuwei plan set A ticket=acme/app#24` to the command loop (planner passes below strict,
  seat refused naming the planner, strict names the host terminal). Expected to pass on main;
  if it fails, fix `_planner_ticket` in `cli/wuwei/guards/protect_state.py` in the smallest
  way and note it in this task.

## Phase 8: finish

- [X] T017 Run the full suite (`python -m pytest -q`); check every file written for em-dashes,
  emojis and absolute local paths.

## Dependencies

T001-T002 first (every later phase calls `full_id`). Phases 2 to 5 are independent of each
other. T012-T013 before T014-T015. T016 is independent. T017 last.
