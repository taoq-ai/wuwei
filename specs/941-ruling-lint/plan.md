# Implementation Plan: Ruling IDs at token boundaries

**Branch**: `941-ruling-lint` | **Date**: 2026-10-13 | **Spec**: [spec.md](spec.md)

## Summary

Constrain the ruling extractor in `cli/wuwei/brief.py` and clarify the missing-file path in `cli/wuwei/security.py`. Use existing entry points and test fixtures.

## Constitution Check

- III: one extractor for all brief callers and one outbound file reader for all guarded sends.
- IV: run failing field-case tests before code changes.
- V: two local changes, no new module or dependency.

## Verification

Run every test file importing the changed modules with the specified Python interpreter and explicit file arguments.
