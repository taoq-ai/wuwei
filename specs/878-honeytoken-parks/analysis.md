# Analysis: 878-honeytoken-parks

CRITICAL 0, HIGH 0 open.

| ID | Severity | Summary | Resolution |
|---|---|---|---|
| A1 | HIGH | A seat check inside `security.record` runs before `_record` binds the session, so a seat whose first call reads the honeytoken would not park. | Resolved. FR-002 runs the check after `_record`; T001 covers the first-call binding. |
| A2 | MEDIUM | A seat's read writes a plain and a critical `scanner.finding`, so doctor shows two rows. | Accepted, recorded under Assumptions. The plain one is the non-seat behaviour and stays before the span write. |
| A3 | MEDIUM | The `scanner_hold` card says "tool sequence" for a single read. | Accepted. The chain names `security.honeytoken`; the owner answer is the same. |
| A4 | LOW | The canary has no park. | By design (7.1): the canary is an outward refusal and a page; recorded under Assumptions. |
| A5 | LOW | The bare `Read -> Bash(curl)` egress gap from the #870 review. | Out of scope; under Deferred. |

Coverage: FR-001 to FR-004 map to T001 and T002, 100 percent.
