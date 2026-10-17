# Tasks: writes to the ledger and the cache meet the ledger door in the spellings sh expands

## Phase 1: Real execution and tests first

- [x] T001 Branch from origin/claude/shell-stdin f7e30fb and merge origin/main ab841e3 (merge-evidence, #1114); runtime 2,980
- [x] T002 [US1] Real bash in a fresh folder changes the records for the seven acceptance-1 commands; the guard refuses each (tests/test_guards.py)
- [x] T003 [US2] Glob, brace, `..`, find, cd, git clean and cache spellings are refused (tests/test_guards.py)
- [x] T004 [US3] A cache write is refused naming the cache; a Write on `.wuwei/cache/ci-x.json` is refused (tests/test_guards.py)
- [x] T005 [US4] The acceptance-4 commands and other reads pass (tests/test_guards.py)
- [x] T006 Infra ask and leak check see the program after the new shapes (tests/test_guards.py)
- [x] T007 Run the new tests on the base: 44 red, the seven real-bash ones failing at the guard after bash changed the records

## Phase 2: Implementation

- [x] T008 `records()` replaces the `LEDGER` regex in redirects, writer arguments and edit paths
- [x] T009 Cache writes refused; `rm` of the cache passes
- [x] T010 `find` with a writing action, `cd`/`pushd` into `.wuwei`, a session inside it, `git clean -x`
- [x] T011 Run the tests green
- [x] T012 Probe holes for POSIX classes and stepped ranges: tests red (3), then green
- [x] T013 Brace cap: test red (timed out at 60 s), then green

## Phase 3: Integration

- [x] T014 routes.json records the acceptance rows; older rows keep their verdicts
- [x] T015 doors.md, design.md and SECURITY.md name the new shapes; SECURITY.md drops the closed gaps
- [x] T016 Re-vendor `.claude/wuwei/cli/wuwei/guards.py`
- [x] T017 Generated probes at head: 0 holes
- [x] T018 Route corpus dumped at main and head with the corpus sha256
- [x] T019 Full suite green; runtime 2,995

## Phase 4: Gate fix round (head 6d4f8af)

- [x] T020 Tests and routes.json rows for the security gate's holes (brackets, git clean pathspecs and `!` excludes, python -c) and the quality gate's surviving mutants: red at 6d4f8af
- [x] T021 Brace cap counts words (512), bracket classes read as `*`, linear regexes; timing test red (4.0 s), then green
- [x] T022 git clean refuses `$ ~ { backtick` pathspecs, records() matches and `!` excludes; `-n` passes
- [x] T023 Writer arguments are also split at quotes and punctuation, so a python -c body is read
- [x] T024 Docs, spec and vendored copy follow; runtime stays 2,995

## Phase 5: Gate fix round (head 4f99d48)

- [x] T025 Tests and routes.json rows for `--no-dry-run`, `--exc`, `--work-tree`, `--git-dir`, `--namespace`, `GIT_WORK_TREE`, a `-c` alias, `--ex src`, `git-clean` and the wide range: red at 4f99d48
- [x] T026 git clean read by allowlist; the dry-run pass is dropped and `git clean -n -x` flips to a refusal
- [x] T027 A brace range builds at most cap + 1 words; tests for width-1 halving and the `(` split
- [x] T028 Docs, spec and vendored copy follow; runtime 2,996
