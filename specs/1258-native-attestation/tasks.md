# Tasks: Protected native seat attestation

## Setup

- [x] T001 Read canonical item, design, constitution, observed sanitized records and existing consumers.
- [x] T002 Specify acceptance, pre-mortem, research, data model and producer contract.

## User Story 1: Native proof and protection

- [x] T003 Add failing proof/root/settings tests in tests/test_native_evidence.py and sanitized fixtures (FR-001 through FR-005, FR-007, FR-008).
- [x] T004 Implement shared native proof and root protection in cli/wuwei/hook.py, ws.py and guards.py; preserve legacy behavior.

## User Story 2: Report lifecycle

- [x] T005 Add failing native latest-report, notification, collision, redaction and race consumer tests (FR-006).
- [x] T006 Reuse current report store and map canonical identity only after proof in cli/wuwei/hook.py.

## Cross-cutting verification

- [x] T007 Amend the approved 4,000 cap, document accurate native support, regenerate agents and vendor copies.
- [x] T008 Run focused/full tests, route differential, generated path/wrapper probes and isolated mutants; retain commands and counts.
- [x] T009 Analyze completed artifacts with no open critical/high finding and complete the validation checklist.

Dependencies: T001 and T002 precede tests; each test runs red before its implementation. T007 follows the behavior. T008 and T009 follow the final source. Required independent gates, CI and owner review occur at the draft head after builder handoff.

## Combined review fix round

- [x] T010 Add the minimized genuine fork-all inherited metadata/report/model regression, run red, and move extra-metadata rejection after the fork boundary; preserve root, schema and ordinal checks.
- [ ] T011 Replay the genuine producer through the pure reader, repeat focused/full validation and route/probe evidence, then hand the serialized mutant slot to the delta gates.
