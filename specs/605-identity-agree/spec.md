# Feature Specification: doctor and the commit and push guard agree on an empty repos.N.identity

**Feature Branch**: `605-identity-agree`
**Created**: 2026-10-09
**Status**: Draft
**Input**: GitHub issue #605 (light item)

## Promise

One rule in one place: an empty `repos.N.identity` gives the same answer in doctor's
identity row and in the commit and push guard, with the same reason and the same fix
command.

## Root cause

- `cli/wuwei/commands/doctor.py:313-326`: an empty identity whose checkout resolves a git
  identity is a `warn` ("empty; the repository resolves ..."), so doctor reads the
  workspace as fine.
- `cli/wuwei/guards/commit_push.py:15-20` (`_identity`, reached from line 441 and from
  `identity_check`): the same empty identity raises "missing or malformed identity" and the
  guard exits 2 on the first commit.

Two rules for one value, each written on its own.

## Direction chosen: fail in doctor

Setup (#356, `cli/wuwei/commands/setup.py:354-360`) writes each repository's git identity
into `repos.N.identity`, and `bin/wuwei worktree add` (`cli/wuwei/workspace.py:801-808`)
writes `repos.N.identity` into the item worktree and writes nothing when it is empty. So
the configured identity is the source of truth and an empty one is a setup gap, not a
value to guess. Resolving it in the guard would also add a git subprocess on the
PreToolUse path (the latency budget, design 10.6), and the guard would then check the
worktree against whatever git happens to say, which is no check. So doctor fails the row,
and both doctor and the guard take the reason and the fix from one helper,
`commit_push.unset_identity`. The fix is a command (#551):
`bin/wuwei config set repos.N.identity '{name = "...", email = "..."}'`, with the name
and email git resolves: doctor reads the checkout, the guard reuses the author of the commit
context it already read (no new git call); placeholders only when git has none. The rule
is `_identity`'s own check, so a malformed identity (for example the placeholders written
literally) fails in both too.

## Acceptance scenarios

1. Given `repos.0.identity` empty and a checkout whose git config has `user.name` and
   `user.email`, when doctor runs and a session commits, then doctor's identity row fails
   and the guard exits 2, both with the reason `repos.0.identity is empty or malformed` and
   the fix `bin/wuwei config set repos.0.identity ...` naming the resolved name and email.
2. Given `repos.0.identity` empty and no git identity, then both fail with the same reason
   and the same fix, word for word.
3. Given a malformed `repos.0.identity` (for example `name = "<name>"`), then both fail the
   same way (review finding F1).
4. Invariant I25 (design 9.2, `tests/test_invariants.py`): doctor and the commit and push
   guard agree on identity.

## Assumptions

- The guard already exited 2 on an empty identity; this item changes its words, not its
  outcome, so no new refusal is added under observe or guarded (#530). The reason names a
  command, not a host terminal, so it is no wall.
- The native git hook (`git_hook.py`) shares the guard's identity path and gets the same
  reason.
- Doctor's host `git identity` row (global git config) is left as it is.
- The invariant id is I25; a parallel item that also appends a row renumbers on rebase.

## Out of scope

Two plugin installs, the canonical `.wuwei/executable`, doctor's hooks row (#601), the
GitHub tracker auth fallback, deploy.deny patterns.
