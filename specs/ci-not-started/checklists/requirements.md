# Requirements checklist: ci-not-started

- [x] Every acceptance scenario of item ci-not-started maps to a test
- [x] The Actions runs endpoint shape was read from the real API (one read-only call)
- [x] The Actions read happens only for an empty rollup and is cached a day per repository
- [x] A failed Actions read is not cached and counts as CI
- [x] The new gap is a waiting safety gap, so it holds the merge
- [x] The merge door exempts only `CI running` for `--auto`
- [x] A repository with no pull_request run reads as on main
- [x] Vendored copy rewritten; drift test passes
- [x] Runtime at 2,992 lines, within the 3,000 budget
- [x] No CLI flag, config key, exit-code meaning or guard route changed
- [x] No emojis, no em dashes
