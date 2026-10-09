# Tasks: merge eligibility after a real day

Test first: each test task runs and fails for the expected reason before its implementation
task. No test reaches the network or a real `gh`: the merge tests use the `Fake` code host,
setup uses its fixture host. Run only the touched test files, then the full suite.

## Phase 1: risk evidence for plan add (FR-001 to FR-004, US1)

- [X] T001 Test in `tests/test_intraday_intake.py`: `plan.added` carries `flags` for a
  candidate (its measured flags) and an owner item (all False); `plan add` on an item without
  evidence records a `replan` event and returns `risk recorded`; a second call is refused with
  `already in the plan`.
- [X] T002 Test in `tests/test_merge.py`: an item whose only evidence is `plan.added` passes;
  no evidence gives exit 2 naming `bin/wuwei plan add item-7`; after `plan add item-7` the check
  passes.
- [X] T003 Implement `merge.risk_evidence`, the reason, and `plan.add` (flags and replan).

## Phase 2: the deploys question (FR-005, FR-006, US2)

- [X] T004 Test in `tests/test_interview.py`: the id list gains `deploys` before `merge`; the
  widgets list `Merges do not deploy` first for a snapshot with no deploy facts and `Merges
  deploy` first for a deploy workflow or a repository missing from the snapshot; the answer
  sets `repos.N.merge_deploys`. Test in `tests/test_setup.py`: setup passes the order from the
  survey (a deploy workflow in one repository).
- [X] T005 Implement `calibrate.deploys`, the row, `deploys_first`, `leads`, `first` by
  repository in `ask` and `widgets`, setup and `calibrate --interview`; update the tests that
  pin the id list, the terminal replies and setup's `first`.

## Phase 3: size_exclude (FR-007, US3)

- [X] T006 Test in `tests/test_merge.py`: `results/run.json` with 1000 lines passes with
  `size_exclude = ["results/*.json"]`, fails without it, a never-auto excluded file is refused,
  a rename from an excluded path counts.
- [X] T007 Implement `size_exclude` in `MERGE_SCHEMA` and the size rule in `merge.check`.

## Phase 4: docs (FR-008)

- [X] T008 Template line; configuration.md rows and interview table; daily.md list.

## Phase 5: verify

- [X] T009 Full suite `python -m pytest -q`; adversarial review (correctness, security,
  ponytail).
