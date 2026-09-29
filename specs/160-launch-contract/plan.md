# Implementation Plan: Seat launch contract

**Branch**: `160-launch-contract` | **Date**: 2026-09-29 | **Spec**: [spec.md](spec.md)

## Summary

Add `brief.launch_prompt` and a shared brief-reference prefix to the existing core brief module. Claude dispatch uses it, including steward launches routed through that adapter. Continuation regenerates instructions through dispatch, retains the brief handle and adds feedback. The launch guard and transcript reader use the same prefix. No guard validation is relaxed.

## Technical Context

- Python 3.11+, standard library runtime; pytest for tests.
- Existing CLI, runtime adapter and workspace day files. No new state schema or dependencies.
- Existing dispatch syntax is unchanged. Relative command arguments keep their current cwd semantics; the generated reference is always relative to the workspace root.
- Tests use existing brief fixtures, fake VCS and host measurements. No network or real agent runtime.

## Constitution Check

Pass before and after design: one core formatter, no subprocess in core, three-state error handling, failing regression tests before code, existing locked state writers and scope checks unchanged. No new trusted records, config keys or abstractions. No commits or pushes.

## Investigation

The supplied operator workspace was inspected read-only. Calling the existing Claude adapter for its logged builder and steward briefs produced exit 0, but checking each prompt through the launch guard returned exit 1: missing logged brief reference at prompt start. State writes were blocked during reproduction. The historical events contain the same refusal.

`steward.run` already delegates to runtime dispatch; keep that route instead of formatting twice. `brief.transcript_reference` also recognizes this prefix and should share the constant. Continuation currently drops the brief and has no prompt. Reuse dispatch validation and retain its returned handle for repeated continuation.

## Project Structure

- `cli/wuwei/brief.py`: formatter and shared prefix, transcript reader reuse.
- `cli/wuwei/guards/agent_launch.py`: shared prefix and actionable refusal.
- `adapters/runtime/claude.py`: dispatch and continuation integration.
- `tests/test_launch_contract.py`: command output to guard integration and malformed continuation cases.
- `docs/site/concepts.md`, `skills/wuwei-plan/SKILL.md`, `charters/planner.md`: launch contract and generated instruction usage.
- `specs/160-launch-contract/`: specification, plan, tasks and quality checklist.

## Validation

Write and run failing integration tests for dispatch, continuation, missing-marker guidance and steward. Then implement the shared formatter and rerun focused tests. Exercise all roles, a worktree distinct from the workspace, repeated continuation, malformed handles, and existing guard denial cases. Run the full suite with the task-provided interpreter and `-m pytest -q`. Check the final diff for absolute local paths, emojis, em-dashes and whitespace errors.

## Deferred

None. No new scheduling or resume protocol is needed for this prompt repair.
