# Implementation Plan: Publish reads

**Branch**: `947-publish-reads` | **Date**: 2026-10-13 | **Spec**: [spec.md](spec.md)

## Summary

Fix the shared classifier in `cli/wuwei/guards/edges.py` and its publish card description. Extend `tests/test_edges.py`; no new runtime module.

## Technical Context

Python 3.11+, standard library only. Existing Bash segment parser, gh option scanner, workspace fixtures and sessions.needs_owner. Storage and owner approval events unchanged. Local CLI/plugin hooks; pytest is dev-only. No network, new dependency, subprocess or hook I/O. Constant-size predicate additions preserve the existing hook latency budget.

## Constitution Check

Pass before and after design: stdlib runtime, shared behavior, three-state exits and owner boundary preserved; test-first reproduction required. No new state writer or subsystem. Issue's explicit test-file instructions override the bare full-suite rule. Design wording interpretation is recorded in spec Assumptions. Owner design file stays untouched.

## Project Structure

- `cli/wuwei/guards/edges.py`: api, command_result, check_deploy.
- `tests/test_edges.py`: existing fixture-based guard tables and owner-card tests.
- `specs/947-publish-reads/`: specification, plan, research, data model, contract, quickstart, tasks, analysis and checklists.

## Implementation

1. Reproduce field reads, conservative request variants and exact-command card requirement before fixing.
2. Exempt only GET without fields/input from deployment/environment API refusal, using the existing scanner. Reject residual unparsed short clusters conservatively and return immediately for safe deployment/environment reads. Leave other API classification unchanged.
3. Add `env ls` to the existing Vercel/vc read predicate, after explicit deny patterns.
4. Add exact-command and run-alone wording at check_deploy's existing needs_owner call.
5. Run the focused tests and every test file importing edges, plus review correctness, security and unnecessary complexity.

## Validation

Use the task-specified interpreter with `-m pytest -q -p no:cacheprovider` and explicit test paths. Record exact summary lines in analysis.md. Existing tests cover exits 0, 1 and 2. All external behavior uses fakes. Review original approval versus modified options and compounds without running any real command.


## Review follow-up: F1 and F3

1. Reproduce preview writes and ambiguous deployment/environment operands in tests/test_edges.py, then add --preview to GH_VALUED and refuse multiple targets containing these paths in api(). Recognize preview values through the shared scanner for every caller.
2. Reproduce override headers in tests/test_edges.py, then classify -H/--header values containing override (case-insensitive) as non-reads. Keep ordinary headers allowed.
3. Leave F2 host permissions and F4 owner design unchanged; record both decisions and the design conflict in spec Assumptions.
4. Run every test file importing edges plus tests/test_signal_status.py with the task-specified interpreter and explicit paths. Record red/green summaries and final verification in analysis.md.
