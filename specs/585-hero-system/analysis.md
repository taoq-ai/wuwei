# Specification Analysis Report: 585-hero-system

Artifacts: spec.md, plan.md, tasks.md, against issue #585 (storyboard and the owner's
reference-image comment), the orchestrator notes, the prototype `hero-system-proto.svg`,
the four reference images and the constitution. Timing tables were checked in a scratch
run: all three lanes are busy from k 0.22 to 0.74, and at `STILL_K` 0.55 (13:55) rate limits
and login fix hold at the gates, docs page builds, D-3 is open and two items wait.

## Findings

| ID | Category | Severity | Location | Summary | Resolution |
|----|----------|----------|----------|---------|------------|
| H1 | Owner intent | HIGH | issue storyboard vs owner comment | The storyboard asks for five panels with many lines; the later comment asks for a left-to-right agentic flow, about twelve labels, "not too complex". Building the storyboard as written would fail the review. | Resolved: the comment refines the storyboard; panels become five stages in the reader's words, the lane caption and band day line are dropped, the day loop is the return arrow; spec Assumptions, FR-001, SC-003. |
| H2 | Consistency | HIGH | prototype timings vs the reduced-motion frame | With the prototype's timings no k shows lane 1 at the gates, lane 2 in the fix round, lane 3 building and D-3 open together, so the required mid-day frame did not exist. | Resolved: new `ITEMS`, `FIX` and `DECISIONS` tables; the frame exists over k 0.52 to 0.58; `STILL_K` 0.55; T010 computes the still frame from the tables. |
| H3 | Correctness | HIGH | prototype counter and parked line | "shipped today: 0, 2, 3" ran ahead of the merges, and "parked: 1" named no parked item; a fifth queue item stayed queued after a lane freed, breaking "a lane frees, the next ranked item starts". | Resolved: shipped steps with each merge from `PRS`, cache keys starts when docs page leaves, "carried to tomorrow: 2" derived; T008, T009; spec Assumptions. |
| H4 | Product truth (#530) | HIGH | storyboard "guards: every call checked, 1 refused" | Under the default posture a guard warns or raises a card, never refuses. | Resolved: "1 caught", as #569 decided; spec Assumptions. |
| H5 | Owner intent | HIGH | storyboard caption "a seat never asks you" | Contradicts the owner's guidance loop "a seat asks through a decision record". | Resolved: caption dropped; FR-006 draws the two loops. |
| M1 | Coverage | MEDIUM | FR-006 to FR-008 | The guidance loops, the lead and the close had no timed test. | Resolved: ids `ask-loop-lit`, `answer-loop-lit`, `lead`, `day-loop-lit` in plan.md; T009 checks each by `_value_at`. |
| M2 | Testability | MEDIUM | plan.md drawing | Tests reading an element's timing need a stable spot, and the still copy would duplicate ids. | Resolved: the timing `<animate>` is each id'd element's first child; ids on static and live copies only; no SMIL outside `live`. |
| M3 | Fidelity | MEDIUM | card lines | Storyboard texts ("D-1 Routine · taken under mandate", about 215 px at 12 px) do not fit a 170 px right panel. | Resolved: shortened lines; spec Assumptions; T015 checks they sit inside the panel. |
| M4 | Budget | MEDIUM | FR-014 | More shapes (nine gate dots, five items, loops) push the SVG size and the 320-line cap. | Accepted: the #569 SVG is 23 KB; the plan deletes the ticker, track, fix and exit lanes and six indicators; T006 pins both budgets. |
| L1 | Drawing | LOW | plan.md `PLACES['off']` | An item fading in under the queue panel would draw over the queue pills. | Resolved: 'off' is the lanes panel's left edge. |
| L2 | Fidelity | LOW | storyboard "17:50 close" | A close at k 0.98 shows for a third of a second. | Accepted: stamp derived from `clock(CLOSE)` at 0.92 (17:15); spec Assumptions. |
| L3 | Scope | LOW | README Acknowledgements, NOTICE | The Simple Icons credit names glyphs the hero no longer uses; the notes limit README edits to the alt. | Deferred in spec.md to #561 or a follow-up. |
| L4 | Style | LOW | reference image 1 near-black ground | Copying it would change `PAL`, which the notes say to reuse. | Accepted: `PAL` unchanged; one accent kept. |

No CRITICAL findings. No HIGH finding is left open.

## Coverage

| Requirement | Tasks |
|-------------|-------|
| FR-001 stages, icons, names | T001, T003, T012 |
| FR-002 queue, waits, gate card | T004, T005, T008, T012 |
| FR-003 lanes, build glyph, gate dots, fix loop | T005, T007, T012 |
| FR-004 PR stack, sweep, shipped, carried | T005, T009, T012 |
| FR-005 cards, phone, asked | T005, T009, T012 |
| FR-006 guidance loops | T005, T009, T012 |
| FR-007 return arrow, close line | T005, T009, T012 |
| FR-008 band indicators | T004, T009, T012 |
| FR-009 forward only | T007, T012 |
| FR-010 derived labels | T008, T009 |
| FR-011 reduced motion | T006, T010 |
| FR-012 themes, palette, no brands | T006, T014 |
| FR-013 alt sentence | T002, T013 |
| FR-014 budgets | T006 |
| US2 first frame | T004, T015 |
| SC-002 rendered check | T015 |

## Constitution

- I stdlib: generator imports unchanged. Pass.
- IV test first: T001 to T010 written and run red (T011) before T012. Pass.
- V ponytail: shared helpers reused, `holds` extended with a lane filter instead of a
  copy; derived labels computed once. Pass.
- No runtime, guard or rule change: no 9.2 invariant row, `tests/test_invariants.py`
  untouched.
