# Commit and push contracts

## Configuration and evidence

Each `[[repos]]` table requires `identity = {name = "Builder", email =
"builder@example.test"}` to authorize a commit or push. The existing `path`,
`default_branch` (required) and `fast_checks` fields select the checkout, protected branch and
exact check names. A linked worktree is matched by its common Git directory.

The current day's state carries a `fast_checks` object:

```json
{"example/project": {"unit": {"sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "exit": 0}}}
```

Each configured command must have a record with the current HEAD and integer exit 0.
Run `bin/wuwei fast-checks [checkout]` to execute configured commands and record their
results through the existing state writer. The checkout defaults to the current directory.
The recorder accepts no SHA, exit or command override. `state.RESERVED` includes
`fast_checks`: generic state writes, including parent-object replacements, refuse with 1.
Before rerunning checks the recorder clears prior evidence for that repo. It reads HEAD
through VCS and checks it after each command; a changed or unavailable HEAD exits 2
without publishing passing evidence. Failed, missing or stale results refuse. Invalid data is exit 2.
Changing check names invalidates evidence. No configured checks means no check gate.
The later gate runner can schedule this recorder.

`checks.run(path, command, root=None)` returns a three-state `registry.Result`.
The default `local` adapter executes `/bin/sh -c <configured command>` in the checkout,
with inherited GIT_* selectors removed and a 300-second timeout. Process failures map
to 1; launch failures and timeouts map to 2. The `none` adapter reports unmeasured.
Outputs are not persisted in state or events. Each evidence record stores derived SHA
and exit 0, 1 or 2; only exit 0 authorizes a push.

## Driving adapters

`commit_push.GUARDS` registers `PreToolUse`, matcher `Bash`, `check(payload)`.
Guard results are `(0|1|2, reason)`; hook dispatch translates either refusal into
Claude Code's deny payload and exit 2. Unrelated plain commands do not read workspace
config or invoke a VCS adapter.

`bin/wuwei git-hook pre-commit` checks effective author and committer.
`bin/wuwei git-hook pre-push <remote> <url>` reads Git's four-field update lines from
stdin, checks HEAD identity, actual branch destinations, source SHA, check evidence
and ancestry. New branches have zero remote SHA. Deletions and non-HEAD updates
refuse. Missing ancestry is exit 2. These commands return raw policy exits 0/1/2.

`workspace.create_worktree` calls the pure `vcs.worktree_add` port, then installs
executable shims in `.wuwei/git-hooks`. Installation enables
`extensions.worktreeConfig` and sets `git config --worktree core.hooksPath` only in
the new linked worktree. It records the workspace in `<private git dir>/wuwei-workspace`.
The primary checkout and unrelated worktrees retain their hooks. Existing custom
hooks fail installation rather than being overwritten.

The shim locates the Git directory with `git rev-parse --absolute-git-dir`, exits 0
without a marker, and resolves the executable from `<workspace>/.wuwei/executable`.
`wuwei init` writes that pointer; #40 will rewrite it on `init --upgrade`. Missing
runtime paths produce exit 2 with an explanation. No plugin version path is embedded
in a shim. The CLI launcher uses `python3 -P -m wuwei` against package shadowing.

## VCS port additions

All additions use `registry.Result` and the existing trailing `root=None` convention.
No operation invokes commit, push, a transport helper, or the code host.

- `commit_context(repo, settings, env)`: returns `{path, common_dir, author, committer}`.
  `path` is the selected absolute Git directory, including the private directory of
  a linked worktree. This preserves HEAD selection even for GIT_DIR overrides.
  `settings` contains identity config keys; `env` holds explicit environment overrides.
  Inherited repository/config selectors are scrubbed before applying explicit values.
  Identities have `{name, email}`. Configured checkout comparison uses empty overrides.
- `head(repo)`: returns `{sha, author, committer}` from the actual HEAD object with
  replacement objects disabled. Both push_context and native pre-push use this read.
  Native pre-push takes destinations from hook input without inventing a refspec.
- `push_context(repo, remote, refspecs)`: returns `{head, updates, force}`. `head` has
  `{sha, author, committer}`; each update has `{source: sha, destination: full ref}`.
  The result also includes the named `remote`. Requires explicit refspecs, accepts
  the current branch as shorthand, and reads local push configuration without transport.
  Replacement objects are disabled so evidence describes the actual objects sent.
- `push_commits(repo, remote, destination, local_sha, remote_sha, default_branch)`:
  returns `{commits: [{sha, author: {name, email}, committer: {name, email}}]}`.
  Uses the supplied remote SHA for native hooks; null selects the remote-tracking
  destination. A zero/missing destination uses the merge-base with the remote-tracking
  default branch. Malformed or unavailable evidence exits 2. The allowlisted Git
  log read covers the complete base..local_sha range without replacement objects.
- `hooks_path(repo, path)`: requires a linked worktree, preserves custom hooks,
  enables worktreeConfig and writes worktree-local core.hooksPath. Returns `{git_dir}`.
  Common core.bare/core.worktree settings needing migration fail closed.

## Conservative subset and residuals

Use a named remote with the current branch or `HEAD:refs/heads/feature`. Bare
pushes fail closed with an explicit-refspec hint. No push.default emulation.
Short destination names after a colon, configured remapping of shorthand pushes,
matching/wildcard pushes, tag pushes, custom receive programs, and unsupported
options fail closed. Default and environment branches refuse.

Commit message/path arguments are distinguished from options. Explicit authors must
match. Amends and reused messages require `--reset-author`; skipping hooks refuses.
Git identity settings and author/committer environment overrides are checked against
workspace identity. GIT_DIR and GIT_WORK_TREE selectors are resolved by the VCS adapter. GIT_COMMON_DIR
overrides fail closed in both anchors because subsequent reads cannot safely preserve them.

Workspace discovery precedes all parsing: no workspace is exit 0; a workspace
whose configuration cannot be read is exit 2. Within a workspace, shared shell.mentions
checks raw text and text with quotes/backslashes removed for Git/GH together with a
guarded verb, config, or identity override. ANSI-C quoting, substitutions and dynamic
command names also reach the normalizer. Unrelated literal commands pass.
Relevant opaque interpreters, context-changing compounds and environment
clearing/unsetting fail closed. The shared shell normalizer remains unchanged.
`git add . && git commit -m x`, `-am`, `--fixup` and `--trailer` are supported.
Identity checks cover commit, merge, revert, cherry-pick, rebase, am, commit-tree,
notes, and any Git invocation carrying identity overrides. A push following a
commit-creating verb in the same compound refuses pending fresh HEAD evidence.
Config writes to core.hooksPath and extensions.worktreeConfig refuse, as do
remove-section/rename-section operations on core/extensions and rm of a
wuwei-workspace marker or the workspace executable pointer.
Commit/push `-n` and `--no-verify` refuse.

A Git hook does not receive the original force option, so it cannot distinguish a
force-marked fast-forward update from a plain fast-forward update. Bash refuses all
visible force flags; the native hook independently refuses non-fast-forward updates.
Interpreters constructing command names are a parser residual covered by native hooks
for identity, destinations, HEAD evidence and ancestry. Deliberately disabling hooks
outside guarded calls is outside this local enforcement boundary.

## Deferred

Automatic check scheduling belongs to the gate runner. Tag deployment policy belongs to the
deployment-ban issue; this feature refuses tag updates as unsupported. More general
Git refspec support requires authoritative remote resolution and its own tests.
F13 remains deferred: literal Git/GH mentions in echo/grep arguments can still
refuse; distinguishing them requires coordinated command-position parsing.

F5 is closed using #11's reserved-namespace mechanism and the dedicated check recorder.
