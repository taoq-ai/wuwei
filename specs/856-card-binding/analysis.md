# Specification Analysis Report: 856-card-binding

| ID | Severity | Summary | Resolution |
|----|----------|---------|------------|
| B1 | HIGH | Options no longer bind: a planner could ask the exact question with a misleading Yes description. | Resolved by the owner's ruling in #856 (the token binds, the diff is for review). The question still names the exact command and token; a changed question is a different action and does not count. Recorded in design 9.1; the #831 F6 test is replaced by `test_issue_856_a_shortened_option_counts`. |
| B2 | HIGH | Seat answers, forged notes and damaged rows must still count for nothing. | Resolved: the recorder skips `agent_id`, only `gate.asked` rows are read; the existing tests pass. |
| B3 | MEDIUM | Review F2: with a command token, an old Yes on `config set k v` could re-apply over a later owner change. | Resolved: a Yes is spent by the `owner.approved` row of the run that applies it (FR-005); the close hold reads without spending. Tested. |
| B4 | MEDIUM | A short shared token (`hold 1`) would fire the mismatch line for the wrong item. | Resolved: the token topic is recorded only for 12-hex digests; binding never uses it. |
| B5 | LOW | Rows recorded before the upgrade have old-shape reply topics. | Accepted: day-scoped, at most one card re-asked. |
| B7 | LOW | Review F4: a card without a token got no mismatch line. | Resolved: the hook records the command part of each answered question (FR-006). Tested. |
| B8 | LOW | Review F3: the planner can misdescribe an action on the exact question. | Accepted trade-off, recorded in the spec Assumptions (the owner's #856 ruling). |
| B6 | LOW | `owner_answer` and `owner_topic` lose parameters. | Resolved: all callers updated. |

Coverage FR-001 to FR-006, 100 percent; CRITICAL 0, HIGH 0 open.
