# Plan: an owner setting auto-approves plans (#1291)

- `cli/wuwei/plan.py` `approve(root, answer, line='', goals=())`: with a view line it approves
  only open, unapproved items whose goal (upper case) is in `goals`, records
  `{items, answer, auto: true, line}` when any were approved, and drops the board cache.
- `cli/wuwei/__main__.py`: `auto` is the set of open goals (the headings of `goals.md`, upper
  case, minus the goals ruled met) when `auto-approve` is in `allow`, else false. `plan view`
  calls `plan.approve(root, 'auto-approve', <view line>, auto)` before writing the page and prints
  the `Ask: plan:` line only when auto is off or an item still waits; `plan add` (both forms)
  calls it after adding. `plan.py` takes the set as an argument, since `view` imports `plan`.
- `cli/wuwei/report.py`: an `## Auto-approved` section lists each auto row with its time, items
  and line, after the owner prompts.
- `cli/wuwei/hook.py` is not changed: its own board cache drop after a `plan:` answer stays.
- Charters and skill: `planner.md` and `skills/wuwei-run/SKILL.md` ask `plan:` only when the view
  prints the Ask line; `_way.md` names the setting next to admin-merge, within the SessionStart cap.
- Docs: `docs/site/reference.md` (the allow row shows both names; the seat-reads line says plan
  view approves with auto-approve on), `docs/design.md` section 4, `docs/site/concepts/decisions.md`.
- Vendored copies under `.claude/wuwei/` and `.claude/skills/wuwei-run/`; `bin/wuwei agents build`.
- Runtime budget: +12 at most.
