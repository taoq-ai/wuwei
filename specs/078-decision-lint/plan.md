# Implementation Plan: Decision lint

## Technical Context

Python 3.11+, stdlib runtime and pytest development tests. Add one decision core,
one command module and one guard module, plus the reserved state namespace.
Reuse verdict.active_text, guard discovery, shell.normalize/is_opaque, workspace clock,
state writer and registry VCS port. No shell execution in core.

## Constitution Check

Pass: stdlib only, three-state exits, single shared evaluator, tests before implementation,
atomic state and append-only events, bounded scope, no new dependencies or abstractions.
Recheck after full suite and diff review.

## Design

Parse named Markdown fields and strict option/must/want tables. Compute scores once in
the shared evaluator. CLI lint returns 0/1/2. Hook dispatcher translates findings to 2.
Read failures return 2; invalid content returns 1. Attributable write rejections log
decision.rejected; Bash day scans and citation checks only give feedback.
Question check reuses lint_file on today's cited ids and is reusable by M5. Morning gates
cite today's plan; C-n clarifications use Question, Context and unscored Options.
Routing uses the same evaluated fields, logs seat outcomes through the dedicated command,
and defaults to owner for any nonlocal or uncertain declaration.
File guard scope follows resolved target. Workspace anchors plus VCS commit_context
identify configured worktrees without core subprocess calls. Relevant Bash normalizes
first and scans the current day's decision files, following verdict lint's approach.

## Files

- cli/wuwei/decision.py: evaluation, file lint, rejection events, routing predicate.
- cli/wuwei/guards/decision.py: write guard, shared question/escalation check.
- cli/wuwei/workspace.py: shared workspace/repository/worktree scope helper.
- cli/wuwei/guards/verdict.py: shared interpreter table.
- cli/wuwei/commands/decision.py: lint and seat-only route command path.
- cli/wuwei/commands/event.py: reserve all decision. kinds.
- cli/wuwei/state.py: reserve decision_outcomes.
- tests/test_decision.py: in-process table and integration tests.
- tests/test_state.py: update the reserved namespace contract.
- specs/078-decision-lint/contracts/decision.md: record and command contract.

## Validation

For each story, add and run failing tests, implement minimally, rerun affected tests.
Run the full suite using the supplied interpreter, inspect diff and prohibited text.
No commits, pushes or gh commands. Extension hooks skipped as instructed.

## Review outcomes

Independent review and regression tests cover normalized path-valued Bash operands,
quoted decision-name fragments, current-day symlink escapes, seat-only routing events,
and reserved namespaces nested in JSON arrays (including tuple callback inputs).
The reservation walker now covers these arrays for all existing reserved namespaces.
No additional runtime dependencies or adapters were introduced.

The commit/push guard retains its VCS context-based target discovery. Substituting a
cwd-only scope check is not trivially compatible with its git -C and repository overrides.
