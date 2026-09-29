# Implementation Plan: Scope stop verdict lint

**Branch**: `166-stop-lint-scope` | **Date**: 2026-09-29 | **Spec**: [spec.md](spec.md)

## Summary

Reuse the transcript-to-reservation lookup already in the agent stop guard. Select
only the exact registered seat verdict in its original day. Prefix stop lint findings
with the file path without changing shared lint or PostToolUse output.

## Technical Context

Python 3.11+, stdlib-only runtime, pytest development tests. Existing JSON state and
transcript files; no new schema, ports, dependencies, configuration or public interface.
In-process tests cover raw guard exits and hook translation. Scope is one hook bug.

## Constitution Check

Pass before and after design: shared ownership lookup, test first, three-state exits,
shared workspace scope and reserved seat state, no external calls or new trust keys.
PostToolUse and agent stop lifecycle behavior remain unchanged.

## Evidence and Design

Read-only reproduction against the supplied operator dry-run workspace returned exit 1
for architecture and security verdicts during a quality stop. Event persistence was
mocked to keep that workspace untouched. The daily glob applies the stopping role to
all files, which explains the missing Simplicity and Design rows.

Extract the existing validated transcript brief lookup from `agent_launch.stop` into
`agent_launch.stopping_seat`, returning the original day, registered name and role.
Both stop handlers call it, including after a reservation is marked stopped. The verdict
guard selects the exact assigned filename, preserving case-insensitive gate detection
and the existing missing-file behavior. Ownership failures return exit 2 with a reason.
SubagentStop uses the existing guard_scope helper so anchored worktrees are covered
and an environment-selected workspace does not make unrelated directories relevant.
No fallback to runtime agent ID or role-only filtering: neither uniquely identifies the
registered seat. Lint findings still log through the existing verdict rejection writer.

## Project Structure

- `cli/wuwei/guards/agent_launch.py`: share existing stop ownership resolution.
- `cli/wuwei/guards/verdict.py`: scope stop lint and name refused files.
- `tests/test_verdict.py`: ownership and three-state regression table.
- `tests/test_retro.py`: update stop integration to the new ownership contract.
- `specs/166-stop-lint-scope/`: spec, plan, tasks and requirements checklist.

## Validation

First run new regression tests against the old implementation and confirm failures.
Then run verdict, retro and agent launch tests, followed by the full suite using the
interpreter provided in the task. Review the diff for scope, portability and prose hygiene.
