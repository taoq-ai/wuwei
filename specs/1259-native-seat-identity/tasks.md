# Tasks

## Setup
- [x] T001 Read approved item, native findings, callers and constitution; write spec and plan.

## US1: Successful dispatches
- [x] T002 [US1] Add native payload and failing requested-setting and identity tests in tests/test_codex.py (FR-001, FR-002, FR-003).
- [x] T003 [US1] Normalize supported native and legacy dispatches in cli/wuwei/hook.py.

## US2: Unsupported dispatches
- [x] T004 [US2] Add failing missing-role and malformed-response consumer tests in tests/test_codex.py (FR-004, FR-005).
- [x] T005 [US2] Record precise diagnostics without running seats in cli/wuwei/hook.py.

## Validation
- [x] T006 Update skills/wuwei-run/SKILL.md, docs/site/concepts/codex.md and vendor copies (FR-006).
- [x] T007 Run focused tests, checks and main/head route differential; record evidence and runtime budget.

Dependencies: T001 precedes all tests. T002 and T004 precede runtime edits. T003 and T005 precede T006 and T007.
Parallel work: none; one small adapter and its consumer change together.
Implementation strategy: deliver the two supported surfaces and diagnostics as one tested patch.

## Combined native review fix
- [x] T008 Add consumer red regressions for credential/canary persistence, clipping boundaries and cross-session native identities in tests/test_codex.py (FR-007, FR-008).
- [x] T009 Redact shared seat metadata before persistence and clipping in cli/wuwei/hook.py; scope board.py stop matching by session, retaining sessionless legacy history and raw native paths. Update both vendor copies.
- [x] T010 Run Codex, models, hook and board-consumer focused tests and the route differential at the pushed fix head; update PR and handoff evidence.

## Observed native hook spelling
- [x] T011 Reproduce the captured collaborationspawn_agent schema through normalization and the seat consumer, including unsupported roles, malformed results and an unsupported sibling tool; accept both proven spawn spellings in the existing dispatch condition and vendor copy. Red: 22 failed, 49 passed. Green: 71 passed.
