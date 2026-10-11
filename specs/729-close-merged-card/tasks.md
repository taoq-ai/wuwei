# Tasks: a merged PR closes its merge card

Test first: each test task runs and fails for the expected reason before its implementation
task. Tests are in-process with the existing fixtures (`case` and `linked` from
`tests/test_stop.py` and `tests/test_pr_actions.py`, `root` and `approved` from
`tests/test_next.py`, `root` and `config` from `tests/test_grants.py`). Neutral fixtures only.
Run the touched test files after each pair, then the full suite (`python -m pytest -q`).

## Phase 1: who merged (FR-001)

- [X] T001 Test in `tests/test_merge_ports.py`, beside `test_pr_carries_actual_merge_commit`:
  the recorded `pr` body with `merged=True`, a `merge_commit_sha` and
  `merged_by={'login': 'owner-login', 'type': 'User'}` gives `result.data['merged_by'] ==
  'owner-login'`; the unmodified recorded body (no `merged_by` key) gives `None`. Fails with a
  `KeyError` on `merged_by`.
- [X] T002 Implement `merged_by` in `adapters/code_host/github.py` `pr`, and add
  `"merged_by": null` to the recorded `pr` case's expected `data` in
  `tests/fixtures/code_host/recordings.json` (run `tests/test_adapters.py` and
  `tests/test_code_host.py` too).

## Phase 2: the close at the shared spot (FR-002, FR-003, FR-004, FR-005, US1, US2)

- [X] T003 Test in `tests/test_pr_actions.py`, parametrized over the two producers
  (`watch.poll(root)` and `main(['pr', 'state'])`): with `linked(case)`, write through
  `grants.ask` and `grants._record` a planned card (`target 'pr:acme/widget#7'`, rule
  `planned`) and a runtime card (`target 'repo:acme/widget'`, rule
  `'merge: acme/widget#7 at ' + 'a' * 40`); set `host.results['pr'].data.update(state='closed',
  merged=True, merge_commit='b' * 40, merged_by='owner-login')`; run the producer. Assert for
  both ids: `decision_outcomes[id]` has `option 'merged'`, `outcome 'merged by the owner'`,
  `decided_by 'owner'`, `pr 'acme/widget#7'`, `sha 'b' * 40`, `by 'owner-login'` and no
  `reversibility`; `grants[id]['answered'] == 'merged'`; one `decision.closed` event per id
  with payload `id`, `pr`, `outcome`, `sha`, `by`; `decision.answered(data, id) == 'merged'`;
  `status.snapshot(workspace.day_dir(root))['decisions'] == []`;
  `control_plane.pending(root) == {}`. Run the producer again: still exactly two
  `decision.closed` events. Fails: both cards stay open (the scratch reproduction in the spec).
- [X] T004 Test in `tests/test_pr_actions.py`: with the same merged PR, cards that must not
  close: a runtime merge card whose rule names `acme/widget#70`, a planned merge card on
  `pr:acme/widget#8`, a planned merge card on `repo:acme/widget`, a deploy card on
  `repo:acme/widget`, and a planned merge card on `pr:acme/widget#7` already answered `keep`
  through `commands.decision.owner_outcome` (with `integrity._host_confirm` patched to `True`,
  as `tests/test_grants.py` `answer` does). After `main(['pr', 'state'])`: the open ones keep
  `answered None` and no outcome, the answered one keeps its `keep` row, and no
  `decision.closed` event names any of them. Separately, a merge card on `pr:acme/widget#7`
  with the PR `state='closed', merged=False`: the card stays open.
- [X] T005 Test in `tests/test_pr_actions.py`: `signal.classify({'kind': 'decision.closed',
  'payload': {}}, {}) == ('silent', 'Decisions')` (fails before T006: it is a nudge), and `wuwei event decision.closed '{}'` through `main` exits 1
  naming its producer (`EVENT_PRODUCERS['decision.closed']`).
- [X] T006 Implement `grants.MERGED` and `grants.close_merged` in `cli/wuwei/grants.py`, the
  `observe` call in `cli/wuwei/pr_actions.py`, `'decision.closed'` in `SILENT` in
  `cli/wuwei/signal.py`, the `EVENT_PRODUCERS` entry in `cli/wuwei/commands/event.py`, and the
  two `STATE_PRODUCERS` texts in `cli/wuwei/state.py`, as the plan gives them.

## Phase 3: the readers drop it (US1 scenario 2)

- [X] T007 Test in `tests/test_next.py`: `approved(root, {}, decision_routes={'D-1': 'owner'},
  grants={'D-1': {'action': 'merge', 'target': 'pr:example/project#7', 'rule': 'planned',
  'command': None, 'item': None, 'seat': None, 'planned': True, 'answered': None,
  'spent': False}})`; `coarse(root)['state'] == 'decision'`; then
  `grants.close_merged(root, 'example/project#7', {'merge_commit': 'b' * 40, 'merged_by':
  'owner-login'}) == ['D-1']` and `coarse(root)['state'] != 'decision'`. With T006 in place
  this passes on first run; it pins the reader so a later change to `next` cannot bring the
  dead card back. Run it against a stub `close_merged` that returns `[]` without writing to
  see it fail first.

## Phase 4: a closed card grants nothing (US3)

- [X] T008 Test in `tests/test_grants.py`: call `grants.gate` as `merge.by_grant` does
  (payload `{'session_id': '', 'cwd': str(root), 'tool_input': {'command': 'bin/wuwei merge
  fixture-org/app#7'}}`, argv `['bin/wuwei', 'merge', 'fixture-org/app#7']`, rule
  `'merge: fixture-org/app#7 at ' + 'a' * 40`, repo `fixture-org/app`,
  `pr='fixture-org/app#7'`): exit 1 naming `D-1`. Then
  `grants.close_merged(root, 'fixture-org/app#7', {'merge_commit': 'b' * 40, 'merged_by':
  None}) == ['D-1']`; `grants.active(config(root), state.read_state(root), 'merge',
  'repo:fixture-org/app') is None`; the same gate for `fixture-org/app#8` exits 1 naming
  `D-2`, and `records(root) == ['D-1.md', 'D-2.md']`. Fails before T006 (no `close_merged`);
  with T006 it pins I5 and the no-reuse rule.

## Phase 5: docs and the suite (FR-006)

- [X] T009 Add the sentence to the merge paragraph under `## Grants` in
  `docs/site/concepts.md` (plan, Docs); run `tests/test_docs.py`.
- [X] T010 Run the full suite (`python -m pytest -q`); check every file written for
  em-dashes, emojis and absolute local paths.
