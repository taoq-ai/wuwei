# Implementation Plan: Outward-text guard

**Branch**: `011-outward-lint` | **Date**: 2026-09-28 | **Spec**: [spec.md](spec.md)

## Summary

Reuse workspace configuration, the Guard registry and adapter ports. A shared outward
lint and send/draft classifier enforce the same policy through PreToolUse and port calls.
No network or new runtime dependencies; commit resolution stays behind the VCS port.
Use the current worktree and leave changes uncommitted.

## Technical Context and Constitution Check

Python 3.11+ standard library; pytest tables run in process. Workspace TOML supplies rules.
Existing hook.run translates findings into refusal output. Errors return 2 and cannot
become warnings. Diagnostic output never echoes message bodies. Tests run red before each
correctness fix, then green with the interpreter supplied in the task.

## Decisions

A complete mechanical allowlist avoids semantic guesses: only a resolved `fixed in <sha>`
message can send. The shared classify function returns send or draft with a three-state
code. The approve tier never sends because a process with the owner's uid can forge any
local file or hook payload. There is no approval storage, digest or recorder. Adapter draft
delivery and #95 outbound tiers are deferred.

Configured regexes handle internal phrases and tool names. NFKD and removal of Mn, Me and
Cf prevent common obfuscations. Emoji detection uses conservative symbol ranges plus
U+FE0F presentation sequences. Unknown MCP names require configuration unless their last
segment starts with a read verb, optionally preceded by a service word contained in the
MCP server segment. Missing workspaces fail closed at ports; hooks are inert
outside workspaces only when the override is unset.

The state writer retains generic namespace reservation with an empty set. Future owning
features register keys; #8 will add fast_checks. Existing gate_verdicts writes remain valid.
State and event writers create only days/ and its day directory under an existing .wuwei/.

## Files and Validation

- cli/wuwei/outward.py: lint, extraction and send/draft classification.
- cli/wuwei/guards/outward.py: workspace scope and MCP routing.
- cli/wuwei/registry.py: policy enforcement at text-bearing ports.
- cli/wuwei/workspace.py and templates/workspace/config.toml: defaults and matchers.
- cli/wuwei/state.py: generic reserved-namespace mechanism.
- tests/test_outward.py: lint, classification, payload, scope and hook tables.
- tests/test_state.py: generic reservation and restored gate_verdicts regression.
- Adapter transport tests unwrap the policy decorator; outward tests exercise wrapped ports.

Run focused tests after each correction, then the full suite and git diff --check.
