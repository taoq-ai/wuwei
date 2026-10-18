# Requirements checklist: breaking-latest

- [x] Every acceptance scenario of the item maps to a test
- [x] A declared break (`!` or `BREAKING CHANGE:`) still counts on its own
- [x] How the arch gate decides Breaking is untouched (outside the promise)
- [x] No config key or ledger kind added
- [x] Runtime at 3,000 lines or fewer, within the item's budget of 2
- [x] .claude/ re-vendored
- [x] Rollback line in the spec
- [x] No emojis, no em dashes
