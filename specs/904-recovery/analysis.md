# Specification Analysis Report: 904-recovery

| ID | Severity | Summary | Resolution |
|----|----------|---------|------------|
| A1 | HIGH | Turning the environment park into a plain recheck would let the planner or the Codex loop recheck forever on an unrepaired environment. | Resolved: the hold counts repeats with `_signature`; `build.stuck_after` unchanged results park (FR-001); `run_loop` stops on a hold (US1-3). |
| A2 | HIGH | Resetting a parked build to a fresh start would lose the counters and make unchanged failures unbounded. | Resolved: only status and action change; `repeats`, `signature` and `iteration` stay, so the next unchanged failure parks (FR-002, US2-3). |
| A3 | HIGH | The grant must not be applied without the owner, or applied twice. | Resolved: `_resumed` needs a `plan.resumed` after the park, which only the owner's Yes writes; `open_fix` writes `build.fix_opened`, which ends it (FR-003, US3-2). |
| A4 | MEDIUM | `open_fix` relied on callers passing `granted`; the blocking-delta and `_fix_round` callers did not. | Resolved: `open_fix` reads the grant itself; the parameter is gone. |
| A5 | MEDIUM | `derive.offers` red-at-cap asked the owner even after the resume, a second card for the same Yes. | Resolved: it uses `capped` too. |
| A6 | MEDIUM | `owner_hold` raises on a damaged record where the old truthiness check did not. | Accepted: the same record already raises in `merge.check`; damaged state is reported, not guessed. |
| A7 | LOW | `fix round already used` re-parks after a resume. | Deferred: reachable only through a manual transition (spec Deferred). |
| A9 | HIGH | Review F1: a resumed build park left the grant open until a fix round, so at the gates a PARK, ESCALATE or Blocked line would open a round with no owner card. | Resolved: `build.checked` ends the grant (FR-005). |
| A10 | HIGH | Review F2: `derive._gate` still asked the cap card after the owner's resume. | Resolved: it uses `capped` (FR-006). |
| A8 | LOW | Scanner, PARK-verdict and owner parks must not be resumed by this change. | Resolved: their build records are not `parked`; the build reset needs the owner's Yes anyway (Edge Cases). |

Coverage: FR-001 to FR-006 each have tasks (T001 to T014), 100 percent. CRITICAL 0 open, HIGH 0 open.
