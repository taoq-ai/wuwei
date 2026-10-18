# Tasks: closed findings go under Probes, and a refused verdict names the next free file

## Phase 1: Tests first

- [x] T001 [US1] A delta verdict with closures under Probes is attested (tests/test_hook.py)
- [x] T002 [US2] Closures under Findings name quality-abc1234-2.md as the file to write next (tests/test_hook.py)
- [x] T003 [US2] Generated next-free cases: -2, -3, -4, dangling and live link at -2, digit sha, flat, no sha (tests/test_hook.py)
- [x] T004 [US3] The named file is written in the worktree and attested (tests/test_hook.py)
- [x] T005 [US4] The copy-in and replaced-verdict refusals name the free file (tests/test_hook.py)
- [x] T006 [US5] Rule 6 and the generated sentinel-quality agent say closures go under Probes (tests/test_charters.py)
- [x] T007 Run red on main's code: 14 failed (T001 passes on main, by design)

## Phase 2: Implementation

- [x] T008 The `free` helper and the three refusals (cli/wuwei/hook.py)
- [x] T009 The FORMAT note (cli/wuwei/verdict.py)
- [x] T010 Rule 6, the verdict block and the verdict paragraph (charters/_gate.md)
- [x] T011 `bin/wuwei agents build` and `setup.vendor('.')`
- [x] T012 Full suite green; runtime 2,987

## Phase 3: Checks

- [x] T013 Mutants M1 to M9 in fresh copies, each killed (specs/verdict-closed/mutants.py)
- [x] T014 Main-versus-head differential: routes, payloads, generated hand-backs (specs/verdict-closed/probe_differential.py)
