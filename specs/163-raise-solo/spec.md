# Feature Specification: Solo PR raise

**Feature Branch**: `163-raise-solo`
**Created**: 2026-09-29
**Status**: Ready

## User Scenarios and Testing

### Worktree gate (P1)

Given gates passed at the item worktree HEAD while the configured repository path is on main, raising the PR proceeds using the worktree for HEAD, identity, diff and branch evidence.

### Reviewer policy (P1)

Given one eligible reviewer and `shepherd.min_reviewers = 1`, raising proceeds. Given zero eligible reviewers, it refuses and names `shepherd.min_reviewers`. The lead is eligible, including for a solo owner. An unmapped author email produces an error naming `shepherd.authors` and the email.

### Configuration and adapter (P1)

Every shepherd setting is present in the workspace template with comments and in the configuration page. With `adapters.code_host = "none"`, raising exits 2 with `code_host adapter is none; configure github`.

## Requirements

- Raise uses the item worktree recorded by brief creation and refuses absent worktree evidence.
- Reviewer selection uses a configurable minimum of one and counts the lead.
- Existing ports and gate policy remain the only source of external and verdict evidence.

## Assumptions

- A brief with a worktree records its resolved path on the item; a missing path is an unmeasured raise input.
- The author is excluded from review; a lead different from the author may satisfy the minimum alone.
- Existing author window and tie behavior applies once the minimum is reached.

## Deferred

- None.
