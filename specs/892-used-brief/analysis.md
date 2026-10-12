# Specification Analysis Report: 892-used-brief

| ID | Severity | Summary | Resolution |
|----|----------|---------|------------|
| A1 | HIGH | Returning a fresh `launch` of a used brief can never register (one brief, one seat). | Resolved: the stopped seat's `continue` is returned; the guard's #614 path binds it (FR-002). |
| A2 | HIGH | Starting the bound build at the current HEAD would hide the seat's commits and park on no change. | Resolved: start is the seat's launch HEAD (FR-002); test moves HEAD after the seat. |
| A3 | MEDIUM | A record an older `build next` wrote on the used brief would keep returning its launch. | Resolved: an unbound used seat makes the record replaceable (recorded case). |
| A4 | MEDIUM | An unmeasured or running seat cannot be continued. | Resolved: running waits for its stop hook; other statuses ask for a fresh brief (FR-003). |
| A5 | LOW | The guard still lets a builder launch with no build record, which is how the seat ran outside it. | Accepted, deferred: a flow change outside this issue. |

Coverage: FR-001 to FR-003 each have tasks (T001 to T004), 100 percent. CRITICAL 0 open, HIGH 0 open.
