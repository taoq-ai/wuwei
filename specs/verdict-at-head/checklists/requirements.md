# Requirements checklist: verdict-at-head

- [x] Every acceptance scenario of the item maps to a test
- [x] The #1135 walk is reused, not written twice (`newer`, called by both readers)
- [x] The small-delta carry rule is unchanged (existing tests green)
- [x] A PASS for another PR or repository counts nowhere; a finding on the PR's line still holds
- [x] The bounds in the spec are backed by fixtures and by the probes' property checks
- [x] The route corpus read at main and at the head, every moved route listed by class
- [x] No config key or ledger kind added
- [x] Runtime within the item's budget of 5 and at or under 3,400
- [x] .claude/ re-vendored
- [x] Rollback line in the spec
- [x] No emojis, no em dashes
