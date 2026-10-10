# Tasks: wuwei pr raise --draft

Test first: each test task runs and fails for the expected reason before its implementation
task. No test reaches the network or a real `gh`: raise tests use the `case` fixture and
`solo_raise` helper of `tests/test_shepherd.py`, act tests use `linked(case)` of
`tests/test_pr_actions.py`, adapter tests use the recorded `gh` replay. Run only the touched
test files after each pair, then the full suite (`python -m pytest -q`).

## Phase 1: the ready port operation (FR-005)

- [X] T001 Test in `tests/test_adapters.py`: add `('code_host', 'ready', ('ref',), False)` to
  `CALLS`, so `test_module_contracts` fails until the registry and both adapters have it. Add
  `ready` to the recording fake in `tests/fakes/code_host.py`.
- [X] T002 Test in `tests/fixtures/code_host/recordings.json`: one `ready` recording, args
  `["acme/widget#7"]`, step argv `["pr", "ready", "https://github.com/acme/widget/pull/7"]`,
  stdout `""`, data `{"ready": true}` (picked up by `test_write_recording` and
  `test_write_failure` in `tests/test_code_host.py`). In `tests/test_code_host.py`
  `test_invalid_write_input_never_spawns`, add `('ready', ['https://evil.test/acme/widget/pull/7'])`
  and `('ready', ['../widget#7'])`.
- [X] T003 Implement `'ready': ('ref',)` in `cli/wuwei/registry.py`, the `['pr', 'ready', url]`
  allowlist case and `ready` in `adapters/code_host/github.py`, and `ready` in
  `adapters/code_host/none.py`.

## Phase 2: raise as a draft (FR-001 to FR-004, US1, US2)

- [X] T004 Test in `tests/test_shepherd.py` (US1): with `solo_raise` plus
  `items.ITEM-1.owner_merge = {value: true, by: planner, at: ...}`, ranked reviewers (restore
  `authorship` rows for alice and bob as in `test_raise_checks_gates_then_requests_recent_authors`,
  `request_reviewers` returning them) and `host.results['pr'].data['draft'] = True`,
  `raise_pr(...)` exits 0; the `create_pr` args carry `draft: True`; `REF` is in
  `raised_prs`; the item phase is `raised`; the last `pr.raised` event payload has
  `draft: True`; `pr_reviewers[REF]` is the ranked list; `request_reviewers` was called with
  it; stdout has `REF` and `reviewers: <the ranked logins>`.
- [X] T005 Test in `tests/test_shepherd.py` (US2): the same item without `owner_merge` and
  `raise_pr(..., draft=True)` gives the same result; without `draft` (the fixture PR not a
  draft) `create_pr` gets `draft: False`, the `pr.raised` payload has no `draft` key, and
  stdout still lists `reviewers: ...`.
- [X] T006 Test in `tests/test_shepherd.py`: a draft raise whose created PR reads
  `draft: False` exits 2, records no PR (`raised_prs` as the fixture left it, item `pr` unset, no `pr.raised` event) and requests no
  reviewer.
- [X] T007 Test in `tests/test_shepherd.py`: `main(['pr', 'raise', 'acme/widget', '--base',
  'main', '--title', 'T', '--body-file', <file>, '--item', 'ITEM-1', '--draft'])` with
  `wuwei.shepherd.raise_pr` monkeypatched passes `draft=True`; without the flag `draft=False`.
- [X] T008 Implement `draft` in `shepherd.raise_pr` (flag, `owner_hold`, payload, created-PR
  check, `record_pr`, reviewers line) in `cli/wuwei/shepherd.py`, `record_pr(draft=)` in
  `cli/wuwei/state.py`, and `--draft` with `run_raise` in `cli/wuwei/commands/pr.py`.

## Phase 3: pr act marks the draft ready (FR-006, US3)

- [X] T009 Test in `tests/test_pr_actions.py`: on `linked(case)` with
  `host.results['pr'].data['draft'] = True` and `host.ready` replaced by a function that
  records the call, sets the fixture's `draft` to False and returns `Result(0, {'ready': True})`:
  (a) with `items.A.owner_merge = {value: false, by: owner, at: ...}`, `main(['pr', 'act',
  REF])` exits 0, prints `{"action": "ready", "pr": REF}` and `ready` ran once; (b) with the
  flag true, and with no flag, `ready` is never called; (c) `main(['pr', 'act', REF,
  '--ready'])` with the flag true calls `ready` and exits 0; (d) a closed draft is never
  readied.
- [X] T010 Test in `tests/test_pr_actions.py`: `--ready` on a non-draft approved PR prints
  `REF: already ready for review`, exits 0 and never calls the host `merge`; `--ready` with
  `--run` exits 2 (argparse); `ready` returning `Result(2, None, 'offline')`, or leaving the
  fixture a draft, exits 2 with `REF: PR action unmeasured:`; a malformed `owner_merge`
  record exits 2 and calls no `ready`.
- [X] T011 Test in `tests/test_pr_actions.py`: `pr_actions.evaluate(root, [REF])` rows carry
  `draft` True for the draft fixture and False otherwise.
- [X] T012 Implement the row `draft`, `act(ready=)` and `_ready`, which also reads the cleared flag, in
  `cli/wuwei/pr_actions.py`, and `--ready` with `run_act` in `cli/wuwei/commands/pr.py`.

## Phase 4: docs and the suite (FR-007)

- [X] T013 Update "Raising a PR" in `docs/site/reference.md`: `--draft` and the automatic
  draft for an `owner_merge` item, the `reviewers: <logins>` line, `pr act <ref> --ready` and
  the automatic ready after the owner clears the flag.
- [X] T014 Run the touched test files (owner rule of 2026-10-10: CI runs the full suite); all green. Check the changed files
  for em-dashes, emojis and absolute local paths.
