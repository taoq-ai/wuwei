# Requirements checklist: breaking-latest

- [x] Every acceptance scenario of the item maps to a test
- [x] A declared break (`!` or `BREAKING CHANGE:`) still counts on its own
- [x] How the arch gate decides Breaking is untouched (outside the promise)
- [x] A stale, off-line, foreign or same-head `no` clears no `yes` (security round 1)
- [x] gate_gaps untouched (its ordering is the later item verdict-at-head)
- [x] No config key or ledger kind added
- [x] Runtime at 3,000 lines or fewer; +4 over a budget of 2, accepted by the planner
- [x] .claude/ re-vendored
- [x] Rollback line in the spec
- [x] No emojis, no em dashes
