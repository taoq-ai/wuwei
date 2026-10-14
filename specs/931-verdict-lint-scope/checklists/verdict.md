# Requirements Checklist: Verdict lint scope

**Purpose**: Review the issue-specific lint contract.
**Created**: 2026-10-14
**Feature**: [spec.md](../spec.md)

## Parsing

- [x] CHK001 Is the authorized Findings section named without depending on citation position? [Clarity, FR-001]
- [x] CHK002 Are required finding fields and PASS/FIX consistency measurable? [Completeness, FR-002, FR-003]

## Hook scope

- [x] CHK003 Is PostToolUse limited to the file identified by its write? [Clarity, FR-005]
- [x] CHK004 Is SubagentStop tied to its registered sentinel? [Coverage, FR-005]

## Notes

These markers record requirements quality. Task status is tracked separately.
