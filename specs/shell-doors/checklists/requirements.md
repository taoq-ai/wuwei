# Requirements checklist: shell-doors

- [x] Every acceptance scenario of item shell-doors maps to a test
- [x] Each of the seven acceptance shapes ran under bash with a stub git that logged push origin main
- [x] The punctuation rule splits rather than refuses, so the #1038 test still passes
- [x] `$'` and `$"` inside other quotes stay literal and pass
- [x] Every pre-existing routes.json row keeps its verdict on head
- [x] Each new route is a routes.json row naming its source
- [x] The breaking change has a section with migration notes
- [x] Vendored copy rewritten; drift test passes
- [x] Runtime at 2,999 lines, within the budget
- [x] No emojis, no em dashes
