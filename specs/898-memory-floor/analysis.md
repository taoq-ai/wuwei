# Analysis: 898-memory-floor

| ID | Severity | Finding | Resolution |
| --- | --- | --- | --- |
| A1 | MEDIUM | A refusal in the Agent launch hook on the new floor would only log (#837 capacity refusals) and leave the seat unregistered (#889). | Not added; `next` holds. Recorded under Assumptions. |
| A2 | MEDIUM | `stuck` read whole transcripts; `live` calls it on every launch. | `stuck` reads the tail (`tail_turn`), same answer. |
| A3 | LOW | The launch event's `running` feeds the measured seat cost; adhoc seats use memory too. | The event keeps every running seat; only CAP and the ceiling use `live`. |
| A4 | LOW | A memory hold on a gate made planned items report "a gate waits for seats". | Under a memory hold the gate-first rule is skipped; each planned item names the hold or CAP. |
| A5 | LOW | The MiB floor still does not hold Codex launches in `next` (the fit floors at one seat). | Out of scope; default behaviour unchanged as asked. |
| A6 | HIGH (review F1) | A held briefed planned item still ran `build next` (record, phase move, tracker claim) before its entry became a wait. | The planned loop waits on the hold before `build next`; test asserts it is never called. |

No open CRITICAL or HIGH findings. Every FR maps to a task and a test.
