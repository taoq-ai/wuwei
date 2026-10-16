# Requirements checklist: verdict-handback

- [x] Every acceptance scenario of the item maps to a test
- [x] The role comes from the harness's agent_type, never the message
- [x] One check: the hand-back and the stop both call _verdict_problem
- [x] Evidence's verdict counting and the verdict file location unchanged (outside the promise)
- [x] No config key or ledger kind added
- [x] Runtime at 3,000 lines or fewer, net zero or fewer for this item
- [x] Charter changed in charters/, agents/ rebuilt, .claude/ re-vendored
- [x] Docs updated: design hook table
- [x] Rollback line in the spec
- [x] No emojis, no em dashes
