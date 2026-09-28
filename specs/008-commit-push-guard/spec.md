# Feature Specification: Commit and push guard

**Feature Branch**: `008-commit-push-guard`
**Created**: 2026-09-28
**Status**: Accepted for implementation
**Input**: Issue #8, including normalization, second-anchor and ports amendments.

## User Scenarios & Testing

### User Story 1 - Preserve repository identity (Priority: P1)

As an owner, I require commits and pushes to use the repository's configured identity.
Independent test: in-process guard tables with fake VCS results.

1. Given a configured owner, `git -c user.email=x commit` is refused.
2. Effective author is checked before effective committer for all commit-creating
   verbs and any Git invocation carrying identity overrides. Push checks HEAD and
   the author and committer of every outgoing commit.
3. Matching identity permits commit; missing configuration or unreadable VCS data
   exits 2. Explicit author overrides and reused commit authors cannot bypass checks.

### User Story 2 - Push only checked feature HEADs (Priority: P1)

As an owner, I require non-forced feature pushes with current fast-check evidence.
Independent test: push tables and state records for matching, stale and failed checks.

1. `git push --force-with-lease` and `sh -c 'git push --force'` are refused.
2. `python3 -c "import subprocess; subprocess.run(['git','push','-f'])"` is refused.
3. Pushes to the configured default branch, including destination refspecs, are refused.
4. Fast checks recorded for an older HEAD do not authorize the current HEAD.
5. Missing or failed configured checks refuse push; malformed evidence exits 2.

### User Story 3 - Enforce at Git hooks (Priority: P1)

As an owner, I require worktrees created by WUWEI to enforce the same policy even
when shell analysis cannot see a command. Independent test: installed executable
hook shims with recorded port output and in-process policy tests.

1. Worktree creation installs pre-commit and pre-push hooks invoking the CLI.
2. Pre-commit enforces effective identity; pre-push checks actual update destinations,
   current HEAD, identity, ancestry and fast checks without parsing a shell command.
3. Installation or evidence failure exits 2; non-fast-forward updates are refused.

## Requirements

- FR-001: Return 0 outside a WUWEI workspace. Inside one, establish relevance with
  shared `shell.mentions` before calling `shell.normalize`: Git or GH plus commit, push, merge,
  revert, cherry-pick, rebase, am, commit-tree, notes, config, or an identity override.
  Unrelated commands return 0 without parsing; relevant ParseError is exit 2.
  Relevance includes quote/backslash-obfuscated names, ANSI-C quoting and dynamic
  name construction. Hook-pointer removal is also relevant. Keep extra
  interpreter/context policy local to this guard; normalization behavior is unchanged.
- FR-002: Wrappers, subshells, git options and environment overrides cannot bypass policy.
- FR-003: Runtime is stdlib-only; Git policy reads and configuration writes go
  through VCS ports. The native shim uses only `git rev-parse --absolute-git-dir`
  to locate its worktree marker before resolving the CLI.
- FR-004: Results are `(0|1|2, message)`; errors fail closed and explain why.
- FR-005: Each configured fast check needs an exit-0 result tied to repository and HEAD.
  `fast_checks` is reserved state. Only the dedicated recorder, which executes the
  configured commands itself, writes evidence; generic state writes refuse it.
- FR-006: Git hooks and PreToolUse call the same identity and push policy functions.
- FR-007: Unsupported dynamic or ambiguous operations fail closed, never assume a target.

## Assumptions

- Expected identity is `repos[].identity.name` and `.email` in workspace config,
  independent of command-line and Git configuration overrides. Missing identity blocks.
- `repos[].default_branch` is required for every configured repo. Config check exits
  1 when absent; guard configuration read/validation failures exit 2. Only
  FileNotFoundError from workspace discovery means outside scope and exits 0.
- Fast-check evidence uses today's state `fast_checks[repo name][check command]` with
  `sha` and integer `exit`. `wuwei fast-checks [checkout]` resolves the configured repo,
  clears its prior evidence, executes its configured commands through the checks port,
  and records results only if HEAD remains unchanged. It accepts no SHA or exit inputs.
  No configured checks means no check gate. Generic `state set` and `write_state`
  cannot change the reserved namespace, including through parent-object replacement.
  The local adapter runs commands with `/bin/sh` in the supplied checkout, with a
  300-second timeout per check. Nonzero process exits map to findings (1); execution
  failures map to unmeasured (2). Check output is not written into state or events.
- Explicit pushes support `git push [-u] <remote> <current-branch>` and
  `HEAD:refs/heads/<destination>`. Default and environment branch patterns refuse.
  Bare pushes fail closed with a hint; no push.default emulation. Git validates
  branch refs and boolean configuration. Deletes, tags, wildcard/matching pushes,
  custom receive programs, and ambiguous configuration fail closed. Tag deployment
  policy belongs to the deployment-ban issue.
- Configured repo paths identify both the primary checkout and its linked worktrees
  through Git's common directory. GIT_DIR/GIT_WORK_TREE selectors are resolved by VCS;
  GIT_COMMON_DIR overrides are unsupported and fail closed at both anchors.
- The core `workspace.create_worktree` caller invokes the pure `vcs.worktree_add`
  port, then installs hooks. Installation enables extensions.worktreeConfig and
  writes `core.hooksPath` with `--worktree` only in the new worktree. The primary
  checkout and other worktrees keep their hook settings. Existing custom hooks
  are not silently overwritten. A marker in the private Git directory records
  the workspace; the shim exits 0 without that marker.
- `wuwei init` records the absolute CLI path in `.wuwei/executable`. Shims read it
  at invocation, never embed a plugin version path, and report exit 2 when missing.
  Issue #40 must rewrite this pointer during `wuwei init --upgrade`.
- Push identity reads use remote_sha..local_sha for existing native-hook updates,
  the remote-tracking destination for Bash pushes, or a merge-base with the
  remote-tracking default branch for new branches. Missing range evidence exits 2.
- Normal `git add . && git commit -m x`, `-am`, `--fixup` and `--trailer` are
  supported. Commit/push `-n` and `--no-verify` are refused. Guarded config writes
  to core.hooksPath and extensions.worktreeConfig, including set/unset/unset-all/worktree
  forms, are refused. Removing or renaming core/extensions sections and removing
  a wuwei-workspace marker or the workspace executable pointer are refused.
- A push after any commit-creating verb in the same compound is refused because
  pre-execution HEAD evidence cannot cover the resulting commit. Run push separately
  after recording checks for the new HEAD.
- Native pre-push reads HEAD identity directly through vcs.head and obtains actual
  destinations only from hook input. It does not synthesize a refspec.
- Git hooks cannot detect a force flag on a genuinely fast-forward update; Bash refuses
  all force flags, while pre-push independently refuses non-fast-forward updates.
- Disabling Git hooks or changing trusted workspace config outside guarded commands is
  outside this local enforcement boundary.
- F13 is an accepted false positive: `echo "git push"` inside a workspace still
  fails closed. Command-position disambiguation remains deferred. Ordinary unrelated
  substitutions such as `echo $(date)` and read-only redirect targets remain irrelevant;
  dynamic command or Git verb construction remains relevant through `shell.mentions`.

## Success Criteria

- All issue acceptance and bypass cases have passing table tests for exits 0, 1 and 2.
- Both anchors refuse wrong identities, unsafe pushes and stale check evidence.
- The complete repository test suite passes without network or commit/push operations.

## Known dependencies and deferred work

- Issue #40 owns rewriting `.wuwei/executable` during `wuwei init --upgrade`.
- F13: literal Git/GH mentions in echo/grep arguments still fail closed. Restricting
  relevance to command positions requires a coordinated parser change and is deferred.

- Automatic gate-runner scheduling of checks; deployment-ban policy for tag pushes.
- General-purpose Git refspec/configuration support beyond safely resolved HEAD updates.
