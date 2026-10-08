# Specification Analysis Report: 283-cruise-mode

Artifacts read: spec.md, plan.md, tasks.md, constitution, design 5.8, 5.8.1, 5.9 and 9, the item and the notes. The base has no tests/test_invariants.py (T042 is conditional).

| ID | Category | Severity | Summary | Resolution |
|---|---|---|---|---|
| A1 | Inconsistency | HIGH | Item acceptance "thin margin goes to the owner" conflicts with #530: the Routine-by-definition classes (all four L2 defaults) are taken at any margin | Resolved: cruise refines the mandate and never overrides it. The fixture is a class raised to L2 with blast radius workspace, where a thin margin is Strategic and goes to the owner (spec, US2.3) |
| A2 | Inconsistency | HIGH | Read as routing, the note "autonomous means each class at its default level" turns every L0 class into a card, breaking #530 and principle #530 | Resolved: the level only selects a cruise answer for a record the mandate takes. Supervised maps to L0 in level() |
| A3 | Security | HIGH | A seat could raise levels by writing cruise.json or a proposal file | Resolved: protect-state guard, `_target` rejection, owner-card-only raise, ceiling cap (T005 to T008, T029) |
| A4 | Security | HIGH | Undo confirmed by "a card was asked" would accept a Keep answer | Resolved: confirmation via card_topic(D-n, 'Undo'), host terminal or DM (T020) |
| A5 | Coverage | HIGH | Status part between nudges and watch breaks existing substring asserts | Resolved: part placed before meeting (T035) |
| A6 | Inconsistency | MEDIUM | Design says the steward proposes and `wuwei promote` lands | Accepted (Assumptions): plan propose writes the cards; the promote-module writer lands them on the owner's answer |
| A7 | Underspecification | MEDIUM | The undo window should start when the nudge reaches the owner | Accepted: it starts at the answer; ponytail comment |
| A8 | Consistency | MEDIUM | Supervised at L0 also changes profiles._current and the seat mandate | Accepted; T035 asserts the mandate block |
| A9 | Performance | MEDIUM | The status line imports decision/cruise when a config exists | Accepted: import happens inside snapshot only when config exists |
| A10 | Ambiguity | MEDIUM | Scope of the thin streak | Resolved: one day, after the last change, reset by a cruise answer (T014) |
| A11 | LOW | LOW | Agreements on the cruise cards (Class other) count toward other | Accepted |
| A12 | LOW | LOW | L1 behaves like L0 | Accepted |
| A13 | Coverage | LOW | FR-017 has no task | Covered by design and T042 |
| A14 | Coverage | LOW | Merge-class levels | Deferred |

No CRITICAL findings; every HIGH finding is resolved in the artifacts. Coverage: each FR-001 to FR-018 and each item acceptance maps to tasks T001 to T043 (spec FR to task table in tasks.md order).
