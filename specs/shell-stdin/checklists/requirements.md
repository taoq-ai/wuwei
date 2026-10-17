# Requirements checklist: shell-stdin

- [x] Every acceptance scenario of item shell-stdin maps to a test or a recorded probe run
- [x] Each acceptance-1 shape ran under bash with a stub git that logged push origin main
- [x] The generated probe reports 0 holes at the head, with positions start, end, after `;`, after `&&`, after `|` and inside `( )`
- [x] The no-door shapes of acceptance 3 pass
- [x] Every routes.json row keeps its verdict on head
- [x] The breaking change has a section with migration notes
- [x] Vendored copy rewritten; drift test passes
- [x] Runtime within the budget
- [x] No emojis, no em dashes
