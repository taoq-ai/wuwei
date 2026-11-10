# Requirements checklist: verdict-mask

- [x] The item's acceptance scenario maps to tests (T001, T002)
- [x] One masking helper: `hook.mask` moved to `guards.mask`, canary first, no new inline copy
- [x] The file is masked before its sha256, so attest and evidence read the same bytes
- [x] A verdict with no match keeps its exact bytes
- [x] Verdicts already on disk or on wuwei/state are not rewritten outside a stop
- [x] No config key or ledger kind added
- [x] Runtime at 4,000 lines or fewer, within the item's budget of 6
- [x] Both copies of hook.py changed
- [x] Docs updated: design hook table and the hooks concept page
- [x] Rollback line in the spec
- [x] No emojis, no em dashes
