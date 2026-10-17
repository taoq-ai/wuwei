# Requirements checklist: gh-doors

- [x] Every acceptance scenario of item gh-doors maps to a test
- [x] Each gh api shape was sent by real gh 2.89.0 to a logging server
- [x] Each merge shape agrees with a pflag v1.0.6 mirror
- [x] `-f query=@file` is a literal query in real gh, so it passes
- [x] The head, base and body read of an `--input` file is unchanged
- [x] Every pre-existing routes.json row keeps its verdict on head
- [x] Each new route is a routes.json row naming its source
- [x] The breaking change has a section with migration notes
- [x] Vendored copy rewritten; drift test passes
- [x] Runtime at 3,000 lines, within the budget
- [x] No emojis, no em dashes
