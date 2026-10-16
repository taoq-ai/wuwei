# Requirements checklist: free-lines-2

- [x] Every acceptance scenario of item free-lines-2 maps to a test
- [x] replay.replay had no runtime caller before the move (grep)
- [x] replay.record and wuwei evidence --record unchanged
- [x] Board open-PR cache keeps its name and the 60 s TTL
- [x] guards._default keeps its cache name, the 86,400 s age, the main/master fallback, and caches nothing on GhError
- [x] Every route in tests/fixtures/routes.json reads as recorded
- [x] Vendored copy rewritten; drift test passes
- [x] Runtime at 2,962 lines
- [x] No CLI flag, output, config key or replay case format changed
- [x] No emojis, no em dashes
