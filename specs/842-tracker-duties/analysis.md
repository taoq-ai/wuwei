# Specification Analysis Report: 842-tracker-duties

Artifacts read: spec.md, plan.md, tasks.md; the constitution (2.2.0); the #789 pass plan
(owner constraints, "Process control kept", "Outward duties", batch 8 care); the part 16 plan
and working tree; the code and tests at d60253b8.

| ID | Category | Severity | Location(s) | Summary | Resolution |
|----|----------|----------|-------------|---------|------------|
| D1 | Owner constraint | CRITICAL | Outward duties | The owner requires the lifecycle updates to happen, be recorded, be listed by `next`, and hold done. Deleting only the walls would leave failed moves unnoticed. | Resolved: duty events on `tracker_call`, `open_duties`, the `next` row and the close wait (FR-002 to FR-006), each with a red test. |
| D2 | Batch 8 contract | CRITICAL | Key Entities | Batch 8 derives `next` from files; a duty held only in `state.json` would be lost. | Resolved: duties live only in events, with named kinds and fields (Assumption 7, Handoff). |
| L1 | Dead end | HIGH | close | A tracker that never answers would hold close forever, a loop dead end. | Resolved: tracker duties stop counting under `adapters.tracker = "none"` (Assumption 6), tested in `next` and close. |
| L2 | Duplicate send | HIGH | `tracker._entries` | Moving the PR link into the duty while `tracker log` still writes it would post twice. | Resolved: FR-008 removes the entries; the log test asserts none. |
| W1 | Scope | HIGH | `strict_close` | Close's "ticket not done" line was a wall and a real missed update. | Resolved: split in the plan table; "not done" becomes the done duty (b), "shipped without a ticket" goes (a). |
| G1 | Governance | MEDIUM | constitution | Its tracker hygiene bullet looks like a wall. | It governs WUWEI's own issues, not the product; unchanged. |
| S1 | Signal | LOW | `signal.py` | The none-adapter reason mismatch tiered a none tracker as warn. | Fixed in passing (Assumption 8). |

**Coverage**: FR-001 T001, T002; FR-002 T003, T004; FR-003 T003, T004; FR-004 T003 to T006;
FR-005 T005, T006; FR-006 T005, T006; FR-007 T003, T004; FR-008 T003, T004; FR-009 T002, T007;
FR-010 T007; FR-011 T008. 11 requirements, 9 tasks, 100%.

**Constitution Alignment**: I to VII hold; III via one performer and one reader; IV via T001,
T003, T005, T007.

**Next Actions**: no CRITICAL or HIGH finding is open. Proceed to implement.
