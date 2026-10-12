# Specification Analysis Report: 905-stop-report

| ID | Severity | Summary | Resolution |
|----|----------|---------|------------|
| A1 | HIGH | Stopping the seat on any recording error would end a relaunched seat when a delayed stop races a resume (`test_delayed_stop_cannot_consume_a_resumed_iteration`). | Resolved: `stop_seat(expected=...)` stops only the seat record the stop read; a changed record is left as it is (FR-003). |
| A2 | HIGH | Reading the report before the identity check let a replaced agent's late stop end the replacement seat. | Resolved: builder identity first; `Mismatch` returns without touching the seat (FR-002). |
| A3 | MEDIUM | A kept report from an earlier round could be offered for a later one on the same seat name. | Resolved: the path is on the seat record; a launch writes a fresh record and `stop_seat`, `record_result` drop it. |
| A4 | MEDIUM | Claim 1 (guards ignore the transcript fallback) asked for a new normalization step. | Resolved: verified it does not hold; `hook.fill_stop_text` already normalizes once for every stop guard. No change. |
| A5 | LOW | The Codex `run_loop` result path still refuses malformed usage. | Accepted: outside the stop hook the issue names; recorded under Assumptions. |
| A6 | LOW | A message that differs from the transcript now ends the seat unmeasured instead of leaving it running. | Accepted: same agent, so the seat ended; the report is kept for `--verdict`. |
| A7 | HIGH | Review F1: an unprotected kept report read back unverified lets any live seat forge a verdict or result. | Resolved: `protect_state` protects `days/<d>/reports` and its files; the seat records the kept text's sha256 and `kept_report` refuses a mismatch (FR-007). |
| A8 | MEDIUM | Review F2: a payload message that differs from the transcript was kept as the report. | Resolved: the transcript turn is kept, or nothing (FR-003). |
| A9 | LOW | Review D1: the kept report was hashed, then read again for the lint and the record; a symlinked `reports` directory was followed. | Resolved: `kept_report` reads the bytes once, checks the hash and passes that text on; a sentinel's lint reads a private copy; a symlinked `reports` directory is refused on keep and on read. |

Coverage: FR-001 to FR-007 each have tasks (T001 to T011), 100 percent. CRITICAL 0 open, HIGH 0 open.
