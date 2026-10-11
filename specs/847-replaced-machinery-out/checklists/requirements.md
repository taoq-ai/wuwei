# Requirements Checklist: 847-replaced-machinery-out

**Purpose**: confirm the spec, plan and tasks are complete before implement.
**Created**: 2026-10-12

## Process control

- [x] CHK001 Every removed unit is classed (a) or (b) in plan.md; no (b) check is lost [plan.md table]
- [x] CHK002 Merge supervision and the 5.6 outcome measurement keep running without the watch [FR-009, T004]
- [x] CHK003 The default-branch push edge holds without `git-hook` [US2, T009]
- [x] CHK004 Outward duties and the close wait are unchanged [US2, T005]
- [x] CHK005 The records floor stays (`days/*/state.json`, `events.jsonl` protected) [Assumption 11]

## Completeness

- [x] CHK006 Every file deleted and edited is listed, with the survivors of each deleted test file named [plan.md]
- [x] CHK007 Retired keys are listed for `workspace.RETIRED` [plan.md RETIRED]
- [x] CHK008 Every hidden reader the reference sweep found has a home (anchor, telemetry, trace sweep, doctor, export, unit remover) [analysis.md H1 to H7]
- [x] CHK009 The batch 8 fix round's end state is designed against [plan.md]

## Quality

- [x] CHK010 A red test precedes every behaviour change [tasks.md]
- [x] CHK011 No test is loosened; deleted tests cover deleted code only [plan.md tests]
- [x] CHK012 No emojis, no em-dashes, no absolute local paths, no names [all artifacts]
