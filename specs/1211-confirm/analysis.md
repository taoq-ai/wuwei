# Specification analysis: 1211-confirm

Artifacts read: spec.md, plan.md, tasks.md, checklists/requirements.md, against the item's promise
and acceptance, taoq-ai/wuwei#1211 and #1231, the lead's reproduction on main 6828776, and the
constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Coverage | HIGH (closed) | spec.md What the real data shows | The promise's first step asks for a real free-text answer row; none exists in any fixture or in this session | Resolved: the free-text payload is marked reconstructed, the assumed shape is under Assumptions, and the fix is shown to hold under either cause (probe classes late and differing) |
| A2 | Inconsistency | HIGH (closed) | plan.md Lines | Runtime +10 puts the tree at 3,406, over the 3,400 cap, so the budget test fails on this branch alone | Resolved by the lead's ruling for #1231 (more than +5 allowed when stated); the branch merges after free-lines-6 (#1229, 23 lines), as the item's why already says |
| A3 | Coverage | MEDIUM (closed) | spec.md Compaction | #1231's acceptance names a compaction; no compacted transcript exists to reproduce it | Pinned on the record shapes the session shows, plus a compact_boundary row; the next unrecorded answer names its check |
| A4 | Security | HIGH (closed in fix round 1) | hook.py `_shown` | Model-written question text, option labels and WUWEI's own deny reasons fill the tool_result text, so a planted pair recorded approvals the owner never gave (security, arch and quality at a71bcb1) | Resolved: the text fallback is removed; only `toolUseResult.answers` counts, and the three planted cases are tests that record nothing |
| A5 | Coverage | LOW | spec.md How this fails 4 | A real row with no answers dict, if that is #1231's cause, is still not recorded | It now names its check and type; the PR says Refs #1231, which stays open for a captured row |
| A7 | Inconsistency | LOW (closed in fix round 1) | spec.md How this fails 1 | "re-ask only that question" contradicted `_common.md` Decisions 2 | Removed |
| A6 | Coverage | LOW | spec.md How this fails 3 | A forged first entry before the row still suppresses the real answer | Same as main; recorded under What stays open |

No open CRITICAL or HIGH finding.

## Coverage

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 `_shown` pending or per-question | yes | T004, T005 | |
| FR-002 bound | yes | T004, T005 | |
| FR-003 one claim records both parts | yes | T004, T005 | |
| FR-004 note names what is not recorded | yes | T004, T005 | |
| FR-005 docs | yes | T006, T016 | |
| FR-006 failed check named | yes | T014, T015 | |
| FR-007 text match | yes | T014, T015, T021 | |
| FR-008 Stop never blocked | yes | T014, T015, T021 | |

## Constitution alignment

No conflict: stdlib only, no config key, test first, the trust boundary of #962 kept. The runtime
budget is the one tension (A2), resolved by the lead's ruling and the merge order.
