# Requirements checklist: pr-draft-text

- [x] Both acceptance scenarios of item pr-draft-text map to a test (`tests/test_guards.py`, `tests/test_setup.py`)
- [x] The new test fails on negation, a dropped clause, the old reviewer line and a stale vendored copy, not only on a missing word
- [x] `charters/_pr.md` no longer says "Request a reviewer" or that the gates passed before the PR opened
- [x] Terms reused from `builder.md` and `shepherd.md` ("draft head", "turns ready", reviewers requested after the flip)
- [x] `.claude/wuwei/charters/_pr.md` matches; `agents/` unchanged
- [x] No sentence over 35 words; the charter's average under 20 (`tests/test_charters.py` green)
- [x] No shared file with open PR #1138
- [x] Runtime unchanged (2,976)
- [x] No emojis, no em dashes
