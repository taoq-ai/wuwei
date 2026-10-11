# Requirements Checklist: 843-discovery-rank-out

**Purpose**: confirm the spec, plan and tasks are complete before implement.
**Created**: 2026-10-11

- [x] CHK001 A non-light item never reaches its gates without its spec, tested in dispatch [FR-004, T001]
- [x] CHK002 Morning discovery and `wuwei discover` stay; only intraday intake goes [FR-001, FR-002]
- [x] CHK003 `plan propose` orders the queue by the framework; `rank` the command goes [FR-005, US4]
- [x] CHK004 Only the PreToolUse spec guard goes; the recorder and stop check stay [FR-003, Assumption 3]
- [x] CHK005 Every removed unit is classed (a) or (b); no (b) check is lost [plan.md table]
- [x] CHK006 Every file deleted and edited is listed; part 17 and 20 dependencies marked [plan.md]
- [x] CHK007 Retired keys listed for `workspace.RETIRED` [plan.md RETIRED]
- [x] CHK008 Tests other files import move before their file goes [T003]
- [x] CHK009 No test is loosened; only touched test files run locally [tasks.md header]
- [x] CHK010 No emojis, em-dashes, absolute local paths, or client, repository or people's names
