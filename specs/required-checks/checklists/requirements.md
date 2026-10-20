# Requirements checklist: required-checks

- [x] Every acceptance scenario of the item maps to a test
- [x] A required check with no run on the head is a safety gap naming it, and the merge door refuses
- [x] Protection and rulesets both count; a check both require is named once
- [x] Every required check green reads as on main
- [x] No protection is not a gap; an unreadable or malformed read fails closed and is not cached
- [x] mergeable_state blocked with no other safety gap is a gap that says so
- [x] The read is cached PR_TTL, keyed by repository and base branch, unambiguously
- [x] No config key or ledger kind added
- [x] Runtime grows by 10 lines or fewer
- [x] .claude/ copy matches cli/wuwei/
- [x] Route differential run at main and at the head, corpus sha256 recorded, every moved route listed
- [x] Rollback line in the spec
- [x] No emojis, no em dashes
