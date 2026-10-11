# Requirements Checklist: 841-docs-system-out

**Purpose**: confirm the spec, plan and tasks are complete before implement.
**Created**: 2026-10-11

- [x] CHK001 Every removed unit is classed (a) or (b); no (b) check is lost [plan.md table]
- [x] CHK002 The quality gate no longer blocks on a docs value, with a red test [FR-002, T002]
- [x] CHK003 The helper another module imports moves before the deletion [T001]
- [x] CHK004 What is not the docs system is named and kept (DOC class, docs-only tier, MCP docs channel, credentials) [spec Context, Assumptions 2 and 3]
- [x] CHK005 Every file deleted and edited is listed; part 16 dependencies marked [plan.md]
- [x] CHK006 Retired keys listed for `workspace.RETIRED` [plan.md RETIRED]
- [x] CHK007 Charter edits go through `agents build` [T006]
- [x] CHK008 No test is loosened; only touched test files run locally [tasks.md header]
- [x] CHK009 No emojis, em-dashes, absolute local paths, or client, repository or people's names
