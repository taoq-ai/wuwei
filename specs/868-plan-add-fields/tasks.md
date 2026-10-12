# Tasks: 868-plan-add-fields

Test first: each implementation task follows its failing test. Depends on #864 T004
(`plan.governed`, `plan.checkout`).

- [x] T001 Test: in a two-repository workspace `plan add X --goal G-1 --repo acme/code` records the repo and `launch_set` returns `wuwei worktree add X --repo acme/code`; without `--repo` or with an unknown one it exits 2 and writes nothing (tests/test_plan.py)
- [x] T002 Implement `--repo` in `plan.add` and the CLI; `_start` reads the item's repo first (cli/wuwei/plan.py, cli/wuwei/commands/plan.py, cli/wuwei/dispatch.py)
- [x] T003 Test: `plan add X --goal G-1 --track FULL --trust-surface` records FULL and trust_surface; `--track MEDIUM` exits 2 with propose's message; an unresolved `--governed-by` exits 2; a resolved one is recorded (tests/test_plan.py)
- [x] T004 Implement `_admitted`, call it from `_proposal` and `add`; add `--track`, `--governed-by` and the flag options (cli/wuwei/plan.py, cli/wuwei/commands/plan.py)
- [x] T005 Planner charter admission sentence and the user docs name the new options (charters/planner.md, agents/planner.md regenerated, docs/site/daily.md, docs/site/reference.md)
- [x] T006 Run every test file that imports a changed module, on 3.12 and 3.11
