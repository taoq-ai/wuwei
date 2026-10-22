# Requirements checklist: 1211-confirm

- [x] Every acceptance scenario of the item maps to a test and to a probe class
- [x] The real flows are captured from this session's transcript with their provenance in tests/fixtures/payloads/README.md
- [x] The free-text shape is marked reconstructed, and the spec says the fix holds under either hypothesis
- [x] An answer counts only with the tool_use id, an AskUserQuestion tool_use and that question's exact answer in the last tool_result row
- [x] A forged first PostToolUse and a replay record nothing the transcript does not hold
- [x] The pending wait is bounded by a named constant (hook.BOUND) and ends in one answer.unconfirmed row
- [x] The reason names which case held, with both values truncated
- [x] (#1231) The reason names the failed check: no tool_use, no tool_result, no toolUseResult answers, or the differing question
- [x] (#1231, fix round 1) The tool_result text is never read; a row with no toolUseResult answers dict records answer.unconfirmed naming that check, and the gates' planted pairs record nothing
- [x] (#1231) An unrecorded answer never blocks the Stop; its note comes on the next tool call, once
- [x] (#1231) The compaction search is stated, and no directory scan is added without evidence
- [x] The route corpus differential lists every moved case with the corpus sha256
- [x] design.md section 8 and the hooks page state the new rule
- [x] No config key, no new ledger kind
- [x] Runtime +9 after the merge of main (3,382), under the 3,400 cap
- [x] .claude/ re-vendored
- [x] How this fails and Rollback in the spec
- [x] No emojis, no em dashes
