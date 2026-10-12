# Requirements Quality Checklist: window budget per runtime (#845)

**Purpose**: check that the requirements in `spec.md` are complete, clear, consistent and
testable before `implement`.
**Created**: 2026-10-12
**Feature**: `specs/845-window-budget/spec.md`

## Completeness

- [x] CHK001 Does each acceptance line of the issue map to a requirement? (`next` never offers a launch the window cannot carry: FR-006, FR-007; CAP per runtime and routing: FR-005, FR-008) [Completeness, Spec FR-005 to FR-008]
- [x] CHK002 Is the source of each runtime's reading named, with evidence? [Completeness, research.md]
- [x] CHK003 Is the fallback when no reading exists specified (tokens against a per-window budget)? [Completeness, Spec FR-003]
- [x] CHK004 Are the config keys, their defaults and the retired key named? [Completeness, Spec FR-001, FR-012]
- [x] CHK005 Is the behaviour for running seats stated (never stopped or resumed)? [Completeness, Spec FR-013]
- [x] CHK006 Are launches that are not seats excluded from window holds? [Completeness, Spec FR-006, Edge Cases]
- [x] CHK007 Is what happens after the reset specified (the loop resumes without the owner)? [Completeness, Spec US1 scenario 3, FR-007]

## Clarity

- [x] CHK008 Is "room" defined with a formula, including rounding and the floor at 0? [Clarity, Spec FR-003]
- [x] CHK009 Is "until" defined for both a reading and an estimate, and for several spent windows? [Clarity, Spec FR-004]
- [x] CHK010 Is "when the role allows it" made concrete (the policy row's `alternate`, builder starts only)? [Clarity, Spec FR-008]
- [x] CHK011 Is the window length mapping for Codex readings stated (300 and 10080 minutes)? [Clarity, Spec US3 scenario 3, Edge Cases]
- [x] CHK012 Is the timed wait's shape specified (state, `until`, background command, then line)? [Clarity, Spec FR-007]

## Consistency

- [x] CHK013 Do the day CAP's meaning and the state invariant (at least 1) stay as the clarification says, with no requirement that drops CAP to 0? [Consistency, Spec Clarifications, FR-005]
- [x] CHK014 Does the reading rule agree across FR-003, US3 scenario 4 and the research decisions (used is the larger of counted and percent of budget)? [Consistency]
- [x] CHK015 Do routing rules agree between US2 scenarios 1 to 5 and FR-008, FR-009? [Consistency]

## Measurability

- [x] CHK016 Can each success criterion be checked by a test or a count (SC-001 to SC-005)? [Measurability]
- [x] CHK017 Do the acceptance scenarios give concrete numbers (budget, counted tokens, per-seat cost) a test can reuse? [Measurability, Spec US1, US3]

## Edge cases and failure paths

- [x] CHK018 Are a damaged day log and a damaged readings cache specified, and do they never block a launch? [Edge Case, Spec Edge Cases]
- [x] CHK019 Is unmeasured per-seat cost specified? [Edge Case]
- [x] CHK020 Is a budget below one seat specified? [Edge Case]
- [x] CHK021 Are malformed status line stdin and a missing Codex rollout specified as no reading, no error? [Edge Case, Spec FR-010, FR-011]
- [x] CHK022 Are pre-feature `seat.usage` rows without a runtime assigned? [Edge Case]

## Non-functional

- [x] CHK023 Is the hook path kept free of window computation? [Performance, Plan CAP per runtime, analysis H1]
- [x] CHK024 Is the status line output required to stay byte-identical? [Compatibility, Spec SC-005]
- [x] CHK025 Is the Codex thread id treated as untrusted before it names a file? [Security, Plan Readings cache]

## Dependencies and assumptions

- [x] CHK026 Are the assumptions about unmeasured Claude gate tokens and Codex tokens recorded with their effect? [Assumption]
- [x] CHK027 Is the design spec amendment named, and the 15.8 governor's status stated? [Assumption]
- [x] CHK028 Is deferred work listed so it is not silent scope? [Traceability, Spec Deferred]
