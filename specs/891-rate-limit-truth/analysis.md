# Specification Analysis Report: 891-rate-limit-truth

| ID | Severity | Summary | Resolution |
|----|----------|---------|------------|
| A1 | HIGH | Re-asking with `--include` after a primary-worded refusal sends a request into the refusal window, and its headers labelled the bucket; why rate_limit and the refused reply disagreed is unproven. | Resolved: the re-ask is deleted (FR-003); rate_limit decides (FR-001). |
| A2 | HIGH | Checking rate_limit only when the header says 0 would keep two sources of truth. | Resolved: rate_limit is the only source; an empty row is a primary limit with that row's reset. |
| A3 | MEDIUM | When gh's wording is primary but rate_limit shows calls left, the true reading is unknown. | Resolved: the reason names both readings (and an `--include` reply's own headers when present) plus a token hint; secondary is said only on secondary wording or Retry-After. |
| A4 | MEDIUM | `where` could leak a search query (an email) into the reason. | Resolved: a search names `search` only (#362); tested. |
| A5 | MEDIUM | doctor and auth_status parse the `GitHub rate limit until ` prefix. | Resolved: prefix unchanged; doctor and auth tests pass. |
| A6 | LOW | The tracker token path (`_http.request`) still reads its own failed reply's headers. | Accepted, out of scope (not on the pr act path); spec Assumptions. |

Coverage: FR-001 to FR-005 each have tasks (T001 to T007), 100 percent. CRITICAL 0 open, HIGH 0 open.
