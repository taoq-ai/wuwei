# Implementation Plan: Commit and push target scope

**Branch**: `164-push-target-scope` | **Date**: 2026-09-29
**Spec**: [spec.md](spec.md)

## Summary

Resolve normalized Git targets before applying existing commit/push policy. Reuse
`workspace.scope`, `worktree_workspace`, `git_command` and the state guard's
directory operand handling. Preserve port-based repository reads.

## Technical Context

Python 3.11+, stdlib runtime, pytest development tests. Existing CLI and Git adapter;
no new dependencies, configuration, state, port operations or background discovery.
In-process guard tables use `tests/fakes/vcs.py`; adapter tests replay Git output.

## Investigation and Design

Read-only calls against the supplied operator dry-run workspace reproduced exit 0
for outside `git -C` force push and `cd` push; the inside force push returned 1.
The existing `check` exits before normalization based solely on cwd. Its non-Git
branch also rejects directory changes. `git_command` already handles repeated `-C`
and equals-form Git directory options, but needs separate-value forms.

Extend normalized commands with scope identifiers and following separators.
Track directories per scope, replacing cwd after successful `cd ... &&` and
retaining alternatives for other separators. Restore the parent on subshell exit.
Collect literal parser tokens to establish scope on parse failures without a second
parser. Unresolved target selectors fail closed. Prefer target-local workspace
discovery over a workspace selected only through the environment. Determine each command's workspace from effective
Git cwd and repository environment, with session scope as fallback. Skip outside
commands; then run existing identity and push checks unchanged. Ambiguous scoped
operations fail closed. Extend existing anchor discovery only if needed to accept
an explicitly targeted worktree Git directory.

For detached HEAD, accept symbolic-ref's documented missing result and explain the
required branch checkout. Make failed push context reads identify the operation
and corrective action without leaking raw stderr or executing input.

Alternatives rejected: a second shell parser, a global repository registry, or a
new target-resolution layer. They duplicate existing helpers or expand scope.

## Constitution Check

Pass before and after design: stdlib only; three-state exits; shared policy;
failing tests before implementation; no state or trust changes; no core subprocess;
no commit, push or gh commands. Existing hooks and fake ports remain the contracts.

## Project Structure

- `cli/wuwei/guards/commit_push.py`: target scope and directory tracking.
- `cli/wuwei/workspace.py`: target-local scope and explicit metadata anchors.
- `cli/wuwei/shell.py`: scope/separator metadata and observed literal words.
- `adapters/vcs/git.py`: actionable read failures and detached HEAD.
- `tests/test_commit_push.py`: target and relevance regression tables.
- `tests/test_vcs_guard.py`: replayed push failures.
- `docs/site/concepts.md`: explain target scope and corrective action.

## Validation

Run new guard and adapter cases red, implement, then run focused tests green.
Run the full suite with the task-provided interpreter using `python -m pytest -q`.
Inspect the diff for scope regressions, local paths, prohibited characters and
unnecessary abstractions. Re-run the supplied dry-run check without writes.
