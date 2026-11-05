# Plan: open items reach only the planner session (#1276)

## Approach

- `cli/wuwei/hook.py`: a planner check over the ledger (`plan.session` row, or `seat.started` with an item);
  `stop` returns no block for a non-planner; `session_start` replaces the board with the count line for a
  non-planner and keeps andon lines; PostToolUse records `plan.session` for a plan pass by command shape or reply.
- Vendored copy `.claude/wuwei/cli/wuwei/hook.py` matches.
- Tests in `tests/test_hook.py`; callers in `test_flow.py`, `test_charters.py` and `test_watch.py` run in a
  planner session. Docs: `docs/design.md` section 8, `docs/site/concepts/hooks.md` and `watch.md`.

## Constitution check

Stdlib only, no new module, runtime 3,913 of 4,000, test first. Guard code is not touched.
