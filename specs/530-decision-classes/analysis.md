# Specification Analysis Report: 530-decision-classes

Artifacts read: `spec.md`, `plan.md`, `tasks.md`, `.specify/memory/constitution.md`, design
5.4, 5.8, 5.8.1 and 9. The base has no `tests/test_invariants.py` (task T026 is conditional).

| ID | Category | Severity | Location | Summary | Resolution |
|----|----------|----------|----------|---------|------------|
| A1 | Inconsistency | HIGH | spec FR-004; design 5.8.1 Ceilings | Under autonomous a Consequential record (one-way, a `message`, `scope-cut` or `re-plan` class) is decided under mandate, while 5.8.1 says these stay at L0 or L1. The design spec wins over the plan, so the conflict must be resolved in the design, not left silent. | Resolved: plan and T025 add one dated sentence to 5.8.1 Ceilings: under autonomous the ceilings bind the action through its floor (merge policy, publish grants, outbound tiers), not the record. The item scope (part A, item 3) is the owner's decision. |
| A2 | Inconsistency | HIGH | item Scope 3 vs Acceptance 2 | Scope says "under supervised, Consequential and Exploratory also ask" (implying Routine is decided), Acceptance says "under supervised, the same decisions raise cards as today". | Resolved: supervised keeps the legacy `route()` unchanged (spec Assumptions, FR-004, US3); both statements hold. |
| A3 | Coverage | HIGH | plan "Existing tests" | The default flips to autonomous, so existing owner-card tests that route one-way records through `decision route` will print `mandate`. Without a rule the builder could rewrite assertions. | Resolved: T027 names the one allowed change (set `[autonomy] mode = "supervised"` in that test's workspace) and forbids other assertion edits; SC-002 states it. |
| A4 | Underspecification | MEDIUM | spec FR-002 | "Clearly above" and "evidence is thin" had no number. | Resolved: the 5.8.1 margin with its documented 0.2 default, Confidence `low` as thin evidence, tie as margin 0 or less (Assumptions). |
| A5 | Security | MEDIUM | FR-002 Routine by definition | A seat could label a Strategic decision `Class: retry` or `approach` to have it taken under mandate. The floors still hold at the action (merge, publish, outward, records), and Consequential is mandate anyway; the only gain is skipping the Strategic card. | Accepted: the owner asked for these classes to be two-way by definition; the report lists every mandate decision with its class and reversal command, and gates review records. Noted for the retro. |
| A6 | Inconsistency | MEDIUM | `closing.py:188` | A one-way mandate record has `route() == 'owner'` and no owner answer, so close would list it as pending. | Resolved: FR-012, T020, T021. |
| A7 | Underspecification | LOW | US1.4 digest | A Routine-by-definition record written `one-way` is mandate-decided but not in the digest (the digest lists two-way doors). It still appears in the report. | Accepted; fixtures use two-way records; the digest header stays truthful. |
| A8 | Coverage | LOW | FR-015 | "No new refusal" has no dedicated task. | Covered by T007 (only a message changes) and by T026 when the invariant test exists. |
| A9 | Terminology | LOW | spec, plan | The record already has a `Class:` field (5.8.1 cruise classes); the CISR class is a different value. | Resolved: the CISR value is named `cisr` in code, state and events, and "class" in the report heading with the four CISR names; `Class:` keeps its meaning. |
| A10 | Ambiguity | LOW | FR-011 counts | Whether morning-gate and grant cards count as cards. | Resolved in Assumptions: a card is a `decision_routes` entry, whatever its producer. |

## Coverage summary

| Requirement | Tasks |
|-------------|-------|
| FR-001 | T001, T002 |
| FR-002 | T005, T006 |
| FR-003 | T003, T004 |
| FR-004 | T009 to T013 |
| FR-005 | T009, T013 |
| FR-006 | T010, T011, T013 |
| FR-007 | T014, T015 |
| FR-008 | T014, T015 |
| FR-009 | T007, T008 |
| FR-010 | T016, T017 |
| FR-011 | T018, T019 |
| FR-012 | T020, T021 |
| FR-013 | T022, T023 |
| FR-014 | T024 |
| FR-015 | T007, T026, T027 |

Every behaviour has a test task before its implementation task. No unmapped task.

## Constitution alignment

No violation. One function per behaviour (`cisr`, `margin` shared with `why`), CLI-only
writers for the trusted ledger, exits unchanged, stdlib only, no new refusal under observe
or guarded.

## Metrics

- Functional requirements: 15; tasks: 27; coverage 100 percent.
- CRITICAL: 0. HIGH: 3, all resolved in the artifacts. MEDIUM: 3 (2 resolved, 1 accepted).
  LOW: 4.

## Next action

Proceed to checklist and implement.
