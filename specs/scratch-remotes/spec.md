# Feature Specification: the push door passes a push whose remote is a local path under the session scratch folder

**Feature branch**: `claude/scratch-remotes`
**Item**: scratch-remotes, tier full, goal G-2
**Input**: real-git acceptance for push-door items needs pushes to a scratch bare remote. The door
refuses them today, because a push to `main` meets the default-branch rule whatever the remote is,
so the git-globals builder ran its pushes from Python around the door (the owner accepted that one
run, `trust:`, and asked for this item).

## The promise in my words

The default-branch push door stops reading a push as a push to the repository when its remote is
plainly a scratch remote: a local path, a `file:///` URL, or a configured remote whose every url and
pushurl is one, that resolves (symlinks followed) under the temp folder where the session scratch
folder lives, and is not the working repository, its `.git`, any other checkout or any folder
holding `.wuwei`. Force pushes stay refused, and every other push keeps today's door. Files: the
guards, their tests, the route corpus, the vendored copy and SECURITY.md.

The acceptance scenarios, restated:

1. A scratch bare remote and a clone of it: `git push ../r.git main` and `git push origin main`
   (origin on the scratch path) pass the door. The planner runs this through the live door after
   the merge, once the vendored guards update; this build proves it by calling `guards.bash` at the
   head with real local repositories and no push.
2. `git push /home/user/wuwei/.git main`, a remote whose url is a symlink from scratch to the
   working repository, and `git push origin main` with origin on GitHub are each refused as before.

## Clarifications

- Q: How is the session scratch folder known? A: neither the hook payload (`session_id`,
  `transcript_path`, `cwd`, the tool input) nor the environment (`CLAUDE_*`) names it. The scratch
  folder lies under `tempfile.gettempdir()` (`/tmp/claude-0/...` here), so the rule reads the temp
  folder, resolved with `realpath`, and keeps out every path inside a checkout or a workspace.
- Q: Which paths count? A: the realpath must start with the temp folder's realpath plus `/`, and
  neither the path nor any folder above it may hold a `.git` or a `.wuwei` entry. That excludes the
  working repository and its `.git` (and a worktree's `.git` file), any checkout in the temp folder,
  and any workspace. A bare scratch remote has no `.git` above it.
- Q: How is the remote read? A: the first word after `push`. If `git config` holds
  `remote.<word>.url` or `remote.<word>.pushurl`, every such value must be scratch (git pushes to
  every pushurl, else every url; requiring both is a superset and fails closed). Otherwise the word
  itself is the path. A relative path is joined to the folder git runs in, which must be the top of
  a checkout, since git reads relative paths from the top (read from real git 2.43: `git fetch
  ../r.git` in a subfolder found `<top>/../r.git`).
- Q: How is url rewriting handled? A: the environment here sets
  `url.https://github.com/.insteadOf=git@github.com:` through the command-line config scope, so
  refusing on any `url.*` would make the exception useless. The rule refuses when any `insteadOf` or
  `pushInsteadOf` value is a prefix of a url it reads, which is when git would rewrite it.
- Q: Which commands qualify? A: only one plain command: the whole Bash command is
  `git( -C <dir>)* push` followed by plain words (letters, digits, `_ . / : + -`) and the options
  `-u`, `-q`, `-v`, `-n`, `--set-upstream` and `--dry-run`. That keeps out a `cd` before the push,
  an env prefix or wrapper, `GIT_DIR=`, `--git-dir`, `-c`, quotes, `$VAR`, `~`, backticks,
  `--repo=`, `-o`, `--receive-pack` and `--exec`, each of which could move the remote or the folder
  after the hook has read them. Any of these keeps today's door (an over-refusal, never a hole).
- Q: Does the exception lift the force door? A: no. Force pushes are refused in every form by the
  design; the scratch check runs after them and only empties the protected-branch set.

## How this fails

1. A push the guard reads as scratch lands somewhere real: a relative path resolved from the wrong
   folder, a symlink, a rewrite or a remote with a second url. Guarded by realpath, the checkout-top
   rule, the prefix rewrite check, all urls and pushurls, and the generated probe whose truth comes
   from real bash with a stub git and git's own url resolution: 0 holes over 368 commands.
2. A shell step between the hook's read and git's run moves the target (`cd`, `ln -s ... &&`, an
   env var). Guarded by the one-plain-command shape; a hook or another process that swaps a path is
   listed in SECURITY.md as not seen.
3. The extra read slows the hook or turns a loop quadratic on a long command, and a hook timeout
   lets the tool run. Guarded by reading the shape and calling `git config` only for a push that
   meets the default branch, which either passes as scratch or is refused, so it happens at most
   once per command; timed at 125 KB and 500 KB against main, and a test for a long first push
   followed by many short ones.

## Requirements

- FR-001: a plain one-line push to a local path, `file:///` URL or remote whose urls are those,
  under the temp folder and outside every checkout and `.wuwei`, passes the default-branch door.
- FR-002: the working repository, its `.git`, a symlink out of scratch, a path holding `.wuwei`,
  GitHub, a path outside the temp folder, a matching rewrite, a `receivepack` or `vcs`, an
  unreadable config, and any command that is not one plain push keep the push door.
- FR-003: force pushes stay refused for scratch remotes.
- FR-004: routes.json gets rows by code; no older row moves.
- FR-005: the vendored guards are byte-identical; SECURITY.md describes the exception and what it
  does not see.
- FR-006: the shell walk stays linear at 125 KB and 500 KB; no shape slower than main beyond noise.
- FR-007: runtime within 3,000 lines.

## Size

Runtime grows by 11 lines (2,976 on main 9c637ab, 2,987 at the head), over the item's estimate of
2 and budget of 3. The reading the brief asks for (a config read for named remotes, rewrites,
realpath, the checkout and workspace exclusion, and the one-command shape) does not fit in 3 lines
without squeezing. free-lines-5 (#1123) freed 21; this leaves 13 for push-refspecs and gh-args,
which free-lines-5's spec estimated at about 6 together.

## Assumptions

- The session scratch folder lies under `tempfile.gettempdir()` in the hook's environment, which is
  the harness's (Node's `os.tmpdir()` and Python read the same `TMPDIR`). Overturned if a harness
  places the scratchpad elsewhere; then the exception never applies (fail closed).
- No real remote of a working repository lives under the temp folder. Overturned by a team that
  keeps one there; SECURITY.md names it.
- A config-file `receivepack`, `vcs` or rewrite is read; a pre-push hook is not, the same class as
  an alias set with `git config` before the call (SECURITY.md).
- Pushing to a scratch remote's `main` is harmless, so the exception lifts only the default-branch
  set; the commit still reaches the repository only through a PR.
