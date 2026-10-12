# Implementation Plan: pr claim on a remote-only PR creates its worktree

**Branch**: `879-claim-remote-pr` | **Date**: 2026-10-12 | **Spec**: [spec.md](spec.md)

## Summary

`pr claim` creates the item worktree through `worktree add --branch`, whose adapter call now
fetches a branch that is only on the remote. Claimed PRs with a worktree get a `fix` step that
the launch set resolves through `pr act` into the builder launch.

## Technical Context

Stdlib Python 3.11+. No new state field. One vcs port signature grows a `remote` argument.

## Constitution Check

- III: one path for an existing-branch checkout (`worktree_checkout`), one fix-round path
  (`pr_actions._fix`), one predicate for seat steps shared by `launch_set` and `next`.
- IV: tests first, red, then code.
- V: shortest diff; fork PRs refused with the exact commands.

## Files to edit

- `adapters/vcs/git.py` `worktree_checkout(repo, branch, path, remote=None)`: when `remote` and
  no local branch, `fetch --no-tags <remote> <branch>` first. `cli/wuwei/registry.py`,
  `tests/fakes/vcs.py`, `tests/test_adapters.py`: the signature.
- `cli/wuwei/workspace.py` `create_worktree`: pass `remote` to `worktree_checkout`.
- `adapters/code_host/github.py` `pr`: `head_repo` (the head repository's full name, None when
  gone).
- `cli/wuwei/shepherd.py` `claim_pr`: no local worktree on the branch: refuse a fork, else
  `commands.worktree.add` with `--branch <pr branch> --repo <repo>`.
- `cli/wuwei/pr_actions.py`: `act` sends a conflicted claimed PR to `_fix` with rebase
  feedback; `launch(root, ref)` returns the builder launch `act` prints, else the run.
- `cli/wuwei/derive.py` `offers`: for a claimed PR with a worktree, a build in flight is a
  `build next` step or nothing; a conflict or due shepherd activity is a `fix` step;
  `seated(data, launch)` names the steps the launch set resolves.
- `cli/wuwei/dispatch.py` `launch_set`, `resolve_offer` and `cli/wuwei/commands/next.py`
  `resolve`: use `seated`; `resolve_offer` sends `wuwei pr act` to `pr_actions.launch`.

## Verification

`python -m pytest -q` on every test file importing a changed module, under 3.12; the
worktree, pr, next and dispatch files under 3.11.
