# Implementation Plan: Step-wise build loop

**Branch**: `161-build-next` | **Date**: 2026-09-29 | **Spec**: [spec.md](spec.md)

## Summary

Refactor commands/build.py around one persisted next_action function. Claude actions
are executed by the planner, Codex actions by the existing adapter loop. Reuse the brief
formatter, state writer, Agent reservation and stop hooks, checks adapter and decision lint.

## Technical Context

Python 3.11+, standard library runtime, pytest development tests. State remains in the
day state.json and append-only events.jsonl, with existing locks and atomic writes.
No network or real runtime in tests. Existing git worktree provides isolation.

## Constitution Check

Pass before and after design: stdlib only, adapter ports, three-state exits, test-first,
producer-owned state, one shared action selector, no new service or speculative layer.
The owner explicitly authorizes the section 5.3 amendment.

## Evidence and decisions

Read-only dry-run reproduction confirmed Claude status returns exit 2, host.seats is one,
and the build park file fails decision lint with thirteen missing fields. The current
build command also rejects next syntax. The provided probe and companion mutate their
workspace, so they were inspected rather than executed. No graphify graph is present;
direct source inspection avoids generating unrelated files or machine paths.

Use reserved builds state for iteration progress and cached actions. Hooks bind it to the
existing brief and reservation. Continue requires the recorded runtime agent ID and the
same brief. Preserve generic-event allowlisting. Store check details in existing reserved
fast_checks evidence so SubagentStop can reuse measured failures; otherwise return check.
Only reuse checks for a tree clean at measurement and stop.
Bind result writes to the exact running record and final transcript completion; bind
check writes to the captured iteration under the state lock to reject delayed producers.

## Project Structure

Modify commands/build.py, guards/agent_launch.py, fast_checks.py, state.py, commands/event.py,
workspace.py and template config. Extend the shared decision writer only if needed.
Tests cover actions, hooks, CLI compatibility, producer protection and host capacity.
Documentation changes are the design amendment, planner skill and site configuration.

## Validation

Write and run failing action/hook tests before implementation. Keep existing Codex tests,
add a shared-selector assertion, and exercise malformed, stale and duplicate evidence.
Run the full suite with the task-provided interpreter. Inspect the diff and hygiene.
