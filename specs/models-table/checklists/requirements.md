# Requirements checklist: models-table

- [x] Every acceptance scenario of item models-table maps to a test in `tests/test_charters.py`
- [x] Every role in `agents/allowlist.json` has a row in the planner table
- [x] Each fact the charter states is in a source the page names with its read date
- [x] The Codex mapping is marked unmeasured and named as a reading of the catalog
- [x] No runtime line; `cli/wuwei/agents.py` untouched
- [x] `agents/` and `.claude/` rebuilt; drift tests pass
- [x] No sentence over 35 words in a charter or skill
- [x] No emojis, no em dashes
