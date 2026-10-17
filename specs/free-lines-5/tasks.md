# Tasks: free runtime lines with no behaviour change and no complexity change

## Phase 1: Probes first

- [x] T001 [US1] Differential probe as a pytest file run in `git archive` copies of d1c3d79 and the head: guards.bash over the route corpus, the suite's string literals and 16,932 generated commands, plus board, report, agents, upgrade, evidence.verdicts, hook, plan, CLI, verdict.parse and setup.doctor outputs and file writes
- [x] T002 [US2] Timing probe: each rewritten function at its worst shape at 125 KB and 500 KB on both trees

## Phase 2: Implementation

- [x] T003 [US1] board: `rows` through `evidence._cached` with `TTL`; `compute` reuses `mine` and builds the cache key in place
- [x] T004 [US1] report: `import hashlib` in the stdlib block; `learning`'s exception lines as one comprehension
- [x] T005 [US1] agents.stale and upgrade.items: comprehension, and the import count as a set-size difference
- [x] T006 [US1] evidence.verdicts: the path read in place
- [x] T007 [US1] walrus `is None` tests in hook, plan, verdict, `__main__` and setup
- [x] T008 [US1] Re-vendor .claude/ with setup.vendor() at the head

## Phase 3: Proof

- [x] T009 [US1] Full suite green on the head (1500 passed, 2 skipped, as on main)
- [x] T010 [US1] Differential probe: base and head outputs byte-identical
- [x] T011 [US1] Mutants of the head change probe output (board open_items, board without TTL, report without approved, upgrade on >=, agents with and)
- [x] T012 [US2] Timing: no shape over 1.20 head/base
- [x] T013 [US1] `cat cli/wuwei/*.py | wc -l` at 2,984 or less; guards.py identical to main
