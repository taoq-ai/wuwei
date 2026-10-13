# Tasks: Spec-mode heading forms

**Input**: [spec.md](spec.md), [plan.md](plan.md)

## Phase 1: Reproduction

- [x] T001 [US1] Add a failing field-case clarification test in `tests/test_spec_mode.py` and run it.
- [x] T002 [US2] Add a failing bold governing test through the shared lookup and analysis path in `tests/test_spec_mode.py` and run it.

## Phase 2: Implementation

- [x] T003 [US1] Accept heading suffixes in `_clarified` in `cli/wuwei/specmode.py`.
- [x] T004 [US2] Accept bold labels in `GOVERNING` in `cli/wuwei/specmode.py`.

## Phase 3: Verification

- [x] T005 Run all explicit test files importing `specmode` with the required interpreter.
- [x] T006 Review the diff for scope, constitution compliance, and open high-severity findings.
- [x] T007 Fold the field-case tests into existing functions and verify colon-inside-bold and bullet governing labels through analysis and gate paths.
