# Requirements Checklist: 849-edge-and-loop-tests

**Purpose**: confirm the spec, plan and tasks are complete before implement.
**Created**: 2026-10-12

## Process control

- [x] CHK001 Each of the eight edges has one table with refused, allowed, enforce-off and outside-workspace rows [plan.md Edge tables]
- [x] CHK002 The loop property test keeps every invariant and per-issue case [FR-003]
- [x] CHK003 No row of an edge is lost; a dropped row is a named duplicate [spec Assumption 2]

## Completeness

- [x] CHK004 Every timing assertion found at 71d3f06b is listed with its fate [FR-004, plan.md Timing]
- [x] CHK005 Hook latency stays measured, by a script, in the informational job [FR-005]
- [x] CHK006 The collapse order and stop rule are stated; CI holds the limit [plan.md, FR-008]

## Quality

- [x] CHK007 Each consolidated table is shown red once by breaking its edge [tasks.md]
- [x] CHK008 No test is loosened: rows stay, only their packaging changes [spec Assumption 1]
- [x] CHK009 No emojis, no em-dashes, no absolute local paths, no names [all artifacts]
