# Tasks: free runtime lines outside the guard, hook, board and evidence modules

## Phase 1: Tests and probes first

- [x] T001 [US1] `test_restore_reopens_a_parked_or_dropped_item` through `wuwei plan restore`: message, reason, ledger row, unknown id; green on main bcdfc1b
- [x] T002 [US1] Differential probe as a pytest file run in `git archive` copies of bcdfc1b and the head: CLI calls, `cache_get`, `cache_prune` and `find` outputs

## Phase 2: Implementation

- [x] T003 [US1] `__main__`: `main()` returns `args.func(args) or 0`; eleven trailing `return 0` lines go
- [x] T004 [US1] plan: `restore` goes; `cmd_plan` calls `plan.mark(root, id, 'open', 'restored')`
- [x] T005 [US1] ws: `find` as `next(...)`; `cache_get` and `cache_prune` with `contextlib.suppress`
- [x] T006 [US1] Copy the three files into `.claude/wuwei/cli/wuwei/`

## Phase 3: Proof

- [x] T007 [US1] Full suite green on the head, with the same counts as main
- [x] T008 [US1] Differential probe: base and head outputs byte-identical
- [x] T009 [US1] Seven mutants of the head each change the probe output
- [x] T010 [US2] `wc -l cli/wuwei/*.py` at 3,380 or less; guards, hook, board and evidence identical to main
