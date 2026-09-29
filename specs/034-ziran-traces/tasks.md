# Tasks: ZIRAN live traces

## Setup

- [X] T001 Read existing contracts and create spec.md and plan.md in specs/034-ziran-traces/.

## US1: Released scanner contract

- [X] T002 [US1] Write and run failing version, audit command and JSON tests in tests/test_ziran.py; update tests/fixtures/scanner/audit.json and tests/test_dispatch.py.
- [X] T003 [US1] Implement released audit and local gate in adapters/scanner/ziran.py and cli/wuwei/scanner.py.

## US2: Trace fidelity

- [X] T004 [US2] Write and run conformance, redaction grouping and reservation binding tests in tests/test_traces.py.
- [X] T005 [US2] Preserve grouping and bind reservations in cli/wuwei/guards/traces.py, reusing transcript lookup from cli/wuwei/guards/agent_launch.py via cli/wuwei/brief.py.

## US3: Sweep response

- [X] T006 [US3] Write and run trace adapter and sweep acceptance/error tests in tests/test_ziran.py and tests/test_watch.py with tests/fixtures/scanner/trace_analysis.json.
- [X] T007 [US3] Implement traces in adapters/scanner/ziran.py and response in cli/wuwei/scanner.py and cli/wuwei/watch.py, reserving producers in cli/wuwei/state.py and cli/wuwei/commands/event.py.

## Verification

- [X] T008 Update docs/site/adapters.md and docs/site/configuration.md for released contracts and limitations.
- [X] T009 Run full pytest, review scope, privacy, producer protections and diff hygiene; complete specs/034-ziran-traces/tasks.md.

## Adversarial review fixes

- [X] T010 F1: Reproduce filtering in scanner fakes, retain all audit findings at severity low, and validate exit against finding presence while preserving local trust rules and notes.
- [X] T011 F2: Reproduce shared planner payloads, isolate subagent identities, bind their own transcripts, and verify sweep parking and redaction.
- [X] T012 F3: Reproduce malformed and unreadable transcripts, then make reservation lookup best-effort after recording the span.
- [X] T013 Run the specified full pytest suite after all review fixes and check diff hygiene.

## Dependencies and Execution

US1 then US2 then US3. Within each story tests run and fail before implementation.
The acceptance sweep is the minimum complete delivery. Contract and recorder tests can
be read independently; implementation runs sequentially to avoid shared-file conflicts.

## Results

- Final suite after F1, F2 and F3 fixes: 4843 passed, 3 skipped in 64.83s (0:01:04).
- Each review fix was preceded by failing regression tests. Filtering fakes exposed
  lost trust findings and notes; shared planner payloads exposed merged identities and
  missed parking; malformed transcripts exposed spurious hook errors.
- Three host performance checks skipped under load; no correctness tests failed.
- Independent review and one delta review cleared the session identity and oversized
  numeric score regressions. Both regressions were observed failing before fixes.
- Diff whitespace, absolute machine paths, em-dashes and emoji checks passed.
- Extension hooks skipped as requested. Changes remain uncommitted in this worktree.
