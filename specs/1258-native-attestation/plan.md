# Implementation Plan: Protected native seat attestation

**Branch**: `codex/1258-native-attestation` | **Date**: 2026-10-27 | **Spec**: [spec.md](spec.md)

## Summary

Extend the shared protected transcript reader and existing report lifecycle. Prove native reports with first metadata, own rows, correlated launch/result and final report. Map UUID to canonical identity only after proof. Read child turn settings separately from provider metadata.

## Technical Context

Python 3.11+, standard library only. Existing JSONL records, hash-chained events and kept Markdown report store. pytest fixtures mirror sanitized observed native rows. Platforms remain POSIX and Windows. No config additions or shell parser change. Item budget is 111 net runtime lines; the owner approved the 4,000 total cap on 2026-10-27.

## Constitution Check

Stdlib, evidence, closed doors, owner scope, test-first and redaction requirements pass before research. The approved cap amendment is explicit and dated in its commit. No trust or installation action belongs here. Recheck after design: same constraints hold, with existing protection expanded to the newly accepted transcript root.

## Research and design

[research.md](research.md) records observed callback timing and native shapes. [data-model.md](data-model.md) defines proof invariants. [contracts/native-records.md](contracts/native-records.md) defines the accepted producer contract. [quickstart.md](quickstart.md) defines validation.

## Project Structure

Runtime: `cli/wuwei/hook.py`, `ws.py`, `guards.py`; guidance string only in `evidence.py`. Tests: `tests/test_native_evidence.py`, fixtures, existing hook/guard/model/setup suites. Documentation: design, SECURITY, Codex concepts, planner charter; generated agents and vendored copies stay synchronized. Spec artifacts stay in this folder.

## Implementation sequence

1. Add native proof, protection, settings and report lifecycle tests; observe failure.
2. Add the shared native reader and protected root; preserve the legacy branch and current store.
3. Update accurate guidance and approved budget, generate agents and vendor files.
4. Run focused and full tests, route differential, generated path/wrapper probes and isolated mutants.
5. Analyze completed artifacts and hand off the draft head for all four gates, CI and owner review.

Size: Native trust-boundary fixtures and full spec evidence require more than 400 changed lines. Runtime remains bounded by the item budget.
