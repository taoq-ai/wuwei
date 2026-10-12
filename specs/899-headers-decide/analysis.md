# Specification Analysis Report: 899-headers-decide

| ID | Severity | Summary | Resolution |
|----|----------|---------|------------|
| A1 | HIGH | #891 made rate_limit the decider; field evidence shows it reporting 5000 while the refused reply's headers say core 0 and that reset holds. | Resolved: the reply's headers decide (FR-002); rate_limit is the fallback only (FR-003). |
| A2 | HIGH | Reading headers must not cost a request (a request inside a secondary limit can extend it). | Resolved: `--include` rides on the read itself (FR-001); no re-ask; tested by call counts. |
| A3 | MEDIUM | `--paginate --slurp` with `--include` prints a head per page; the layout next to the slurped array is unprobed. | Accepted: paged reads keep the rate_limit fallback (spec Assumptions). |
| A4 | MEDIUM | Adding `--include` changes every read's stdout; a body parser that sees the head fails closed. | Resolved: the head is cut before parsing; a test replays every single-page recording with a head. 304 conditional reads are unchanged. |
| A5 | MEDIUM | doctor and auth_status parse the `GitHub rate limit until ` prefix. | Resolved: prefix unchanged; doctor and auth tests pass. |
| A6 | LOW | Headers say 0 and Retry-After is present: which wait wins. | Resolved: the header reset (spec Assumptions); tested. |
| A7 | LOW | Writes could carry `--include` too at no cost. | Accepted: out of the issue's scope (spec Assumptions). |

Coverage: FR-001 to FR-005 each have tasks (T001 to T009), 100 percent. CRITICAL 0 open, HIGH 0 open.
