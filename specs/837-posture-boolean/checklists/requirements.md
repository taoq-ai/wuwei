# Requirements Checklist: 837-posture-boolean

**Purpose**: confirm the spec, plan and tasks are complete before implement.
**Created**: 2026-10-11

## Process control stays in code

- [x] CHK001 Every floor observe kept blocks with `guards.enforce = false` [FR-003, US1.3, P1]
- [x] CHK002 The seat brief contract and a bare `gh pr create` for a recorded item block with enforce on [US4, T003]
- [x] CHK003 The traces recorder never refuses [US3, T005]
- [x] CHK004 An unreadable config still blocks every refusal [US1.5]

## Completeness

- [x] CHK005 Every posture reader is listed with what it becomes [plan.md reader table]
- [x] CHK006 Retired keys are in workspace.RETIRED [plan.md RETIRED]
- [x] CHK007 `init --upgrade` maps observe and shadow, honours `--dry-run`, keeps an explicit value [US2]
- [x] CHK008 The behaviour change on the guarded default is documented [Assumption 2, analysis B1]
- [x] CHK009 Telemetry and DORA keep their record shape [Edge Cases, analysis T1]
- [x] CHK010 No host-terminal text is added; stale LEFT rows go [FR-010]
- [x] CHK011 Docs edits follow the pass plan; the rest is listed for part 24 [plan.md]
