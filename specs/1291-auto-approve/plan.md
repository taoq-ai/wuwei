# Plan: an owner setting auto-approves plans (#1291)

- `cli/wuwei/plan.py` `approve(root, answer, line='')`: with a view line it approves only open,
  unapproved items with a goal, records `{items, answer, auto: true, line}` when any were
  approved, and drops the board cache (moved from the hook's plan: answer).
- `cli/wuwei/__main__.py`: `_auto(root)` calls `plan.approve(root, 'auto-approve', <view line>)`
  when `auto-approve` is in `allow`. `plan view` runs it before writing the page and prints the
  `Ask: plan:` line only when auto is off or an item still waits; `plan add` (both forms) runs it
  after adding.
- `cli/wuwei/report.py`: the Owner section lists each auto row with its time, items and line.
- `cli/wuwei/hook.py`: the board cache drop moves into `plan.approve`.
- Charters and skill: `planner.md` and `skills/wuwei-run/SKILL.md` ask `plan:` only when the view
  prints the Ask line; `_way.md` names the setting next to admin-merge, within the SessionStart cap.
- Docs: `docs/site/reference.md` (the allow row shows both names), `docs/design.md` section 4,
  `docs/site/concepts/decisions.md` (the plan: row).
- Vendored copies under `.claude/wuwei/` and `.claude/skills/wuwei-run/`; `bin/wuwei agents build`.
- Runtime budget: +12 at most.
