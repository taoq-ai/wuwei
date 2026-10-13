# Implementation Plan: PR flow doctor completion

**Branch**: `941-ruling-lint` | **Date**: 2026-10-13 | **Spec**: [spec.md](spec.md)

## Summary

Keep the standalone guidance in `next` and have the process that diagnoses `pr-flow` record the completed check on a started day. The record is an existing `next.action` pass that `_seen` already treats as done. Compound command parsing stays unchanged.

## Constitution Check

- III: `doctor.run` owns the check and writes through the existing state writer.
- IV: the compound-call regression test failed before the code change.
- V: one existing event type, no new parser, module or dependency.

## Verification

Run the impacted explicit test files with the specified interpreter.
