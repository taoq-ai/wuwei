# Implementation Plan: Generic role charters

**Branch**: `019-charters` | **Date**: 2026-09-28 | **Spec**: [spec.md](spec.md)

## Summary

Distill the source harness into eleven short, generic markdown charters. Put cross-seat policy in `_common.md`, authored-output and change-history rules in `_common-authoring.md`, and ordered role work in each role file. Use tests to pin coverage and generic identifier lint.

## Technical Context

Markdown only at runtime. Python 3.11 and pytest for the table and lint test. Existing `config.toml` provides repos, owner, adapters, boundary and environment registers. No new dependencies or CLI functions.

## Constitution Check

The charters follow the design spec as amended, retain the CLI as sole state writer, make guards authoritative, and avoid duplicate policy implementations. Test first, simplest diff, no external calls. PASS.

## Project Structure

- `charters/_common.md`, `_common-authoring.md`: shared authority, decision and authoring rules.
- `charters/{planner,lead,builder,sentinel-arch,sentinel-quality,sentinel-security,sentinel-goal,shepherd,steward}.md`: ordered role checklists.
- `tests/test_charters.py`: file, generic identifier lint, policy and section 5.3 body-clause coverage.

## Validation Strategy

Write the test table and lint first, run it to observe missing charters, then author the files. The owner-local pre-publish scan is tracked in issue #42. Run the focused test, full requested suite, and a final banned-character scan. No additional design artifacts are needed for static markdown.
