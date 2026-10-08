# Specification Analysis Report: 569-hero-simple

Artifacts: spec.md, plan.md, tasks.md, against the issue (redesign and forward-only
correction comments), the orchestrator notes, the corrected reference prototype and the
constitution. This pass replaces the second-round report; its findings A1 to A10 are
carried below where they still apply.

## Findings

| ID | Category | Severity | Location | Summary | Resolution |
|----|----------|----------|----------|---------|------------|
| B1 | Owner intent | HIGH | second-round spec US1, plan `ITEMS` (login fix `(.6, 1)`) | The fix round was a step back from Review to Build, which the owner's correction rules out: nothing ever moves backwards. | Resolved: FR-008 and acceptance 2; login fix now runs Review, patch, delta check, Merge on a siding; T005 pins non-decreasing x in the tables and in every `animateMotion`. |
| B2 | Drawing | HIGH | corrected prototype, siding at y 340 off the middle lane | The siding cuts into the bottom lane, so login fix on the siding overlaps docs page at Review from about k 0.60 to 0.66. | Resolved: login fix moves to the bottom lane and the fix lane sits under all three lanes; a scratch sampling of the plan tables (k 0 to 1 in 0.001 steps, eased bends) finds no pill overlap. Recorded under Assumptions. |
| B3 | Coverage | HIGH | issue redesign: "A station's pill lights while an item is under it" | The second-round artifacts had no requirement, drawing or test for station highlights. | Resolved: FR-009, acceptance 8, `holds()` and `lit-<station>` in plan.md, T006. |
| B4 | Drawing | MEDIUM | prototype login fix `animateTransform` | The pill moves on straight diagonals (653,0 to 700,46) while the drawn siding curves to 770, so it would not follow the branch the owner asked to read clearly. | Resolved: `walk` samples the bend with the same eased curve `bend` draws (cubic with thirds control points equals x linear, y eased by 3t^2 - 2t^3); T011 renders a frame mid-bend. |
| B5 | Drawing | MEDIUM | prototype label at y 412; Build label at y 178 | The fix-lane label sits on the panel's top edge (410) and the Build label's glyphs overlap the phone's lower edge (174). | Resolved: owner row ends at 160, labels at 172, siding label between the track (408) and the panel (436); T011 checks. |
| B6 | Consistency | MEDIUM | issue redesign reduced-motion frame "Build (amber)" | A still frame with the amber item at Build contradicts forward only. | Resolved: the still frame puts login fix on the fix lane; Assumptions. |
| A1 | Constitution IV | HIGH | tasks.md ordering | Tests ordered after the generator rewrite could pass the first time they ran. | Resolved: T001 to T006 come first and T007 runs them red before T008. |
| A2 | Correctness | HIGH | prototype ticker stamps | Hand-typed stamps are out of day order (10:40 after 11:03) and disagree with the clock. | Resolved: FR-004 derives each stamp from the clock (10:15, 12:15, 13:00, 13:55, 15:00, 15:20, 17:25, checked); T003 pins ascending stamps. |
| A3 | Product truth (#530) | HIGH | issue and prototype "guards: 1 refused", "(publish floor)" | Under the default guarded posture a force push is a warning or a card, not a refusal (#555), and the design spec has no publish floor (floors: records and owner-only actions). | Resolved: "guards: 1 caught" and a posture-neutral ticker line; Assumptions. |
| A4 | Correctness | LOW | plan.md `clock` | Flooring a float minute count can drop a whole value one step. | Resolved: minutes rounded to 6 places before flooring; hour texts built from the hour. |
| A5 | Correctness | MEDIUM | plan.md `blink` | A span ending at 1 plus the 0.01 ramp would push `keyTimes` past 1. | Resolved: spans end by 0.98 or exactly at 1; T003 checks every `keyTimes`. |
| A6 | Coverage | MEDIUM | plan.md groups | An animated element outside `live` keeps moving under reduced motion. | Resolved: every animated element in `live`, its mid-day state in `still`; T004. |
| A7 | Consistency | LOW | prototype phone line | The phone shows D-2 while the ticker says D-3 was answered from the phone. | Resolved: the phone names D-3. |
| A8 | Drawing | LOW | plan.md belt | A clip-path on the moving group would move with it. | Resolved: clip on an outer group, `.belt` inside. |
| A9 | Scope | LOW | README Acknowledgements, NOTICE | The Simple Icons credit outlives the glyphs; the notes limit README edits to the alt. | Deferred in spec.md. |
| A10 | Fidelity | LOW | spec FR-002 vs Assumptions | Departures from the prototype (lane order, one guard pulse, warm cards dot, item fade on landing, derived stamps, moved labels) could read as reinventing. | Accepted: each is listed under Assumptions with its reason; composition and timing are the prototype's. |
| B7 | Fidelity | LOW | issue "a label switches on as the item arrives" vs prototype timing | Prototype labels show while the leading item rides into the station, not after it arrives. | Accepted: the owner asked to keep the prototype's timing; the station highlight (FR-009) marks the arrival. |
| C1 | Coverage | HIGH | design check (notes, issue comment): wait at Plan, park on an exit lane | FR-010 and T013/T014 existed but no acceptance scenario or coverage row pinned them, so the review could not check them against the spec. | Resolved: acceptance 9 in spec.md; coverage row below; T013 names it. |
| C2 | Owner intent | MEDIUM | notes "a fourth item that waits ... a fifth that is parked" | Two new items need two free seats under CAP 3; the day frees only one (the parked item's) before late afternoon. | Resolved: four items; csv export is parked, login fix is the waiter and takes its lane. Matches the owner's own design-check wording (one item held, one item diverted). Recorded under Assumptions. |
| C3 | Consistency | LOW | Shipped line "yesterday: 4 shipped, 1 carried" vs today's parked item | The line counts yesterday while the parked item is today's carry. | Accepted: owner's text kept verbatim; Assumptions. |

## Coverage

| Requirement or acceptance | Tasks |
|---------------------------|-------|
| AC1 track, stations, items, fix lane, Shipped, owner touchpoints, panel, clock | T001, T005, T008, T011 |
| AC2 forward only (FR-008) | T005, T008, T011 |
| AC3 files match the generator, themes differ only in colour | T010 |
| AC4 reduced motion (FR-005) | T004, T008 |
| AC5 size, line budget, no logos or brands | T001 |
| AC6 alt text (FR-006) | T002, T009 |
| AC7 well-formed SMIL timing | T003 |
| AC8 station highlights (FR-009) | T006, T008 |
| FR-001, FR-002 one generator, prototype composition | T008, T010, T011 |
| FR-003, FR-004 tables and derived stamps | T003, T008 |
| FR-007 README and index change only in alt | T009, review of the diff |
| AC9, FR-010 wait at Plan, exit lane, no overlaps, no "treadmill" | T013, T014, T011 |

No requirement without a task; no task without a requirement.

## Constitution alignment

Stdlib only (I), one helper per animation shape (III), tests first (IV), ponytail: tables
plus small helpers, no new file (V). No runtime code, guard, command or skill changes, so
#530 and #551 add nothing beyond A3. tests/test_invariants.py is absent on this base and no
product rule is added, so no invariant row.

## Metrics

- Requirements: 10 functional, 9 acceptance; coverage 100 percent.
- Findings: CRITICAL 0; HIGH 7 (all resolved); MEDIUM 6 (all resolved); LOW 7 (3
  resolved, 1 deferred, 3 accepted).

## Next action

Proceed to the checklist and implement.
