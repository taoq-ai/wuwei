# Analysis: 896-trace-sweep

CRITICAL 0, HIGH 0 open.

| ID | Severity | Summary | Resolution |
|---|---|---|---|
| A1 | HIGH | Sweeping only new spans drops a chain whose first step was before the offset. | Resolved (review F1). Each window carries the last earlier span of every tool its sessions used, so a path from any earlier tool into the new spans stays in the graph (FR-002, T001, T009); a recorded chain parks again only when its source and sink both ran in new spans. |
| A2 | HIGH | Chunking by total spans does not bound ZIRAN's cost (one session of 500 varied spans did not finish in two minutes). | Resolved. Windows are cut by spans per session (20), the variable ZIRAN's cost grows with (measured, Assumptions). |
| A3 | HIGH | With whole-day credential reads, a resumed builder that read .env before its park re-parks at every Bash -> Write (S6 regression). | Resolved. FR-004 counts a read only at or after the until of the session's latest finding that named a credential read for the same chain (review F2, D1: an unrelated park, or a resumed park of another chain, no longer clears it); every park of a session with a credential read names it (D2). |
| A4 | HIGH | A forged offset past the day's spans would hide them. | Resolved. The file is protected (FR-001); an offset not at a line start or past the size restarts at 0 (T001), which re-analyzes and never skips. |
| A5 | MEDIUM | A failed park after earlier parks in one window re-analyzes the window next sweep. | Resolved. The dedup key includes since; the retried window keeps its start (T001). |
| A6 | MEDIUM | scanner.unmeasured on every failed receive would flood status. | Resolved. One event per distinct reason (FR-005). |
| A7 | MEDIUM | A version memo inside the adapter is lost: registry.load runs a fresh module per call; test fakes leak across tests. | Resolved. registry.CHECKED holds it; tests/conftest.py clears it per test; failures are never remembered. |
| A8 | MEDIUM | The discovery_rows default 50 changes today's output. | Accepted: 1148 rows on the wuwei repo; the source line names the rest and the key raises it. |
| A9 | LOW | Two concurrent sweeps can both page one window. | Accepted; ponytail comment, same as the discovery cache. |
| A11 | LOW | Each sweep parsed the whole day for credential reads (review F3). | Resolved. The mark keeps the last read per session and the carried ranges; a sweep parses new lines only (T009). |
| A10 | LOW | P2, P5, P7 and the gate-card half of P9 remain. | Deferred in spec.md. |

Coverage: FR-001 to FR-009 map to T001 to T006 and T009, 100 percent. Constitution check: no conflict; the two config keys are owner preferences that vary per workspace (V).
