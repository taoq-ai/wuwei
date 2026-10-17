# Implementation plan: scratch-remotes

**Spec**: `specs/scratch-remotes/spec.md`
**Item**: scratch-remotes, tier full, goal G-2

## Technical context

- Stdlib-only Python 3.11+, runtime under `cli/wuwei/`, budget 3,000 lines. Main 9c637ab holds
  2,976 after free-lines-5 (#1123).
- `guards.git_push` refuses a force push, then a push whose targets meet `_default(root,
  origin(cwd))`, whatever the remote. `guards.bash` calls it with the words after `push` and the
  last `-C` value; it already computes `top`, the `-C` dirs joined, and `parts`, the segments.

## Design

1. `PLAIN`, a regular expression for the whole command: `git( -C <dir>)* push` and plain words or
   the options `-u -q -v -n --set-upstream --dry-run`.
2. `bash` passes `git_push` the whole command and the folder git runs in, `join(cwd, top)`.
3. When a target meets the default branch, `git_push` lets it pass only if there is a remote word,
   the command matches `PLAIN` and `scratch(base, remote)` holds; force refusals run first. A feature
   push never reads the shape or the config, and a refused push returns, so the shape is read at
   most once per command.
4. `scratch`: one `git config -z --get-regexp '^url\.|^remote\.'`; the remote's urls and pushurls,
   else the word; refuse on a matching `insteadOf` or `pushInsteadOf` prefix or any `receivepack` or
   `vcs`; each url must be a plain path or `file:///` URL whose realpath, joined to the checkout top,
   lies under `realpath(gettempdir())` with no `.git` or `.wuwei` in it or above it.
5. Re-vendor `.claude/wuwei/cli/wuwei/guards.py`; SECURITY.md and doors.md describe the exception.

## Constitution check

- Stdlib only (`tempfile`, `os.path.realpath`): pass. Runtime 2,987: pass, +11 (see spec, Size).
- Test first: 14 red on main, all green after.
- An auditor, not a gate: the change narrows a door and adds no refusal; nothing that passed on main
  is refused now.
- Security first: allowlist and fail closed; an unreadable config keeps the door.
