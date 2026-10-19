# Requirements checklist: verdict-closed

- [x] Every acceptance scenario of the item maps to a test
- [x] Rule 6 and the verdict block say closed findings go under Probes and Findings holds open ones
- [x] The shape refusal names the next free file instead of "Rewrite it"
- [x] The named file is free of any file or symlink in the workspace folder, and can be attested
- [x] The shape check is not loosened (`verdict.FINDING` and `parse` unchanged)
- [x] The symlink refusal and the exclusive temporary write from verdict-symlink are unchanged
- [x] Generated agents rebuilt, under the 2,250 word ceiling, and .claude/ re-vendored
- [x] Runtime grows by at most 1 line
- [x] Rollback line in the spec
- [x] No emojis, no em dashes
