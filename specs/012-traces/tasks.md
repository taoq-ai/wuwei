# Tasks: Tool-call traces

Input: spec.md, plan.md, contracts/otel.md. All behavior is implemented test first.

## Setup

- [X] T001 Inspect existing hook/state contracts and ZIRAN ingestion; write specs/012-traces/spec.md and plan.md.

## Foundation

- [X] T002 Add failing locked JSONL append, concurrent writer and short-write tests in tests/test_traces.py.
- [X] T003 Extract shared JSONL append logic in cli/wuwei/state.py; pass T002 and existing event tests.

## US1: Record tool calls

- [X] T004 [US1] Add failing envelope/order/session/role/timing/validation tests in tests/test_traces.py.
- [X] T005 [US1] Implement cli/wuwei/guards/traces.py and update discovery expectation in tests/test_hooks.py.

## US2: Redact before writing

- [X] T006 [US2] Add failing nested fields, strings, wrappers and personal-data tests in tests/test_traces.py.
- [X] T007 [US2] Implement cli/wuwei/redact.py and integrate in cli/wuwei/guards/traces.py.

## US3: Report without blocking

- [X] T008 [US3] Add failing 0/1/2 hook tables, malformed input and storage-failure tests in tests/test_traces.py and tests/test_hooks.py.
- [X] T009 [US3] Implement recorder-local safe diagnostics/events in cli/wuwei/guards/traces.py; preserve shared hook refusals and isolate replay workspaces in tests/test_hooks.py.

## Validation

- [X] T010 Review final diff against specs/012-traces/contracts/otel.md; run full pytest and scan changed files for hygiene.

## Dependencies and execution

T001 -> T002 -> T003 -> T004 -> T005 -> T006 -> T007 -> T008 -> T009 -> T010.
US1 is the recording MVP; US2 is required before use with real secrets; US3 completes
operational handling. Each test task must fail for the intended missing behavior before
its implementation task starts. No parallel work is useful in this small shared-file
change. Full-suite and independent text hygiene checks can run together after T009.

## Initial test-first evidence (superseded where corrected below)

- Shared append: 2 expected failures, then 65 passing trace/state tests.
- Span recording: 20 expected registration failures, then 22 passing trace tests.
- Redaction: 29 expected leakage failures, then 51 passing trace tests.
- Nonblocking reporting: 10 expected exit failures, then 266 passing trace/hook tests.
- Review fixes: 15 reproduced failures for command privacy, input diagnostics, duration
  bounds and actual partial writes; then 344 passing trace/state/hook tests.
- Deferred recorder imports after the full suite exposed hook latency overhead; the
  focused benchmark passed at 29.83 ms CPU p95 without relaxing its 50 ms threshold.
- Delta review reproduced one fractional-duration rounding case; the failing regression
  now passes with a final integer start-time range check.
- Final full suite: 1026 passed in 11.94s; hook CPU p95 34.86 ms, wall p95
  44.40 ms. Changed-file whitespace, machine-path, em-dash and emoji scans passed.

## Adversarial review fixes

- [X] T011 [F1] Reproduce oversized-input latency and truncation failures; bound string scans and all regex quantifiers. Test 5 MB Write and 100 KB hex under 50 ms CPU each.
- [X] T012 [F2] Reproduce each privacy case as a table row; redact sensitive files, field names, token prefixes, national phones and shell bodies. Document the M5 redactor limit.
- [X] T013 [F3] Restore dispatcher refusal semantics; move recorder failure logging into the recorder. Test policy exits and recorder failures independently.
- [X] T014 [F4] Check workspace scope before trace validation; quiet return outside workspace. Test external worktree override and document the shared scope-helper limit.
- [X] T015 [F5] Reproduce unterminated JSONL concatenation; insert newline under the writer lock.
- [X] T016 [F6] Parametrize the 60-run latency benchmark over PreToolUse and PostToolUse with the same p95 CPU threshold.
- [X] T017 [F7] Remove invented parent/role input handling and impossible clock checks; simplify timestamp arithmetic while retaining duration validation.
- [X] T018 Run the requested full pytest command and inspect the final diff.

Review test-first evidence: F1 had 4 failures; F2 had 35 failures; F3 had 25 failures
plus 2 interrupt/exit failures; F1/F2 interaction had 2 truncated-body failures; F4/F5 had 4 failures; F7 had 3 failures. All were
observed before their corresponding implementation changes.

Final review validation: 1073 passed in 15.69s. PreToolUse CPU p95 30.09 ms;
PostToolUse CPU p95 40.33 ms. Both oversized-argument CPU tests passed. Final diff
whitespace and changed-file path/style scans passed. No commits were made.
