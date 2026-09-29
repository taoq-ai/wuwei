# Implementation Plan: Scripted delivery day

**Branch**: `037-e2e-day` | **Date**: 2026-09-29 | **Spec**: [spec.md](spec.md)

## Summary

Add default-collected integration tests with a temporary fixture workspace and local
Git demo repository. Drive existing CLI handlers in process. Script only seat execution
and adapter results, using tests/fakes and code-host recordings. Exercise real guards,
state writers, event producers, verdict receipt, shepherding, retro and reporting.

## Technical Context

Python 3.11+, pytest only. No runtime dependencies or new runtime interfaces.
Use the local VCS adapter to initialize the demo and record source snapshots. Existing
recording fakes supply remote metadata, host memory and code-host responses. Scripted
runtime seats emit source changes, verdict files and SubagentStop transcripts. Deny
network and unexpected subprocesses. Default CI already runs all tests on every PR.

## Constitution Check

Pass: runtime remains stdlib-only, errors retain three-state exits, tests precede
fixture implementation, existing producers retain ownership of trusted state, and
all artifacts live under tmp_path. No guard or policy bypasses. No external messages.

## Implementation

1. Write the day scenario and observe its missing fixture failure.
2. Implement the smallest fixture and scripted runtime needed to execute the scenario.
3. Write integrity drift and absent-scanner scenarios before extending their fixture support.
4. Validate targeted tests, full suite, elapsed time and repository hygiene.

## Project Structure

- `tests/test_e2e_day.py`: scenarios and local fixture orchestration.
- `tests/fakes/day.py`: scripted runtime and workspace setup if separation keeps the
  scenario readable; reuse Recorder and existing port fakes.
- `specs/037-e2e-day/`: spec, plan, tasks and requirements checklist.

## Validation

Run `python -m pytest -q tests/test_e2e_day.py --durations=5`, then the default full
suite with the task-provided interpreter. Inspect events for phase ordering, one fix
round, one delta and successful guarded close. Inspect negative exits and absent
trusted records for scanner failure and plugin drift.

## Deferred

None. Record any discovered upstream gap here and in the spec before using xfail.
