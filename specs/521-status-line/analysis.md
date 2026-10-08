## Specification Analysis Report

Artifacts: `spec.md`, `plan.md`, `tasks.md` against `.specify/memory/constitution.md` 1.4.0 and
`docs/specs/2026-09-24-wuwei-design.md`.

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| C1 | Constitution | MEDIUM (resolved) | spec.md Assumptions; plan.md Docs | The design spec (5.2, 5.3, 5.8.2, 5.9) lists the old line contents; the constitution says the design spec wins and a conflict is raised. | Raised in spec Assumptions: issue #521 is the owner's change; the feature amends those sentences citing #521, as earlier features did (T016). |
| A1 | Ambiguity | MEDIUM (resolved) | spec.md US4.2, FR-004 | "parts" and "tokens" named the same unit of truncation. | spec US4.2 now says tokens, matching FR-004 and plan.md. |
| A2 | Ambiguity | MEDIUM (resolved) | spec.md FR-001, Assumptions | The middle dot is the CLI's first non-ASCII output; a stream that cannot encode it would raise. | Assumption added: `__main__._call` turns the raise into exit 2 with the reason, so it fails closed; Python 3.11 coerces the POSIX locale to UTF-8. |
| U1 | Underspecification | LOW | spec.md US1.2 | The issue's example (`planned 3/1 · gate 1/1 · ...`) is illustrative; the exact line depends on the fixture phases. | T006 pins one exact string for its fixture. |
| I1 | Inconsistency | LOW | tasks.md T008, T013 | After T008 the existing tests that assert moved parts on the line fail until T013 and T014. | Expected in test-first order; the builder runs the listed files after T014. |
| P1 | Performance | LOW | plan.md snapshot | `snapshot` now reads `plugin.json` (`integrity.version`) and stats `plan.md` on every line refresh. | Two small reads against a 200 ms wall budget; T015 keeps the latency test. |
| S1 | Scope | LOW | spec.md Assumptions | Watch, listen and heartbeat health leave the line. | Their failures are pages or nudges already counted on the line; `status` and `nudges` name them. Recorded as an assumption. |

**Coverage Summary Table:**

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 three groups, nothing else | Yes | T006, T008 | |
| FR-002 the one thing to do now | Yes | T005, T007, T008 | restart, gate waiting, no plan yet, decision |
| FR-003 seats by role, no items or times | Yes | T005, T006, T008 | |
| FR-004 truncation | Yes | T009, T010 | |
| FR-005 `--width`, fast path kept | Yes | T009, T010, T015 | |
| FR-006 full status | Yes | T011, T012, T013, T014 | |
| FR-007 restart text | Yes | T001, T002 | doctor row included |
| FR-008 snapshot keys | Yes | T003, T004 | |
| FR-009 docs and design spec | Yes | T015, T016 | |
| SC-001 | Yes | T005 | |
| SC-002 | Yes | T015 | |
| SC-003 no refusal, event or state key | Yes | plan.md Constitution Check | nothing is added, so no task |

**Constitution Alignment Issues:** none open. Stdlib only; exits unchanged (full status fails
closed with exit 2); one shared `_groups` feeds the line and the full status; every behaviour
has a test task before its implementation task; no guard or refusal touched (#530); the
planner's path is unchanged (`wuwei next` already returns running items and times, #551).

**Unmapped Tasks:** none. T013 (moving existing asserts) maps to FR-006 and T017 (suite and
hygiene) to FR-009.

**Metrics:**

- Total Requirements: 9 functional, 3 success criteria
- Total Tasks: 17
- Coverage: 100 percent (every FR and SC has a task)
- Ambiguity Count: 2 (both resolved)
- Duplication Count: 0
- Critical Issues Count: 0 (no CRITICAL or HIGH findings)

### Next Actions

No CRITICAL or HIGH findings. Proceed to `speckit-checklist` and `speckit-implement`.
