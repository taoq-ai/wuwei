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

1. `TEMP = (gettempdir(), '/tmp')`, a module constant so a probe can move it.
2. `scratch(cwd, opts, args, command)` returns true only when:
   - the command is one plain git call (`[ \t]*git([ \t]+[\w./=@:-]+)+[ \t]*`), so the shell's
     directory, environment and words are the ones the guard reads;
   - the first word after `push` is not an option, so it is the remote;
   - git, with the session directory and the call's own options, gives a top and a common directory
     (`rev-parse --path-format=absolute --show-toplevel --git-common-dir`);
   - every push URL (`remote get-url --push --all`, else the word) is a path or `file:///` URL in
     plain characters, has no `.git` entry inside it, and `git --git-dir=<top>/<path> rev-parse
     --git-common-dir` names a common directory that, with realpath, lies below a `TEMP` folder, is
     not the working repository's, and has no `.wuwei` in it or in a folder above it;
   - `git config -z --get-regexp` shows no `url.*.insteadof` or `pushinsteadof` whose value starts
     a push URL, and no `remote.*.vcs` or `remote.*.receivepack`.
3. The call site in `bash`: a push `git_push` refuses passes when `scratch` holds. Placing the check
   after `git_push` keeps the git calls off every push that passes anyway, and lets a force push or
   delete to a scratch remote pass (push-refspecs needs `+` refspecs against one).
4. `here` (the raw `-C` value) stays the directory `git_push` reads the origin from; `scratch`
   hands every option to git instead, so git resolves `-C`, `--git-dir` and `--work-tree` itself.
5. Re-vendor `.claude/wuwei/cli/wuwei/guards.py`; SECURITY.md describes the rule and its holes.

## Evidence

- Tests in `tests/test_guards.py`: 12 real-execution passes (the guard passes, then real bash and git
  push, and the bare remote has `main`), 42 refusals with the residual spellings and planted git
  directories, 3 config cases, a worktree case, and a moved `TEMP`.
- Route corpus on main and the head, 4 rows added by hand (no JSON escapes in them).
- Generated probe under real bash, a stub git on PATH that logs and then execs git 2.43; holes are
  pushes the guard passes that move a protected `main` (the code host stand-in, the workspace).
- Mutants: each check removed in its own `git archive` copy; the item's tests fail on each.

## Constitution check

- Stdlib only (`tempfile`, `os.path.realpath`): pass.
- Test first: the first test set ran 13 red on efcd9e7 before the change; the final set runs 14
  red there (12 passes, the worktree pass, the moved `TEMP`) and 45 green (refusals main already
  gives), and all 59 green at the head.
- Simplest: one helper, no new module, git itself reads urls, tops and common directories.
- Runtime: 2,992, over the item's budget by 13 (spec Assumptions).
