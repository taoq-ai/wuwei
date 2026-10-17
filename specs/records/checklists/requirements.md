# Requirements checklist: records

- [x] Every acceptance scenario of item records maps to a test or a recorded probe run
- [x] Each acceptance-1 command ran under bash in a fresh folder and changed the ledger row or the cache value
- [x] The generated probe reports 0 holes at the head
- [x] The cache refusal names the cache; a Write on a cache entry is refused
- [x] The acceptance-4 commands pass, `find .wuwei -name x` and `cd .wuwei && cat plan.json` among them
- [x] Infra and leak checks keep their decisions with the new shapes
- [x] Every older routes.json row keeps its verdict on head
- [x] SECURITY.md drops the closed gaps and names the new known shapes
- [x] The breaking change has a section with migration notes
- [x] Vendored copy rewritten; drift test passes
- [x] Runtime within the budget
- [x] No emojis, no em dashes
