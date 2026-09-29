# Implementation Plan: ZIRAN agent-surface gate

## Summary

Add `adapters/scanner/ziran.py` behind the existing scanner port. At security
`dispatch.receive`, scan the reviewed worktree when approved item flags set
`agent_surface`. Merge scanner rows into the existing verdict, lint it, record using the
existing reserved gate writer, then atomically write it. Recheck HEAD after scanning.

## Technical Context

Python 3.11+ stdlib runtime; pytest tests. No new dependencies. Subprocesses live
only in the adapter and use fixed argv for audit and CI, timeout and JSON validation.
Use temporary report files for the CI boundary, never a caller-supplied executable.
Use recorded JSON and fake subprocess results plus one PATH-stub boundary smoke.

## Constitution Check

- Stdlib only and adapter-only subprocess calls.
- Three-state results: measured clean 0, findings 1, unmeasured 2 with reason.
- Test tasks precede each implementation task.
- Reuse registry, item flags, verdict parser, atomic writer and event/state writers.
- No new trust anchors or state keys; scanner events are already reserved.
- Existing workspace scope applies; no new hooks or shell parser changes.
- Work remains in this branch with no commits or remote writes.

## Structure and Decisions

- `adapters/scanner/ziran.py`: audit/CI contracts, fixed command arguments and unavailable
  traces/MCP operations. Validate structured reports before interpreting any exit.
- `cli/wuwei/scanner.py`: scan orchestration and safe verdict row rendering.
- `cli/wuwei/dispatch.py`: mandatory scan at security receive and HEAD recheck.
- `cli/wuwei/workspace.py`: validated `scanner.severity_threshold`, default high.
- `templates/workspace/config.toml`, `docs/site/configuration.md`: public configuration.
- `tests/test_ziran.py`, `tests/test_dispatch.py`: adapter and receive regressions.
- `tests/fixtures/scanner/`: deterministic vulnerable source and recorded reports.

Only blocking scanner findings change PASS to FIX; other rows remain notes. Threshold controls blocking
for ordinary findings; known trust rules, explicitly marked trust boundaries, and
trust-surface or boundary-relevant items always block security findings. Preserve PARK/ESCALATE decisions. Missing worktree or unreadable evidence is
unmeasured. Scan again for delta receives. Sanitize finding text before Markdown rendering
and redact findings with existing workspace security and redaction helpers.

## Validation

Run focused adapter and gate tests after each red/green cycle. Run docs/adapter contract
checks and then the full pytest suite with the interpreter named by the task. Inspect
the final diff for scope, absolute machine paths, emojis and em-dashes.

## Deferred

Live traces (#34 / taoq-ai/ziran#421), MCP (#35 / taoq-ai/ziran#422), and S1 release pinning.
Live S4 also requires upstream JSON audit/CI and --severity-threshold support; incompatible
versions are unmeasured. See research.md for the explicit fixture contract.
