# Implementation Plan: Commit and push guard

## Approach

Reuse guard discovery, shell normalization, config validation, state reads and the VCS
adapter. Put policy in `cli/wuwei/guards/commit_push.py`; Git hook translation and
installation in `cli/wuwei/commands/git_hook.py`. No new dependency or framework.

Extend the VCS port with commit context, push context, pushed-commit identities
and worktree hook configuration.
Commit context resolves repository selectors, effective identity and the common Git
directory. Push context supplies HEAD identity and resolved branch destinations.
A range read supplies every outgoing author and committer. Existing merge_base
verifies ancestry at the second anchor. The adapter never pushes.

Configuration adds repository identity. Fast-check results live in existing day state;
use its writer and reader instead of inventing another evidence store. Reserve
`fast_checks` with #11's namespace mechanism. A dedicated recorder runs configured
checks through the `checks.run(path, command)` port (`local` and `none` adapters),
clears old evidence before reruns, verifies HEAD, and records derived SHA/exit results.
`wuwei fast-checks [checkout]` is the driving CLI. No caller-supplied result is accepted.

## Constitution check

Stdlib runtime, 0/1/2 exits, policy shared by both anchors, test-first implementation,
atomic hook writes, and port-only external calls. No commit, push or gh commands.

## Test sequence

1. Port the source identity refusals as the first tests, then implement shared policy.
2. Test normalization, override selection, push destinations and fast-check evidence,
   then implement the Bash entry point and VCS reads with replay fixtures.
3. Test Git-hook policy, hook installation and failure handling, then connect worktree
   creation through workspace.create_worktree, keeping vcs.worktree_add a pure Git
   operation. Verify primary/sibling isolation in a disposable local clone. Use in-process fakes and subprocess shims only for executable integration.
4. Run the full suite, inspect the diff for bypasses, check style and path hygiene.

## Boundaries and alternatives

Do not run `git push --dry-run` to discover updates: it executes transport helpers and
hooks. Resolve the small supported subset using local reads and fail closed otherwise.
Do not duplicate policy in shell hook scripts. Keep scripts as CLI calls only.

## Deferred

See spec.md. Automatic gate scheduling and general deployment policy remain deferred.
