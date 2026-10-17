# Requirements checklist: git-globals

- [x] Every acceptance scenario of item git-globals maps to a test or a recorded probe run
- [x] The three acceptance-1 commands ran under real git against a local bare remote, each result recorded
- [x] The generated probe reports 0 holes at the head and every known-option feature push passes
- [x] The unknown-option refusal names the option and the route
- [x] `git -C sub push origin feature`, `git -c user.name=x push origin feature`, `git --no-pager log` and `git --version` pass
- [x] The git clean allowlist keeps its verdicts
- [x] Every older routes.json row keeps its verdict on head
- [x] The addition to the promise (steering -c) is named in the spec and the PR
- [x] The breaking change has a section with migration notes
- [x] Vendored copy rewritten; drift test passes
- [x] Runtime within the budget
- [x] No emojis, no em dashes
