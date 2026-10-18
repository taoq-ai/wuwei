# Implementation plan: scratch-remotes

**Spec**: `specs/scratch-remotes/spec.md`
**Item**: scratch-remotes, tier full, goal G-2

## Technical context

- Stdlib-only Python 3.11+, runtime under `cli/wuwei/`, cap 3,000 lines. Main efcd9e7 holds 2,976
  after free-lines-5. This item's budget is +3; push-refspecs (+6) and gh-args (+5) follow.
- `guards.bash` reads git's options before the subcommand (git-globals) and calls `git_push(root,
  rest[i + 1:], here)` for a push. `git_push` refuses force pushes and any push whose destination is
  the default branch of the origin's repository, whatever the remote.
- `_git(cwd, *args)` runs `git -C cwd ...` with a 5 s timeout and returns stdout, or '' on error.

## Design

1. `TEMP = ()`, a module constant a probe can set; empty means `gettempdir()` and `/tmp`, read only
   for a scratch push (fix round 1).
2. `scratch(cwd, opts, args, command)` returns true only when:
   - the command is one plain git call (`[ \t]*git([ \t]+[\w./=@:+-]+)+[ \t]*`), so the shell's
     directory, environment and words are the ones the guard reads;
   - the first word after `push` is not an option, so it is the remote, and no word is `--exec` or
     `--receive-pack` or a prefix git reads as one;
   - git, with the session directory and the call's own options, says the shell is inside the work
     tree and gives a top and a common directory (`rev-parse --path-format=absolute
     --is-inside-work-tree --show-toplevel --git-common-dir`);
   - every push URL (`remote get-url --push --all`, else the word) is a path or `file:///` URL in
     plain characters, has no `.git` entry inside it, and `git --git-dir=<top>/<path> rev-parse
     --git-common-dir` names a common directory that, with realpath, lies below a temporary
     folder, is not the working repository's, and has no `.wuwei` in it or in a folder above it;
   - `git config -z --get-regexp` shows no `url.*.insteadof` or `pushinsteadof` whose value starts
     a push URL, no `remote.*.vcs` or `remote.*.receivepack`, and, for a word get-url does not
     name, no `remote.<word>.` key in any scope.
3. The call site in `bash`: a push `git_push` refuses passes when `scratch` holds. Placing the check
   after `git_push` keeps the git calls off every push that passes anyway, and lets a force push or
   delete to a scratch remote pass (push-refspecs needs `+` refspecs against one).
4. `here` (the raw `-C` value) stays the directory `git_push` reads the origin from; `scratch`
   hands every option to git instead, so git resolves `-C`, `--git-dir` and `--work-tree` itself.
5. Re-vendor `.claude/wuwei/cli/wuwei/guards.py`; SECURITY.md describes the rule and its holes;
   design.md and doors.md name the exception in one clause each.

## Evidence

- Tests in `tests/test_guards.py`, 79 item cases: 14 real-execution passes (the guard passes, then
  real bash and git push, and the bare remote has `main`), 48 refusals with the residual spellings
  and planted git directories, 10 work-tree cases, 2 global-config remotes, 3 config cases, a
  worktree case, and a moved `TEMP`.
- Route corpus on main and the head, 6 rows added by hand (no JSON escapes in them).
- Generated probe `specs/scratch-remotes/probe.py` under real bash, a stub git on PATH that logs and
  then execs git 2.43; holes are pushes the guard passes that move, create or delete a protected
  `main` (the code host stand-in, the workspace).
- Mutants: each check removed in its own `git archive` copy; the item's tests fail on each.

## Constitution check

- Stdlib only (`tempfile`, `os.path.realpath`): pass.
- Test first: the first test set ran 13 red on efcd9e7 before the change; fix round 1's tests ran
  18 red at the merged head before its change and 17 red at 6a5d00d; all 79 green at the head.
- Simplest: one helper, no new module, git itself reads urls, tops and common directories.
- Runtime: 3,004 against main's 2,986 (+18), under the 3,400 cap (spec Assumptions).
