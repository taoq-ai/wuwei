# Requirements checklist: charter-review

- [x] Every acceptance scenario of item charter-review maps to a test in `tests/test_charters.py` or `tests/test_setup.py`
- [x] The four thresholds in `_common.md` Done match `evidence.py` (400, 3, 0.15 over 28 days, 20, 200)
- [x] No charter or skill names `guards.py`, `hook.py`, `routes.json` or an issue number; `AGENTS.md` holds every moved rule verbatim
- [x] The arch charter holds conformance, coupling, contracts, quality attributes, fitness functions, decisions and Breaking, and hands trust to security
- [x] Every gate names its frameworks; the security scanner is defined; supply chain is read
- [x] Every skill description has `Use` and `Not for`; the trigger set has eight and eight per skill with near misses
- [x] No sentence over 35 words in a charter or skill; each generated agent under 2,250 words
- [x] `agents/` and `.claude/` rebuilt; drift tests pass
- [x] Runtime within the budget and unchanged (2,976)
- [x] No emojis, no em dashes
