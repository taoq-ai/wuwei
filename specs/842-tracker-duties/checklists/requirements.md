# Requirements Checklist: 842-tracker-duties

**Purpose**: confirm the spec, plan and tasks are complete before implement.
**Created**: 2026-10-11

- [x] CHK001 A missing ticket refuses no launch, gate, raise, approve, add or close, each with a red test [US1, T001]
- [x] CHK002 Status, PR link and merged are duties with named events and fields batch 8 can read [spec Duties, Key Entities]
- [x] CHK003 `next` lists every open duty, also for terminal items; close waits on them [FR-005, FR-006]
- [x] CHK004 The loop has a way out of a tracker that never answers [Assumption 6]
- [x] CHK005 No update is written twice [FR-008, L2]
- [x] CHK006 Every removed unit is classed (a) or (b); the external-tracker label guard stays [plan.md table]
- [x] CHK007 Retired keys listed for `workspace.RETIRED`; the LEFT row goes [plan.md RETIRED, FR-010]
- [x] CHK008 Part 16 dependencies marked; parts 21, 22 and 23 handoffs named [plan.md]
- [x] CHK009 No test is loosened; wall tests go with the walls, lifecycle tests stay [tasks.md]
- [x] CHK010 No emojis, em-dashes, absolute local paths, or client, repository or people's names
