# Tasks: config-door

## Phase 1: Tests first

- [x] T001 [US1] `test_a_seat_write_to_the_config_or_the_plan_is_refused_naming_the_owner`: 50 commands x 2 roles
- [x] T002 [US1] `test_a_seat_edit_of_the_config_or_the_plan_is_refused_and_the_owner_edit_passes`: 4 tools x 6 paths
- [x] T003 [US2] `test_the_owner_session_keeps_every_config_and_plan_write`
- [x] T004 [US3] `test_a_seat_reads_the_config_and_the_plan`, near misses included
- [x] T005 [US1] `test_the_hook_refuses_a_seat_plan_write_and_passes_the_owner` through `hook.handle`
- [x] T006 [US4] `test_sed_in_place_in_any_spelling_is_a_write`
- [x] T007 Run on main: 129 failed, 66 passed (the owner and read tests hold on main)

## Phase 2: Implementation

- [x] T008 `OWNED`, `SEAT_WORDS`, `SEAT_CLI`, `OWNER_ONLY` in cli/wuwei/guards.py
- [x] T009 `bash(..., seat)` and `pre_tool` read `agent_type`; the records calls take `OWNED * seat`
- [x] T010 sed `-i` in any spelling
- [x] T011 Vendored copy `.claude/wuwei/cli/wuwei/guards.py`
- [x] T012 Route corpus: eight acceptance routes, the `seat` field read by the corpus test (run red first: 4 failed)
- [x] T013 SECURITY.md and docs/site/reference.md

## Phase 3: Evidence

- [x] T014 `route_diff.py` main against head, corpus sha256 recorded
- [x] T015 `probe.py` verdicts at main and head, `cases.tsv` for `run.sh`
- [x] T016 `mutants.py` on both copies, one at a time: round 1, 29 of 31 killed
- [x] T018 Survivors closed: `wuwei $'plan' done I-1` refused, `wuwei plan show run-evidence` passes; round 2, 31 of 31 killed
- [x] T019 Codex `apply_patch` of either file from a seat refused, from the owner passes (tests/test_codex.py)
- [x] T020 `probe.py` wuwei program class (spellings x calls x positions): 117 seat holes at 3dffaf94, all `$'..'` quoting
- [x] T021 16 tests red at 3dffaf94; the seat check reads `$word` as `word` and a wrapper unwraps to it; probe holes 0
- [x] T022 `mutants.py` round 3, 33 mutants: 31 killed; the two door-word survivors get stdin and eval tests; round 4, 33 of 33 killed
- [x] T024 Probe positions `echo Q | sh` and `eval Q`: 282 holes at c3d77512; 17 tests red; `eval`'s words read as a `sh -c`
  body, a seat's unreadable text matched with quotes removed; probe holes 0; corpus under `eval` 0 moved at head
- [x] T025 `mutants.py` round 5, 38 mutants on both copies
- [x] T023 `analysis.md`: no open CRITICAL or HIGH finding
- [x] T017 Full suite green; runtime 3,912 lines
