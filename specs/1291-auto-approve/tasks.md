# Tasks: an owner setting auto-approves plans (#1291)

- [x] T001 Write the failing tests: tests/test_view.py (plan view approves items with a goal, records the auto row with the view line, prints the Ask line only while an item waits), tests/test_plan.py (plan add and --from approve with their own auto rows; no goal and `unplanned` wait; board), tests/test_report.py (the report lists each auto row), tests/test_guards.py (`wuwei config allow auto-approve` in the seat corpus)
- [x] T002 Run them red: 3 failed (IndexError, an empty plan.approved list, TypeError on approve's third argument); the seat corpus row passed already, the config door holds it
- [x] T003 plan.approve takes the view line; __main__ plan view and plan add call it when `auto-approve` is in allow; report lists the rows; mirror to .claude/wuwei/
- [x] T004 Charters (planner.md, _way.md), skills/wuwei-run/SKILL.md and its vendored copy, docs (reference, design, decisions); agents build
- [x] T005 Run the touched tests, tests/test_charters.py, tests/test_setup.py and the full suite green; count the runtime lines
