# Implementation Plan: Agent generation from charters

**Branch**: `020-agent-generation` | **Date**: 2026-09-28 | **Spec**: [spec.md](spec.md)

## Summary

Add one `agents` CLI command module with `build` and `check` subcommands. Render each role from its versioned charter and common charter bodies, using the explicit JSON tool matrix. Write through the shared atomic writer. Pin output with a pytest golden test invoked by the existing CI suite.

## Technical Context

Python 3.11 stdlib runtime, pytest development dependency. The command module finds the plugin root from its own file, matching existing command conventions. Source and output are plugin files rather than workspace state. No external tool calls.

## Constitution Check

One renderer owns the behavior; CLI and test reuse it. Invalid inputs fail closed with exit 2, drift returns 1, clean returns 0. Generated writes are atomic. Tests run red before implementation. No dependency or extra layer is added. PASS.

## Project Structure

- `cli/wuwei/commands/agents.py`: CLI registration, rendering, validation and build/check.
- `agents/allowlist.json`: nine explicit tool lists.
- `agents/README.md`: role tool rationale.
- `agents/<role>.md`: generated files.
- `tests/test_agents.py`: golden drift, rendering, invalid source and CLI behavior.

## Validation Strategy

Write focused tests first; observe missing module or output failure. Implement the renderer and command. Generate agents, verify golden drift detection after a charter edit in a fixture, then run the requested full suite. No extra design artifacts are needed.
