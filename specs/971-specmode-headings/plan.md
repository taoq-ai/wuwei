# Implementation Plan: Spec-mode heading forms

**Branch**: `971-specmode-headings` | **Date**: 2026-10-13 | **Spec**: [spec.md](spec.md)

## Summary

Recognize the reported Markdown forms at the shared spec-mode parser. Reuse the current status and governing lookup so all callers receive the same behavior.

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: Standard library only at runtime  
**Storage**: Existing Markdown spec files  
**Testing**: pytest via the task interpreter, explicit affected files  
**Target Platform**: WUWEI CLI  
**Project Type**: Claude Code plugin  
**Constraints**: No new module, no network, no real GitHub

## Constitution Check

- Test first: add the field-case regression tests and observe expected failures before editing runtime code.
- One behavior, one function: keep clarification detection in `_clarified` and governing detection in `governing` through its shared regex.
- Stdlib only: use existing `re` expressions.
- Fail closed: preserve missing-heading and invalid-reference errors.
- Simplicity: change only the two match expressions and focused tests.

## Research

`cli/wuwei/specmode.py` has the complete shared parser. `_clarified` anchors `## Clarifications` to the end of a line. `GOVERNING` anchors `Governing:` to the start of a line. `governing` is used by the analysis command and gate brief. Accepting the heading suffix and governing label variants in these expressions is sufficient.

## Design

No data model or external contract changes. `status` and `done` continue using `_clarified`; `governing` continues supplying the resolved reference to analysis and gate callers. Existing plain forms and item-level priority remain.

## Project Structure

- `cli/wuwei/specmode.py`: shared matching rules.
- `tests/test_spec_mode.py`: field-case and existing-form regression tests.
- `specs/971-specmode-headings/`: this issue's spec-kit artifacts.

## Verification

Run the new tests red, then green. Run every explicit test file importing `specmode` with `../_pipeline/venv/bin/python -m pytest -q -p no:cacheprovider`.
