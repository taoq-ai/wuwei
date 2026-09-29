# Implementation Plan: Guard mutation coverage

## Technical Context

Python 3.11+, pytest tests only, no runtime dependencies. Existing `guards.discover()` supplies the live registry. Existing guard tables supply realistic examples and fixtures. Work is test-only unless a new bypass row finds a defect.

## Constitution Check

- Stdlib runtime: no runtime dependency changes.
- Three-state exits: assertions distinguish blocked and unmeasured results.
- One behavior, one function, one test: each registered guard has an explicit probe.
- Test first: demonstrate missing coverage and disabled guard failures before adding coverage.
- Simplicity: one in-process mutation helper, no subprocess per guard.
- Security: bypass cases include wrappers and opaque commands.

## Design

Add `tests/test_guard_mutation.py` with a table keyed by module, event, matcher and check name. The meta-check compares this table to live `discover()` output, plus the merge policy and decision lint. Each table entry invokes a small representative assertion against the real check, then replaces it with a clean no-op and confirms the same assertion fails. Extend existing command guard tables only for 4.5 forms absent there. No new data model or external contract is needed.

## Validation

Run the focused mutation test during red and green phases, then the specified full pytest command. Check changed files for forbidden writing and local absolute paths.
