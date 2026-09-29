# Implementation Plan: Build environment failures and seat usage

**Branch**: `173-build-env-usage` | **Date**: 2026-09-29 | **Spec**: [spec.md](spec.md)

## Summary

Classify execution failures in the existing local checks adapter, park on their first occurrence in the existing build transition, preserve runtime usage from Codex and Claude results, and select each launch adapter from the approved role policy.

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: Standard library only at runtime  
**Storage**: Existing state JSON and events JSONL  
**Testing**: pytest  
**Target Platform**: Existing WUWEI CLI  
**Project Type**: CLI with adapters  
**Performance Goals**: One check and one park transition for an environment failure  
**Constraints**: Three-state exits, fail closed on unreadable input, no new external dependency  
**Scale/Scope**: One build item and its seat per transition

## Constitution Check

- Runtime code stays stdlib-only.
- Adapter owns subprocess execution and classifies its output; build owns state transitions.
- Tests precede every behavior change and cover exit 0, 1, and 2 paths.
- Existing atomic state writer and decision writer remain the only writers.
- No new configuration keys are required.

## Design

1. The checks adapter returns an environment reason in `Result.data` for command-not-found, missing interpreter, or missing development module. The result remains a finding, exit 1, because the check did run and identified an actionable environment fault. An adapter execution error remains exit 2.
2. `complete_checks` parks immediately when a result carries an environment reason. It does not create a continue action. Ordinary test failures still use the current signature and budget logic.
3. Codex result parsing copies usage from `storedJob.result`; `record_result` normalizes missing fields to `unmeasured` while retaining valid reported values. Claude SubagentStop usage goes through the same function.
4. Runtime selection reads the approved `seat_policy` for the role, falling back to workspace config. Keep the selection near the current launch paths and use the existing registry.

## Project Structure

```text
adapters/checks/local.py
adapters/runtime/codex.py
cli/wuwei/commands/build.py
cli/wuwei/commands/runtime.py
cli/wuwei/steward.py
tests/test_build.py
tests/test_build_next.py
tests/test_runtime.py
tests/test_runtime_cli.py
```

## Validation

Run focused red and green tests for each change, then the full required pytest command. Inspect changed files for local absolute paths, em-dashes, and emojis.

## Deferred

No migration of historical seat usage events.
