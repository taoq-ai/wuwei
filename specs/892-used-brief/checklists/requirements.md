# Requirements Checklist: 892-used-brief

**Purpose**: confirm the spec, plan and tasks are complete before implement.
**Created**: 2026-10-12

## Completeness

- [x] CHK001 The root cause names the function and lines that hand out the used brief [spec Root cause]
- [x] CHK002 No record, an older record, a running seat and an unmeasured seat are covered [US1, Edge Cases]
- [x] CHK003 The issue's acceptance (the launch registers) is a test [SC-001]

## Quality

- [x] CHK004 Tests run red before the code [tasks Phase 1]
- [x] CHK005 The fix is in the one shared function, `next_action`, and reuses `_continue` [FR-002]
- [x] CHK006 No emojis, no em-dashes, no absolute local paths [all artifacts]
