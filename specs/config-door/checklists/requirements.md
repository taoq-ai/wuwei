# Requirements checklist: config-door

- [x] Every acceptance scenario maps to a requirement, a test and a corpus route
- [x] The records rule is reused for both paths; no second path matcher
- [x] Owner verdicts compared main against head over the route corpus and the probe
- [x] Seat reads (`wuwei plan show`, `wuwei plan view`, `wuwei config`, `cat`, Read) pass
- [x] Refusal text names the owner
- [x] SECURITY.md and docs/site/reference.md state the rule
- [x] `.claude/` vendored copy matches
- [x] Tests ran red on main and green at the head
- [x] Mutants on both copies, one at a time
- [x] Runtime 3,910 to 3,930 lines: over the item's budget of 8 by 12, with a Size: line in the PR; under the 4,000 cap
- [x] Corpus routes read the same under `eval` as plain at the head
- [x] `run.sh` written for the owner; not run by the builder
- [x] Rollback line in the spec
- [x] No emojis, no em dashes
