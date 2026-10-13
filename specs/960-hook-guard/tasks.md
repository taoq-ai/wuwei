# Tasks: Hook invocation guard (#960)

## Phase 1: Setup

- [x] T001 Create feature artifacts in specs/960-hook-guard/ on the current branch.

## Phase 2: Foundation

- [x] T002 Trace root causes and caller-authentication evidence in specs/960-hook-guard/research.md and plan.md.

## Phase 3: US1 - Refuse forged hook events

Independent test: full PreToolUse denial for field reproductions and all wrapper families.

- [x] T003 [US1] Add field-case, prefix, wrapper, path, pointer and outside-cwd regressions to tests/test_protect_state.py; run and observe expected failures.
- [x] T004 [US1] Fix parsed prefix matching and narrow ParseError fallback in cli/wuwei/guards/protect_state.py with one shared reason.

## Phase 4: US2 - Preserve legitimate hooks and ordinary commands

Independent test: ordinary unsupported syntax retains allow/log behavior, parsed data
stays allowed, and the configured hook shim replays payloads.

- [x] T005 [US2] Add negative controls to tests/test_protect_state.py before T004; validate them and existing configured shim replays in tests/test_hooks.py after T004.

## Phase 5: Verification

- [x] T006 Run explicit affected tests from tests/, review the diff for security and simplicity, and record exact results in specs/960-hook-guard/analysis.md.

## Dependencies and execution strategy

T001 -> T002 -> T003 and T005 tests -> T004 -> T005 validation -> T006.
US1 is the fix; US2 is its compatibility gate. No useful parallel editing: both
stories share the same small regression table and runtime function. Leave changes
uncommitted. No network or real GitHub calls in tests.

## Review follow-up

- [x] T007 Update the spec, assumptions, plan, analysis and checklist for F1-F6.
- [x] T008 Port F1-F4 and ordinary harness rows, add F5 controls in tests/test_protect_state.py, and observe failures.
- [x] T009 Fix F1-F5 in cli/wuwei/guards/protect_state.py and run the focused tests.
- [x] T010 Run all affected test files, inspect the delta and record results in analysis.md.

Dependencies: T007 -> T008 -> T009 -> T010. F6 is deferred explicitly in the spec.
