# Tasks: a cache entry or name never reads, writes or deletes outside .wuwei/cache

## Phase 1: Tests first

- [x] T001 Acceptance 1: a linked cache folder is never read, written or pruned (tests/test_ledger.py)
- [x] T002 Acceptance 3: a linked entry reads as absent and is never pruned through (tests/test_ledger.py)
- [x] T003 Names per path class never leave the folder; a cache folder linked to itself (tests/test_ledger.py)
- [x] T004 Acceptance 2: a Stop with a `../` session_id writes no entry outside the cache (tests/test_hook.py)
- [x] T005 Run the new tests red on main

## Phase 2: Implementation

- [x] T006 `ws._cached`, used by `cache_get`, `cache_put` and `cache_prune`
- [x] T007 Run the new tests green; re-vendor `.claude/wuwei/cli/wuwei/ws.py`

## Phase 3: Checks

- [x] T008 The normalisation probe on main and the branch (`probe.py`, `probe.txt`)
- [x] T009 The full suite once

## Phase 4: Gate round 1 (arch and quality at b0956601)

- [x] T010 Tests: a linked `.wuwei` for get, put and prune; a linked clone entry and folder; a planted `../` clone id; `_confirm` under a linked cache folder
- [x] T011 Run them red at b0956601
- [x] T012 `ws.clone` through `ws._cached` with a plain-token check; `hook._confirm` skips an unchecked entry
- [x] T013 The probe with clone cases; the route differential on main and the head; the full suite once
