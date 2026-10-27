# Specification analysis

Analyzed the specification, plan, tasks, data model, producer contract, checklists and governing constitution on 2026-10-27. This records a read-only consistency review after the combined correction.

## Findings

No open findings remain within the builder's artifact analysis. The independent initial findings are recorded with their verified corrections below. Delta gate rulings remain separate.

| ID | Severity | Source | Status | Resolution |
| --- | --- | --- | --- | --- |
| N1 | MEDIUM | cli/wuwei/hook.py:178 at b5fb247c | RESOLVED | Allow inherited parent metadata before the boundary while rejecting own extra metadata; regression ran red/green and genuine producer replay passes. |
| N2 | HIGH | cli/wuwei/hook.py:233 at b5fb247c | RESOLVED | Stable sensitive identity keys at launch and verified stop prevent disclosure and masking collisions; two leak regressions and isolated start/stop/notification consumers pass. |

## Coverage

| Requirement | Task | Validation |
| --- | --- | --- |
| FR-001 first metadata and own rows | T003, T004, T010 | inherited metadata/report/model, ordinal and fork-boundary cases |
| FR-002 correlated parent launch | T003, T004 | parent, role, call, path, UUID and duplicate-pair negatives |
| FR-003 latest own final and completion | T003, T004 | earlier/later final and callback/task_complete cases |
| FR-004 protected account root | T003, T004 | account variables, native-parent root and symlink escape |
| FR-005 equivalent write protection | T003, T004, T011 | writer/edit/Windows matrix and final generated path probe |
| FR-006 existing report lifecycle and privacy | T005, T006, T012 | report versions, notifications, redaction, distinct sensitive paths and concurrent claims |
| FR-007 child recorded settings | T003, T004, T010 | own post-fork context and inherited/future/malformed settings |
| FR-008 compatibility and owner-answer exclusion | T003, T004, T007, T011 | final full suite, ordinary-owner negative, budget and parity |

## Constitution review

The implementation uses the standard library, shared transcript reader and existing report store. Protection extends to the newly accepted record root. Tests ran before changed behavior. No shell parser, configuration key, owner-answer bridge or background framework was added. The approved cap is 4,000, measured runtime 3,877 and item growth 79 against 111. Twelve completed tasks cover both user stories, the two initial review findings and cross-cutting evidence.

Final full validation at ea78a08d passed 4,356 tests with 7 skips, with actual exit 0 persisted. Main/head 288-route runs pass with ten reason-only changes, 32 generated path commands have zero holes, and eight isolated mutants fail behaviorally. Actual producer replay passes without invoking hooks or attestations. Independent delta gates, CI, owner review and changed-plugin trust remain explicit in validation.md.
