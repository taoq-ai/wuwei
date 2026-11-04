# Requirements checklist: reports-mask

- [x] Every acceptance scenario of the item maps to a test
- [x] One masking expression: the one `_seat_stop` and `post_tool` already use, no new helper
- [x] Reports already on disk are not rewritten
- [x] `sync.LOCAL`, traces and ledger fields unchanged (outside the promise)
- [x] No config key or ledger kind added
- [x] Runtime at 4,000 lines or fewer, within the item's +2
- [x] Both copies of hook.py changed
- [x] Docs updated: design hook table
- [x] Rollback line in the spec
- [x] No emojis, no em dashes
