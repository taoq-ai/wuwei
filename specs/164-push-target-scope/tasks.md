# Tasks: Commit and push target scope

## Setup

- [X] T001 Reproduce supplied dry-run failures read-only and inspect shared helpers in cli/wuwei/guards/commit_push.py and cli/wuwei/workspace.py.
- [X] T002 Record requirements and design in specs/164-push-target-scope/spec.md and plan.md.

## US1: Target repository scope

Independent validation: table tests return 0, 1 and 2 for outside invocation,
configured repositories, managed worktrees, wrappers and ambiguous scoped calls.

- [X] T003 [US1] Add target, directory, scope and relevance tests in tests/test_commit_push.py; run and verify expected failures.
- [X] T004 [US1] Resolve normalized command targets using shared scope helpers in cli/wuwei/guards/commit_push.py, cli/wuwei/shell.py and cli/wuwei/workspace.py; pass the guard tables.

## US2: Actionable push context

Independent validation: replay detached HEAD and other read failures and assert
exit 2 with operation/state and corrective action.

- [X] T005 [US2] Add failing push-context reason tests in tests/test_vcs_guard.py and reason propagation in tests/test_commit_push.py.
- [X] T006 [US2] Explain unavailable push context in adapters/vcs/git.py; pass adapter and guard tests.

## Validation and Documentation

- [X] T007 Document scope and corrective actions in docs/site/concepts.md.
- [X] T008 Run the full pytest suite, repeat read-only reproduction, and review changed files for hygiene; record results in specs/164-push-target-scope/tasks.md.

## Dependencies and Execution

T001 -> T002 -> T003 -> T004 -> T005 -> T006 -> T007 -> T008.
US1 is the first deliverable; US2 is independent but runs sequentially to keep the
change reviewable. Guard and adapter test authoring could run in parallel in
separate files; this implementation uses one seat. No extension hooks are run.

## Verification Results

- Initial scope table: 89 expected failures before implementation.
- Push diagnostics: 7 expected failures before implementation.
- Review reproductions covered environment-selected workspaces, obsolete cwd,
  conditional cd failures and backgrounded command lists; each failed before its fix.
- Final full suite: `5060 passed, 2 skipped in 85.19s (0:01:25)`.
- Read-only operator fixture: outside `-C` force push returns 1; outside cd and
  subshell default-branch pushes return 1; unrelated outside push returns 0.
- `git diff --check` passed. Added lines and feature artifacts contain no local
  machine paths, em-dashes or emojis. No state, config keys or trust producers added.
