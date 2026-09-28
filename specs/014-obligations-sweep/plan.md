# Implementation Plan: PR obligations sweep

## Summary

Reuse state, workspace, code_host and command discovery. Add one obligations module,
`wuwei sweep obligations`, and a narrow shepherd reply command that posts
through the existing port before recording an acknowledgement. No hook guard is added.

## Technical Context

Python 3.11+, stdlib runtime, pytest development tests, in-process code_host fake and
recorded adapter responses. No network, git or gh invocation in core.

## Constitution Check

All gates pass: stdlib only, three-state exits, single state writer, tests before
implementation, reserved acknowledgement namespace, no private bodies in events.
The existing worktree supplies isolation. Extension hooks are skipped as requested.

## Structure and Design

- `adapters/code_host/github.py`: extend existing PR shape with requested reviewers
  and teams, and comment/review shapes with explicit bot identity. Preserve fresh
  reads, pagination refusal and adapter error handling.
- `cli/wuwei/obligations.py`: validate normalized evidence, evaluate absolute reply
  state, visibility, and the union of day PRs. Continue after per-PR errors. Pin the
  day directory once and append one summary event through the existing writer.
- `cli/wuwei/commands/sweep.py`: command translation only.
- `cli/wuwei/commands/reply.py`: specific unthreaded acknowledgement producer;
  read text from stdin, post through outward policy, verify the returned reply via
  fresh reads, then atomically record the target revision. Never accept caller
  supplied success evidence.
- `cli/wuwei/state.py`: reserve `reply_acks` and `channel_posts` at every nesting
  level, refuse PR removal, and record whether state contained PRs in events.
- `cli/wuwei/commands/event.py`: reserve sweep and acknowledgement event kinds.
- `cli/wuwei/references.py`: share canonical repository and PR validation with
  the code-host adapter.
- `cli/wuwei/verdict.py`: share verdict vocabulary and lint gate-file evidence.
- `tests/test_obligations.py`, `tests/test_code_host.py`: table cases and replay.

## Sequence

Port evidence tests and minimal adapter extension; reply/visibility/error sweep
cases and implementation; reserved ledger and successful/failed reply cases and
implementation; full suite and hygiene review. See tasks.md for test-first pairs.

## Decisions

Use structured state for channel evidence instead of carrying forward a vendor log
regex, reserving it until a posting producer exists. Read verdicts from linted
gate files matching the current head. Use the configured owner login without a CLI
override. Check event history before declaring an empty PR set clean. Store a hash of each target revision so edits invalidate acknowledgements.
Keep approval bodies outside reply counts, following the source harness. No new
port operation or shell allowlist entry is needed.
