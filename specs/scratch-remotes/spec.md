# Feature Specification: the push door passes a push to a git directory in a scratch folder

**Feature branch**: `claude/scratch-remotes`
**Item**: scratch-remotes, tier full, goal G-2
**Input**: real-git acceptance for a push-door item needs pushes to a scratch bare remote, and the
push door refuses every push to `main` whatever the remote. The git-globals builder ran those pushes
from Python around the door (the owner accepted that one run under `trust:` and asked for this item).

## The promise in my words

1. `guards.bash` passes a `git push` whose remote is a local repository in a scratch folder: a
   path or a `file://` URL, typed after `push` or held by a configured remote as its url.
2. "In a scratch folder" means: with symlinks resolved, the repository lies below the system
   temporary folder (`tempfile.gettempdir()`) or `/tmp`, where a session's scratch folder and a
   fresh `mktemp -d` folder live.
3. It never passes when the target is the working repository (the repository git runs in, a
   worktree's main clone included) or a path that holds `.wuwei` (the folder or any folder above
   it).
4. Every other push keeps today's verdict: a network remote, the GitHub origin, a path outside the
   temporary folders, a symlink from scratch out of it.

The acceptance scenarios, restated:

1. With a scratch bare remote and a clone, `git push ../r.git main` and `git push origin main`
   (origin's url the scratch path) pass the door, and real git then puts `main` in the bare remote.
2. `git push /home/user/wuwei/.git main`, a remote whose url is a symlink from scratch to the
   working repository, and `git push origin main` with origin on GitHub are each refused by
   `guards.bash`, as on main.

Outside (the item's Outside): any network remote.

## Clarifications

- Q: Where is the session scratch folder? A: the hook payload does not name it. Claude Code puts it
  under `/tmp/claude-<uid>/` here, and `mktemp -d` uses `$TMPDIR` or `/tmp`. The rule takes both
  `tempfile.gettempdir()` and `/tmp`, each resolved with realpath (macOS links `/tmp` to
  `/private/tmp`).
- Q: How does git read a relative remote path? A: from the top of the worktree, not the shell's
  directory. Real git 2.43 run from `c/sub` with `git push ../r.git g` wrote `<scratch>/r.git`, with
  a bare `c/r.git` beside it left empty; a remote whose url is `../r.git` reads the same. The rule
  joins a relative path to `git rev-parse --show-toplevel`.
- Q: Which url does a named remote push to? A: `git remote get-url --push --all <name>`: the
  `pushurl` values when set, else the url with `pushInsteadOf` and `insteadOf` applied, one line
  per URL git pushes to. Each must pass. The item's assumption read only `remote.<name>.url`; that
  misses a scratch url with a GitHub `pushurl` (a hole the probe shows: `pushurl` and `both` rows).
- Q: Can the guard trust the words it reads for the remote and the directory? A: only when the
  Bash command is one plain git call: the first word is `git` and every word is letters, digits
  and `./=@:-`, as the gh `--input` rule reads a plain gh call. A `cd`, `pushd`, `env -C`,
  `sudo -D`, a subshell, an env assignment (`GIT_DIR=`, `GIT_CONFIG_*`), `~`, `$`, a quote, an
  operator or a second command keeps the door: git would run in another directory or read another
  remote than the guard reads. git's own options before `push` (`-C`, `--git-dir`, `--work-tree`)
  are handed to the guard's git calls, so git itself reads the top and the remote's url.
- Q: Which word is the remote? A: the first word after `push`, when it is not an option. `git push
  -o x origin main` gives `x` to `-o`, so a rule that skipped options would read the wrong word.
  The rule refuses to read past an option; `git push ../r.git -u main` passes, `git push -u ../r.git
  main` keeps the door. push-refspecs reads refspecs, not the remote, so it is not blocked by this.
- Q: Do force pushes and deletes to a scratch remote pass? A: yes. The force refusal protects
  history on a shared branch; a scratch remote is no one's. push-refspecs needs `+` refspecs against
  a scratch remote for its real-git acceptance.
- Q: Which repository does git write? A: the remote must be a git directory (a bare repository or
  a `.git` path) with no `.git` entry inside it: the rule reads it with `git --git-dir=<path>
  rev-parse --git-common-dir`, so a worktree path or a non-bare clone keeps the door, and a
  `commondir` file pointing elsewhere is read. The common directory is the one checked, since refs
  live there.

## How this fails

1. A cwd or wrapper trick makes git push from another repository than the one the guard reads:
   `cd ../g && git push origin main` from a scratch clone, where `g`'s origin is GitHub. Guarded by
   the plain-call rule; the generated probe crosses 15 directory-changing spellings with every
   remote and session directory.
2. A remote name's real push URL differs from its url (`pushurl`, `pushInsteadOf`, a second push
   URL) and the push goes to the code host. Guarded by reading `git remote get-url --push --all`.
   Config written before the call can also send a typed path elsewhere: a `url.<base>.insteadOf`
   or `pushInsteadOf` whose value starts the path, `remote.<name>.vcs` (a remote helper) or
   `remote.<name>.receivepack` (the command git runs for the push). Guarded by refusing the rule
   when `git config --get-regexp` shows a rewrite that starts any push URL, or any helper or
   receive-pack key. Holes that stay: an exec path or receive hook that runs another push (a
   program the guard never reads, like any script).
3. A path spelling resolves to one repository for the guard and another for git: `%xx` in a
   `file://` URL, `file://localhost/`, `//`, `/./`, `/../`, a symlink, a worktree path, or a plain
   folder next to a `<path>.git` link (git's `enter_repo` tries `<path>/.git`, `<path>`,
   `<path>.git`). Guarded by refusing `%`, `~`, `$` and a host in the URL, resolving with realpath,
   reading the target as a git directory, and refusing a target with a `.git` entry inside it
   (real git 2.43 entered a planted `p.git/.git` link before `p.git`, and a `q.git` link beside a
   plain folder `q`). Hole that stays: a race that plants such an entry between the guard's read
   and the push; it needs files written by a concurrent process and writes only local refs, which
   `git update-ref` writes anyway.

## Requirements

- FR-001: `guards.TEMP` names the temporary folders; `guards.scratch` reads one plain git call's
  remote and returns true only when every push URL is a git directory below one of them, not the
  working repository's common directory, with no `.wuwei` in it or above it, and no config
  rewrites a push URL or names a remote helper or receive-pack command.
- FR-002: `guards.bash` passes a push the push door refuses when `scratch` reads it as local.
- FR-003: every other push keeps its verdict: the route corpus on main and the head moves no row.
- FR-004: routes.json gets the acceptance rows the corpus can hold (its cwd `/repo` is no scratch
  folder, so they meet the door).
- FR-005: the generated probe under real bash and real git shows 0 holes at the head.
- FR-006: SECURITY.md describes the rule and its residual holes.
- FR-007: the vendored copy matches.

## Breaking

None. The change only passes commands that were refused (pushes to scratch git directories).

## Assumptions

- The scratch folder and fresh temporary folders lie below `gettempdir()` or `/tmp`. Overturned if
  a harness puts its scratch folder elsewhere (the rule then refuses as before: over-refusal only).
- Writing a local repository's refs is not a code host boundary: the agent can run `git update-ref`
  in any local repository. The working-repository and `.wuwei` exclusions are kept because the
  promise names them, and they stop a push into the workspace clone's hooks.
- Runtime lines: measured 2,992, +16 over efcd9e7, against an estimate of +2 and a budget of +3. The
  budget did not price the plain-call rule, the push URLs, the top-relative path, the git
  directory read or the config check. Each check removed on its own (12 mutants) fails the item's
  tests, and the tests that fail plant or spell a push real git sends past the check (How this
  fails 1 to 3). The cap leaves 8 lines for push-refspecs (budget 6) and gh-args (budget 5), 3 short
  of their budgets, unless #1134 (a 3,400 line budget) merges. Overturned if the owner prefers
  fewer checks to the budget: the config check (3 lines) is the cheapest to drop, since config
  written before the call is a hole SECURITY.md already lists.

Rollback: revert the commit; no data or config migrates.
