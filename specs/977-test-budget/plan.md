# Implementation Plan: Restore the test function budget

**Branch**: `977-test-budget` | **Date**: 2026-10-13 | **Spec**: `spec.md`

## Summary

Convert related test functions into parameter cases while preserving each distinct invocation and assertion. Count definitions with the CI regex, compare collected items per changed file, and run the full suite with explicit files.

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: pytest (development only)  
**Storage**: None  
**Testing**: pytest with the issue's pipeline interpreter  
**Target Platform**: CI and local Python 3.11+  
**Project Type**: Test-only maintenance  
**Constraints**: No runtime edits, skipped cases, network, real GitHub, or absolute local paths in repository files  
**Scale/Scope**: 3037 definitions and 7859 collected cases at baseline

## Constitution Check

- Principle III: one behavior per test case; parameter rows remain independently collected.
- Principle IV: add a failing suite budget regression first and see the expected failure.
- Principle V: use existing pytest parameterization, with no new runtime abstraction.
- Workflow: complete specification, clarification by assumption, plan, tasks, analysis, checklist, implementation, suite, and review in order.

## Research and Design

The CI count step at `.github/workflows/tests.yml:29-34` matches `def test_` text, so existing parameterized tests count once per function. Consolidation belongs in tests, not CI or runtime code. October's largest test-file growth guides the search. Merge identical bodies into one parameter table. For related behavior families with different assertion shapes, parameterize named scenario functions and retain each original body unchanged. Keep the group local to its test file, with matching fixture signatures and descriptive case names. Preserve fixtures and marks.

## Project Structure

```text
specs/977-test-budget/
  spec.md
  plan.md
  research.md
  data-model.md
  quickstart.md
  tasks.md
  analysis.md
  verification.md
  checklists/requirements.md
.github/workflows/tests.yml
  existing CI count step, read only
tests/
  test_dev_cycle.py
  selected related test files
```

## Verification

1. Capture baseline collected node IDs per file.
2. Add a suite-count regression in `test_dev_cycle.py` and observe the red result.
3. Consolidate related tests, tracking the exact old-to-new case mapping.
4. Confirm all changed files retain their collected count unless an exact duplicate is listed.
5. Run every changed file and then all explicit test files with the required interpreter.
6. Confirm the regex count is at most 2809 and inspect the diff for runtime changes, skips, weakened assertions, and absolute local paths.
