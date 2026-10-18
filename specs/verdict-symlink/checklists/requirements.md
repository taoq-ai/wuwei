# Requirements checklist: verdict-symlink

- [x] Every acceptance scenario of the item maps to a test
- [x] A link at the copy, at each folder above it and at `verdicts/` itself is refused
- [x] The refusal names the path and says to remove the link
- [x] The write goes to a temporary file beside the copy, then `os.replace`
- [x] The plain worktree copy-in and the main-workspace verdict path unchanged
- [x] No config key, ledger kind or file format added
- [x] Runtime at 3,000 lines or fewer, at most 3 added by this item
- [x] .claude/ re-vendored
- [x] Rollback line in the spec
- [x] No emojis, no em dashes
