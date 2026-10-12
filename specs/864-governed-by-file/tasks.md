# Tasks: 864-governed-by-file

Test first: each implementation task follows its failing test.

- [x] T001 Test: a directory governed_by with spec.md resolves in `specmode.governing`; without spec.md it raises (tests/test_spec_mode.py)
- [x] T002 Implement the directory rule in `specmode.governing` (cli/wuwei/specmode.py)
- [x] T003 Test: `plan propose` with one repository refuses a governed_by that does not resolve and accepts a directory with spec.md; shape errors unchanged (tests/test_plan.py)
- [x] T004 Implement `plan.governed` and `plan.checkout`; call them from `_proposal` and `propose` (cli/wuwei/plan.py)
- [x] T005 Test: `plan set A governed_by=<path>`: unresolved exits 2, no Yes exits 1 with the card, Yes records it with a plan.set event (tests/test_plan.py)
- [x] T006 Implement `plan.set_governed_by` and the `plan set` route and help (cli/wuwei/plan.py, cli/wuwei/commands/plan.py)
- [x] T007 Test: a planned item whose governed_by does not resolve is a park with the fix, and the next queued item starts at CAP (tests/test_dispatch.py)
- [x] T008 Implement the check in `dispatch._start` (cli/wuwei/dispatch.py)
- [x] T009 Run every test file that imports a changed module, on 3.12 and 3.11
