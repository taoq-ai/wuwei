# Tasks: a bug a seat finds is filed by the seat

Test first: each test task runs and fails for the expected reason before its implementation
task. Tests are in-process: `outward.classify` on the `configured` fixture of
`tests/test_outward.py`, and `main([...])` on the `ws` fixture of `tests/test_tracker.py` (the
fake tracker port behind the real outward wrapper, `tests/fakes/tracker.py` `ported`). No
network, no real adapter. Neutral fixture names only (`item-1`, `A`, `ENG-1`, `outside-org`,
`Pat Example`). Run the touched files, then the full suite with `python -m pytest -q` from the
repository root.

## Phase 1: the tier decision (FR-001, FR-002, FR-003; US1, US2, US3)

- [X] T001 Test in `tests/test_outward.py`: extend `test_tracker_auto_policy` (or add a
  parametrized sibling) so the nested port draft with category `bugs`, `triage` and
  `follow-ups` gives: under `default_tier = "send"` `(0, 'send')`; under `"ask"` `(1,
  'draft')` (the current `configured` fixture, unchanged) and `send` with `auto = ["bugs"]`;
  under `"block"` `(1, 'block')` with `why` naming `outbound.default_tier`. Category
  `items`, `decisions` and `None` under `send` still give `draft` (unchanged). A `trace`
  list for the `bugs` case under send shows `party tracker: owner, the workspace tracker is
  the owner's own` and `rule 1 default ...: passed: the umbrella decides the owner's own
  tracker`. Fails: every case drafts.
- [X] T002 Test in `tests/test_outward.py`: under `send`, an owner row `{ tool = "tracker",
  audience = "owner", tier = "ask" }` gives `(1, 'draft')` with `why[0]` starting `ask by
  rule 1 (tool=tracker audience=owner) for tracker:`; the same call with `port=False` and a
  `tool` of `mcp__linear__save_issue` (a connector claiming `category`) keeps its #527
  result and never gets the owner party; a GitHub tracker with `project = "outside-org/repo"`
  gives `ask by rule ... (audience=client) for board` as on `main`; a title with
  `salary` drafts by the sensitive row. Fails: the owner row never matches.
- [X] T003 Test in `tests/test_invariants.py`: change the `i7` held case to `('page',
  'decisions')`; add `i55` (plan, "Design spec and invariants") and register it in
  `INVARIANTS` and `READS` (`OUTWARD`). Run the walk: `i55` fails (the `owner` audience
  adapter write with category `bugs` drafts under the send umbrella).
- [X] T004 Implement in `cli/wuwei/outward.py`: `own` in `classify`, `own=` on `_parties`
  with the owner-class fallback, the default-send pass in `decide`, `own` in the umbrella
  condition (plan, outward.py). Run T001 to T003 and all of `tests/test_outward.py`,
  `tests/test_outbound.py`, `tests/test_drafts.py`, `tests/test_graph.py`,
  `tests/test_invariants.py`.

## Phase 2: the seat's command and its reason (FR-004, FR-005; US1, US2, US3)

- [X] T005 Test in `tests/test_tracker.py`: rewrite `test_bug_drafts_once_by_default` as
  `test_bug_from_a_seat_creates_under_send`: `main(BUG + ['--seat', 'builder'])` exits 0,
  stdout has `ENG-9`, `state.read_state(root).get('drafts', {}) == {}`, one port `create`
  call, and the one `tracker.created` payload has `class: bugs`, `subject: item-1`, `seat:
  builder`; the same with `--triage` and `--seat sentinel-quality`; a second identical call
  prints `ENG-9` and writes no event. `--seat lead` exits 2 (argparse). Fails: no `--seat`,
  the bug drafts.
- [X] T006 Test in `tests/test_tracker.py`: keep the idempotent-draft coverage under the ask
  umbrella (`[outbound] default_tier = "ask"` in the `ws` config): exit 1, one pending draft
  with the same draft dict as today, stdout names `bin/wuwei drafts show <id> --widget` and
  `category not in tracker.auto`, not `drafts approve`; a second call prints the same held
  reason and writes nothing. With the owner row `{ tool = "tracker", audience = "owner", tier
  = "ask" }` under send: exit 1, stdout names `rule 1` and `tool=tracker audience=owner`, a
  `draft.created` event exists, `fake.calls == []`. Under `[security] posture = "strict"`:
  stdout names `bin/wuwei drafts approve <id>` and `host terminal`. Under
  `default_tier = "block"`: exit 1, stderr names `outbound.default_tier`, no draft. With
  `adapters.tracker = "github"` and `[tracker] project = "outside-org/repo"`: exit 1, held,
  names `audience=client`, `fake.calls == []`. Fails: the reason is `ticket drafted:
  bin/wuwei drafts approve`.
- [X] T007 Implement `seat=` and `_held` in `cli/wuwei/tracker.py` (`create`, `record`) and
  `--seat` in `cli/wuwei/commands/tracker.py` (plan). Run `tests/test_tracker.py`,
  `tests/test_plan.py`, `tests/test_intraday_intake.py`, `tests/test_drafts.py`.
- [X] T008 Test in `tests/test_protect_state.py` (the #636 seat test near line 1048): the seat
  form `bin/wuwei tracker create --bug A Broken --evidence cli/x.py:1 --seat
  sentinel-quality` passes `_seat_hook` in every posture. Expected to pass with no code
  change; it pins the gate seat's command (owner item 27).

## Phase 3: the day shows who filed (FR-006; US4)

- [X] T009 Test in `tests/test_board_mcp.py` (next to line 290): the `Tickets created` header
  has `Seat`; the row written with `'seat': 'builder'` shows `| builder |`, one without shows
  `| none |`. Fails: no column.
- [X] T010 Implement the column in `cli/wuwei/commands/board.py` (plan).
- [X] T011 Test in `tests/test_report_retro.py`: a day with a `tracker.created` event carrying
  `seat: sentinel-quality` compiles a retro containing `## Tickets seats filed` and `| ENG-2
  | bugs | a | sentinel-quality |`; a day without one has the `| none | | | |` row. Fails: no
  section.
- [X] T012 Implement the section in `cli/wuwei/retro.py` (plan).

## Phase 4: the brief, the charter and the tier listing (FR-007, FR-008; US3.4, US5)

- [X] T013 Test in `tests/test_brief.py`: a gate brief's `Verdict file:` line contains `the
  only file you write` and `tracker create --bug` and no longer `your only write`. Test in
  `tests/test_charters.py`: `_common.md` rule 1 names filing out-of-scope bugs, rule 7
  contains `--seat <your role>` and `never ask the owner`; `tracker create --bug` still
  appears in no other charter. Fails: old wording.
- [X] T014 Change `cli/wuwei/brief.py` line 478 and `charters/_common.md` (version 1.9.0,
  rules 1 and 7); run `bin/wuwei agents build` (or `python3 -P -m wuwei agents build` from
  the repository root) and confirm `tests/test_agents.py` passes.
- [X] T015 Test in `tests/test_outbound.py` (next to the `outbound tiers` tests near line
  491): the umbrella line names `tickets in the workspace's own tracker`. Fails: old line.
- [X] T016 Change the line in `cli/wuwei/commands/outbound.py` (plan).

## Phase 5: invariants and docs (FR-009, FR-010)

- [X] T017 Add row I55 and the I7 note to `docs/specs/2026-09-24-wuwei-design.md` 9.2 (plan).
- [X] T018 Update `docs/site/configuration.md` (`outbound.default_tier`, `tracker.auto`,
  `tracker.create`), `docs/site/concepts.md` ("Tickets and comments") and
  `docs/site/reference.md` (tracker row). Run any docs test that reads them
  (`tests/test_docs*.py`).

## Phase 6: finish

- [X] T019 Run the full suite (`python -m pytest -q`). Grep every file this feature touched
  for em-dashes, emojis and absolute local paths; remove any.
