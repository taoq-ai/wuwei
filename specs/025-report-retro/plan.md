# Implementation Plan: Report and steward retro

**Branch**: `025-report-retro` | **Date**: 2026-09-29 | **Spec**: [spec.md](spec.md)

## Summary

Compile a local retro and owner report from existing readers. Use the existing promotion producer for charter changes. Make Stop inspect the `.wuwei` promotion repository for committed charter and changelog evidence.

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: standard library only  
**Storage**: workspace files and local git history  
**Testing**: pytest, in-process tests and one real git smoke test  
**Target Platform**: existing WUWEI CLI  
**Constraints**: three-state exits, no direct subprocess in core, no hand edits to charters

## Constitution Check

- Existing state, event, workspace, metrics, decision and VCS port readers are reused.
- Tests precede each behavior. Missing evidence fails closed with a reason.
- No new runtime dependency or adapter is needed.

## Design

1. Add a retro command that reads captured notes, metrics and verdicts and writes a dated review with cycle table. Proposals remain in the existing proposal directory; promotion lands them.
2. Extend promotion so a landed charter proposal writes a dated changelog entry in the same promoted commit.
3. Update Stop to check committed charter and changelog evidence in the `.wuwei` repository, including promotion history integrity.
4. Add report command that composes existing state, decisions and process or outcome evidence into local owner text.

## Deferred

- Any outcome metric without an existing producer is shown as unmeasured. Full four-metric implementation belongs to outcome metrics work.
