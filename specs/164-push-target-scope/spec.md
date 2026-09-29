# Feature Specification: Commit and push target scope

**Feature**: 164-push-target-scope
**Created**: 2026-09-29
**Status**: Draft
**Input**: Issue #164, design sections 4.1, 4.5 and 9.1; depends on #8 and #139.

## User Scenarios & Testing

### User Story 1: Enforce policy at the targeted repository (P1)

As an operator, I need commit and push rules to apply when an agent addresses a
configured repository or managed worktree from another directory.

**Independent test**: Invoke the guard with an outside cwd and literal repository targets.

**Acceptance scenarios**:

1. Given an outside cwd, when `git -C <configured repo> push --force origin main`
   is checked, then the guard refuses.
2. Given an outside cwd, when `cd <configured repo> && git push origin main`
   is checked, then the guard applies the same rules as from inside.
3. Given an unrelated outside repository, when its commit or push is checked,
   then the guard returns 0.
4. Given a managed worktree, when targeted through Git directory options,
   environment assignments, shell wrappers or subshells, then its workspace
   identity and push rules apply.
5. Given a safe commit or checked feature push, then changing the invocation
   directory alone does not cause refusal.

### User Story 2: Explain unavailable push context (P2)

As an operator, I need a refusal to explain repository state and a corrective action.

**Independent test**: Replay detached HEAD and failed Git context reads.

**Acceptance scenarios**:

1. Given detached HEAD, when push context is read, then exit 2 explains
   `detached HEAD; check out a branch before pushing`.
2. Given unavailable HEAD, invalid branch destination or failed Git reads,
   then exit 2 identifies the failed operation and a corrective action.
3. Given a VCS failure, then the guard preserves its reason.

### Edge Cases

Repeated and attached `-C`, relative directories, separate and equals directory
options, inherited repository environment, managed worktree anchors, multiple Git
commands, nested subshells, unknown directory stacks and malformed relevant shell
syntax. Irrelevant pytest, loops and exports pass without normalization.

## Requirements

- **FR-001**: Resolve each Git command's target before deciding workspace scope.
- **FR-002**: Apply existing identity, hook protection, branch and fast-check rules
  when cwd or a target is scoped; do not block unrelated outside repositories.
- **FR-003**: Use existing workspace discovery and managed worktree associations.
- **FR-004**: Inspect relevant shell calls only; uncertainty in scoped operations
  must fail closed with exit 2 and a reason.
- **FR-005**: Push context failures must explain state or the failing operation
  and how to proceed, rather than only a numeric Git exit.
- **FR-006**: Do not execute the submitted command or mutate the target repository.

## Success Criteria

- **SC-001**: All target forms in the guard regression table receive the same
  policy outcomes as equivalent direct invocations.
- **SC-002**: All unrelated repository and irrelevant command cases return 0.
- **SC-003**: All unavailable push context cases return actionable exit-2 reasons.

## Assumptions

- External configured repositories are discoverable through the existing workspace
  environment or installed anchor; no machine-wide repository index is introduced.
- Shell scopes and successful `cd` chains have explicit directory context. Other
  conditional directory changes retain possible paths and may require splitting.
- If parsing stops before a repository selector can be resolved, the relevant
  call fails closed; use a literal target in a separate command.
- Unknown directory stacks are not evaluated; scoped calls must use literal targets.
- Extension hooks are skipped as requested. Existing state and port contracts remain.

## Deferred

Full shell execution modelling and global repository discovery are outside this issue.
