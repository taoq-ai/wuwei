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
- [x] T025 `mutants.py` round 5, 38 mutants: 35 killed. Two survivors showed the `$word` reads redundant, so they and
  their mutants were dropped; the third (eval body first word only) gets an unquoted `eval` test
- [x] T026 `mutants.py` round 6, 36 mutants on both copies, one at a time: 36 killed
- [x] T023 `analysis.md`: no open CRITICAL or HIGH finding
- [x] T017 Full suite green; runtime 3,918 lines (3,930 after gate round 1)

## Phase 4: Gate round 1 at 256a8a2 (arch, security and quality FIX; goal PASS)

- [x] T027 Tests red first (64 failed): `eval` behind `command`, `command -p`, `time`, `time -p`, `builtin`, `env command`,
  `nohup command`, `builtin command`; `$'..'` escapes and splices; an unreadable config.toml write; a backslash in the
  program word; `wuwei sync`; a seat push to `wuwei/state`; 600 nested evals through the guard and the hook; `sed -I`;
  every `wuwei plan` action but the reads refused to a seat; the hook's error path for a seat (tests/test_hook.py)
- [x] T028 `eval` in READ, `builtin` a wrapper; nesting deeper than 64 refused for every session; `unquoted()` decodes
  the escapes at any depth of quoting; `git_push` takes `seat`; `door()` reads the seat words for a seat
- [x] T029 `probe.py`: wrappers x eval, nesting 64, 65 and 600, escapes and splices in programs, actions and paths;
  `run.sh` writes `cases.tsv` itself, so the file leaves the repository
- [x] T030 Docs: design.md section 7, doors.md, SECURITY.md (every claim checked), ADR 0002
- [x] T031 `mutants.py` round 7, 58 mutants on both copies of guards.py and hook.py, one at a time: 52 killed. The six
  survivors (seat word `$` and `sync`, the `\u` escape, the depth bound and its two hand-downs) get tests; each is killed
  when re-run on its own
