# Tasks: Generic writer allowlists

## Setup

- [X] T001 Read design, constitution, writer callers and trusted readers; write specs/114-state-allowlist/spec.md and plan.md.

## US1: Producer-owned state

Independent check: allowed settings and notes work; all other writes refuse without mutation.

- [X] T002 [US1] Add failing state allowlist, callback, approval-freeze and producer tests in tests/test_state_allowlist.py.
- [X] T003 [US1] Replace RESERVED in cli/wuwei/state.py with allowlisted paths and locked callback protection; route transition and cli/wuwei/brief.py through the internal writer.
- [X] T004 [US1] Migrate trusted fixture setup in tests/test_state.py and affected tests/test_*.py to producer writes; retain lifecycle and validation coverage.

## US2: Producer-owned events

Independent check: note appends, trusted and unknown kinds refuse with producer guidance.

- [X] T005 [US2] Add failing event allowlist tests in tests/test_state_allowlist.py.
- [X] T006 [US2] Replace prefix and named denial lists in cli/wuwei/commands/event.py with the free-kind allowlist; update old free-kind expectations in tests/test_state.py and tests/test_signal_status.py.

## US3: Reader coverage

Independent check: source-derived reader inventory cannot be written by generic commands.

- [X] T007 [US3] Add and run failing source-derived state key and event kind enumeration in tests/test_state_allowlist.py before the runtime changes.
- [X] T008 [US3] Verify the inventory passes after T003 and T006 and catches a deliberately widened allowlist in tests/test_state_allowlist.py.

## Verification

- [X] T009 Run focused tests and full pytest suite, inspect runtime diff and file hygiene; record evidence in specs/114-state-allowlist/tasks.md.

## Dependencies and execution

T001 -> (T002, T005, T007) -> T003 -> T004 -> T006 -> T008 -> T009.
All behavior tests precede implementation. US1 is the state-only MVP; all three stories are
required for completion. US1 and US2 tests can be designed independently, but this seat executes
sequentially because they share test files. No parallel agent work is needed.

## Validation evidence

- Initial allowlist and reader checks: 31 failed, 3 passed. Unknown keys and kinds were
  accepted, callback writes bypassed protection, and refusals lacked command guidance.
- After implementation: 34 passed. Focused state, brief, watch, obligations, canary, merge,
  stop and signal suites: 714 passed.
- Additional callback type regression: 1 failed, 2 mutation checks passed. Protected
  comparisons now distinguish JSON numbers from booleans; 37 allowlist tests passed.
- Mutation checks widen the state allowlist with report_at and events with seat launched;
  the source-driven inventory catches both.
- Review found a schema-invalid probe could mask an allowed path. Inventory checks now assert
  permissions separately and use existing valid values; mutations cover report_at,
  gate_approved and seat launched. Dynamic scheduler keys and looped fields are included.
- Corrected the close-event hint after its new test failed; 39 allowlist tests pass.
- Read-only review and one delta review: no remaining blocking findings.
- Full suite passed before the final test/hint changes: 4323 passed, 3 skipped.
  Final full-suite result: 4325 passed, 3 skipped in 78.72s (0:01:18).
- Final diff, Python syntax and hygiene checks passed across all 16 changed or added files.
  No commits, pushes or GitHub commands were run.
