# Requirements Checklist: 840-mcp-gate-out

**Purpose**: confirm the spec, plan and tasks are complete before implement.
**Created**: 2026-10-11

## Process control

- [x] CHK001 Every removed unit is classed (a) or (b) in plan.md; no (b) check is lost [plan.md table]
- [x] CHK002 The security gate still gets scanner findings (S4) and the sweep still pages on traces (S2) [FR-004, T001]
- [x] CHK003 No launch path reads an MCP registry [FR-002]

## Completeness

- [x] CHK004 Every file deleted and edited is listed, with the part 16 and 17 dependencies marked [plan.md]
- [x] CHK005 Retired keys are listed for `workspace.RETIRED`, and the key with other readers stays [plan.md RETIRED, Assumption 2]
- [x] CHK006 The part 14 handoff is closed: D-n library, `owner_confirm`, `_host_confirm`, LEFT rows [FR-005 to FR-007, FR-010]
- [x] CHK007 What parts 20 and 24 inherit is named [plan.md Handoff]

## Tests

- [x] CHK008 Each behaviour change has a red test before its code [T002, T004, T006]
- [x] CHK009 No test is loosened; the once-row rule moves to another row [T002]
- [x] CHK010 Only touched test files run locally; CI runs the suite [tasks.md header]

## Writing

- [x] CHK011 No emojis, em-dashes, absolute local paths, or client, repository or people's names
