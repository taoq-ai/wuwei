# Tasks: smart-tier

## Phase 1: Tests first

- [x] T001 Worktree from origin/main 86b2e56 on `leone/smart-tier`; runtime 3,396
- [x] T002 Fake host (tests/conftest.py): a file kept as `<path>@<ref>` answers at that ref only
- [x] T003 [US1-US4] tests/test_smart.py: the four acceptance scenarios, the complexity rows, the guard-word rows, the lowering probes (clear on an owner path, clear on a guard change), complex and unclassified, goal in doubt, spec artifacts, the error budget, the create door, `plan add`
- [x] T004 Red at 86b2e56's runtime: 31 failed, 4 passed (acceptance 1 and 4 and two under-threshold rows hold at main)

## Phase 2: Implementation

- [x] T005 `plan.TIERS`, `plan.add` domain and in_doubt, `add_from`, `--tier smart`, `--domain`, `--in-doubt`
- [x] T006 `evidence.cynefin`, `WAIVE`, `DECIDE`, `MCCABE`, `needed` at smart, `rose`, `gates_for` cached read, `RAISE['smart']`, spec artifacts for complex
- [x] T007 `guards.create_door` passes the head and merge base shas
- [x] T008 Both runtime copies; runtime 3,424 (+28)
- [x] T009 charters, `bin/wuwei agents build`, the vendored copy, docs/design.md, docs/site/concepts/evidence.md, docs/site/reference.md

## Phase 3: Proof

- [x] T010 Green: tests/test_smart.py 35 passed, then the full suite
- [x] T011 `probe.py`: 70 generated, 70 ran through evidence.gaps, 0 holes at the head (56 at main) (`probe.txt`)
- [x] T012 `route_diff.py`: corpus sha256 de377966... at both trees; standard, full and clear hosts 0 of 864 move; guard 57 and rise 3 move, each to more gates owed (`route_diff.txt`)
- [x] T013 20 mutants, applied to both runtime copies one at a time: 20 killed by behavioural tests
