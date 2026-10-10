# Tasks: the interview reads the config before asking

Test first: each test task runs and fails for the expected reason before its implementation
task. Tests go in `tests/test_interview.py` and use its `root` fixture (config `acme/widget`
then `acme/gadget`, so repo 0 is `acme/widget`) or `offline` for `main('calibrate', ...)`.
Write config text with `(root / '.wuwei/config.toml').write_text(...)`, building on the
module's `ONE` constant. Run `tests/test_interview.py`, then the full suite.

## Phase 1: a config value answers its question (FR-001, FR-003, FR-005; US1)

- [X] T001 Test in `tests/test_interview.py`: config `ONE` with `merge_deploys = false`
  added to the `acme/widget` table, plus `ONE` for `acme/gadget`; no `interview.json`.
  `unanswered(root, ['acme/widget', 'acme/gadget'])` omits `('deploys', 'acme/widget')` and
  keeps `('deploys', 'acme/gadget')`; `main('calibrate', '--questions')` prints no widget
  with `id == 'deploys'` and `repo == 'acme/widget'`; no `interview.json` exists afterwards.
  Fails today: the pair is present.
- [X] T002 Test in `tests/test_interview.py`: a `[security]`, `[outbound]`, `[merge]` and
  `[autonomy]` block setting all five autonomy keys to the Supervised values drops
  `('autonomy', None)` from `unanswered`; the same block without `outbound.default_tier`
  keeps it. Fails today for the full block.
- [X] T003 Implement `_configured` and the `unanswered` change in `cli/wuwei/interview.py`
  (plan, Design 1 and 2). T001 and T002 pass.

## Phase 2: defaults, template and rows without config keys still ask (FR-001, FR-002; US2)

- [X] T004 Test in `tests/test_interview.py`: the shipped `templates/workspace/config.toml`
  plus `ONE`, no `interview.json`: `unanswered(root, ['acme/widget'])` returns every
  (question, repository) pair in table order; the same with `merge_deploys = true` written
  for `acme/widget` still contains `('deploys', 'acme/widget')`; `[repos.merge]` with only
  `auto = false` still contains `('merge', 'acme/widget')`. Expected to pass after T003; if
  it fails, fix `_configured`, not the test.

## Phase 3: asking by id is unchanged (FR-004; US3)

- [X] T005 Test in `tests/test_interview.py`: with `merge_deploys = false` on `acme/widget`,
  `widgets(root, ['acme/widget'], ['deploys'])` returns one card with
  `repo == 'acme/widget'`. Guards against routing ids through the new check.

## Phase 4: unreadable config fails closed (FR-006)

- [X] T006 Test in `tests/test_interview.py`: a `config.toml` that is not TOML makes
  `unanswered` raise `ValueError` (doctor and init already map it to unmeasured).
  Expected to pass after T003.

## Phase 5: finish

- [X] T007 Run the full suite (`python -m pytest -q`); check the changed files for
  em-dashes and emojis.
