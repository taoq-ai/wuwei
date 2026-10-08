# Feature Specification: a path containing the word git is not a git mention

**Feature Branch**: `508-git-in-path`
**Issue**: #508 (light item: spec and tasks only)

## Promise

A workspace, worktree or launcher that lives under a path containing `git` or `gh` (a
`github` folder, a `~/git` directory, a worktree named `470-git-reads`) works exactly like
any other path: the launcher's `state get`, `pytest` and `ls` pass the hook. A real `git
push` is still refused.

## Root cause

`cli/wuwei/shell.py` line 69: `_GUARDED = re.compile(r'(?<![.\w])(?:git|gh)\b')` and the
same pattern in `mentions()` (line 91). A `git` inside a directory component still
matches, so `<dir>/508-git-in-path/bin/wuwei state get` reads as a git mention and
`_reject_mentions` (via `_unwrap`) refuses the call with "unaccounted git/gh mention".

## Fix

One shared word pattern: a name counts only as a whole word that is not a directory
component (no `/` later in the same word). The last path component still counts, so `/usr/bin/git push` and `find -exec /usr/bin/git` stay
mentions.

## Acceptance Scenarios

1. Given a workspace at a path containing `git` and `gh`, when the launcher's `state get`,
   `pytest` and `ls <workspace>` go through the PreToolUse hook, then each exits 0 under
   every posture.
2. Given `git push origin main` at that path, then it is still refused.
3. Given the suite run from such a path (this worktree is one), then green.

## Assumptions

- A directory named `git` or `gh` never runs anything, so a program under one (`/git/eval`)
  is no mention; the two `tests/test_shell.py` cases that pinned the opposite are removed.
  Dashed names (`git-push`, `508-git-in` outside a path) still match as before.
- Only the git/gh classifier (`_GUARDED`) skips directory components. `mentions()`
  keeps its original pattern: its callers include the #530 publish floor, where a floor
  word followed by `/` in an API path (`repos/o/r/branches/main/protection/x`) must
  still count as named (review F1).
- No new refusal is added (principle #530); no invariant row changes because no guard rule
  changes, only what counts as a mention.
