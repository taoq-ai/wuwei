# Requirements checklist: hook-transcript

- [x] Every acceptance scenario of the item maps to a test and to a probe run
- [x] The owner's trust ruling of 2026-10-19 is quoted in the spec's Clarifications
- [x] A transcript path is read only when it resolves to a regular file under the projects folder
- [x] The projects folder never comes from the caller's environment
- [x] An answer counts only with the AskUserQuestion tool_use and the same answers in the last tool_result row for its id
- [x] An answer the transcript does not show is recorded as answer.unconfirmed with the reason, never dropped while the session calls again
- [x] The wait is bounded (1.5 s, at a Stop) and its need is measured on the real flow
- [x] A seat stop counts only with the harness's meta file and the Agent tool_use in the session transcript; else seat.unconfirmed and nothing more
- [x] Writes under .claude/projects are refused in the records rule's spellings and working-directory forms; reads pass
- [x] The route corpus differential lists every moved route; no other verdict moves
- [x] Fixtures hold no local path, secret or canary; their provenance is in the README
- [x] design.md section 12 drops the item from Deferred; SECURITY.md states what stays open
- [x] No config key added; two new ledger kinds (answer.unconfirmed, seat.unconfirmed)
- [x] Runtime under the 3,400 cap; the item's +22 budget overrun stated with its reason
- [x] .claude/ re-vendored
- [x] Rollback line in the spec
- [x] No emojis, no em dashes
