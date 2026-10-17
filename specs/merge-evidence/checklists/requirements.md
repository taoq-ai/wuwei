# Requirements checklist: merge-evidence

- [x] Every acceptance scenario of item merge-evidence maps to a test
- [x] Every caller of `owner_approved` and every ruling reader checked; none depends on breaking or exception rulings counting
- [x] The pull_request_target Actions runs shape was read from the real REST API (one read-only call)
- [x] A docs-only diff makes no Actions read
- [x] A failed Actions read is not cached and shows the gap with the error
- [x] The breaking change (an owner review cleared by a breaking or exception ruling now holds) is declared with migration
- [x] Vendored copy rewritten; drift test passes
- [x] Renamed files, code under docs/, any .txt, seat files and an empty list keep the CI gap
- [x] Runtime at 2,980 lines, within the 3,000 budget
- [x] No CLI flag, config key, exit-code meaning or guard route changed
- [x] No emojis, no em dashes
