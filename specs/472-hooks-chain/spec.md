# Feature Specification: worktree add chains WUWEI's git hooks with a repository's own core.hooksPath instead of refusing, and skips with a warning when it cannot chain

**Feature Branch**: `472-hooks-chain`

**Created**: 2026-10-04

**Status**: Draft

**Input**: GitHub issue #472, "fix(worktree): worktree add chains WUWEI's git hooks with a
repository's own core.hooksPath instead of refusing, and skips with a warning when it cannot
chain". Owner report on 0.15.0, 2026-10-04:

```
wuwei worktree add INVESTIGATE-D2-D3 --repo <org/repo>
git.hooks_path: could not run: custom core.hooksPath exists; refusing to replace hooks
wuwei worktree: git.hooks_path: could not run: custom core.hooksPath exists; refusing to replace hooks
(exit 2)
```

## Root cause (read and reproduced on main, 963a839)

`wuwei worktree add` (`cli/wuwei/commands/worktree.py:34`) calls
`workspace.create_worktree` (`cli/wuwei/workspace.py:719`), which runs `vcs.worktree_add`
and then `git_hook.install` (`cli/wuwei/commands/git_hook.py:21`). `install` writes the two
shims under `.wuwei/git-hooks/` and calls `vcs.hooks_path(worktree, shims)`
(`git_hook.py:48`). The adapter `adapters/vcs/git.py::hooks_path` (lines 499 to 522) then:

- `git.py:506-508`: reads `git config --get core.hooksPath` in the new worktree and raises
  `ValueError('custom core.hooksPath exists; refusing to replace hooks')` when it is set to
  anything else. `_operation` (`git.py:43-47`) turns that into exit 2, `create_worktree`
  raises through `guard.data`, and `wuwei worktree` exits 2.
- `git.py:510-514`: with no custom path, raises `existing default hooks would be disabled`
  when `$GIT_COMMON_DIR/hooks` holds any file not ending in `.sample`.
- `git.py:516-519`: raises when `core.bare` or `core.worktree` is set, because enabling
  `extensions.worktreeConfig` changes their meaning for every worktree.

Reproduced read-only with a scratch script outside the repository (a fresh `git init` with
`core.hooksPath = .husky`, a linked worktree, then the adapter's `hooks_path`):

```
custom hooksPath -> Result(exit=2, reason='git.hooks_path: could not run: custom core.hooksPath exists; refusing to replace hooks')
default hooks   -> Result(exit=2, reason='git.hooks_path: could not run: existing default hooks would be disabled')
```

Because `worktree_add` runs before `install`, the refusal also leaves the git worktree and
its branch behind, so a retry fails at `git worktree add -b`. husky, lefthook, pre-commit and
most team setups set `core.hooksPath` or install default hooks, so every such repository
stops the day at the first dispatch. The git-hook layer is defence in depth behind the
Claude Code PreToolUse guard, which already checks the seat's `git commit` and `git push`
(design spec 9.1, #237), so the refusal protects nothing.

A probe of the proposed chain on git 2.50 (scratch, real `git commit` and `git push`):
`git config --show-scope --get-all core.hooksPath` in the worktree prints `local\t.husky`
before, and `local\t.husky` plus `worktree\t<git-dir>/wuwei-hooks` after the per-worktree
write; the main checkout still reads `.husky`; a chained `pre-commit` ran WUWEI's stand-in
and then the repository's hook (relative path resolved from the worktree root); a chained
`pre-push` passed the same stdin to both, and a refusing WUWEI stand-in stopped the push
before the repository's hook ran.

## User Scenarios & Testing

### User Story 1 - A repository with its own hooks gets a worktree that runs both (Priority: P1)

The owner's repository sets `core.hooksPath` (or keeps real hooks in `.git/hooks`).
`wuwei worktree add` creates the worktree, and a commit there runs WUWEI's check and then
the repository's own hook.

**Why this priority**: it is the owner's report; without it no item worktree can be made in
such a repository.

**Independent Test**: `python -m pytest -q tests/test_worktree_command.py -k chain`.

**Acceptance Scenarios**:

1. **Given** a repository whose `core.hooksPath` is a directory holding an executable
   `pre-commit` that writes a marker, **When** `wuwei worktree add X` runs after the gate,
   **Then** it exits 0, `worktrees/X` exists, and a `git commit` in it runs WUWEI's
   `pre-commit` and then the marker hook.
2. **Given** the same repository with a repository `pre-push` that writes a second marker
   and a WUWEI check that refuses, **When** `git push` runs in the worktree, **Then** the
   push fails, WUWEI's hook ran, and the second marker is absent.
3. **Given** a repository with no `core.hooksPath` and an executable `.git/hooks/pre-commit`
   that writes a marker, **When** the worktree is added and a commit made, **Then** both
   hooks run.
4. **Given** either repository, **Then** the repository's own `core.hooksPath` is unchanged
   after `worktree add`; only the worktree's `config.worktree` names
   `<git-dir>/wuwei-hooks`.
5. **Given** a repository with a custom hooks path, **When** `wuwei doctor` runs, **Then**
   it has a `<name> git hooks` row with status `ok` and value `chained with <path>`.

---

### User Story 2 - A repository that cannot be chained still gets a worktree, except under strict (Priority: P1)

**Why this priority**: the second acceptance line; a hooks path that is a file, a missing
permission or a bare layout must not stop the day under guarded.

**Independent Test**: `python -m pytest -q tests/test_worktree_command.py -k "skip or strict"`.

**Acceptance Scenarios**:

1. **Given** a repository whose `core.hooksPath` names a regular file, under the guarded
   posture, **When** `wuwei worktree add X` runs, **Then** it exits 0, the worktree exists
   and is anchored (`<git-dir>/wuwei-workspace`), no `core.hooksPath` is set for the
   worktree, stderr carries one warning naming the reason and saying the Claude Code
   PreToolUse guard still checks `git commit` and `git push`, and today's events hold one
   `worktree.hooks_skipped` record with the worktree name and the reason.
2. **Given** the same repository under `security.posture = "strict"`, **Then** `worktree
   add` exits 2 and stderr carries the reason and a next step.
3. **Given** a repository with `core.bare` or `core.worktree` set, **Then** under guarded
   the worktree is created with the warning and the event, and the worktree identity is not
   written to the repository's shared config (a warning names why).
4. **Given** a repository that cannot be chained, **When** `wuwei doctor` runs, **Then**
   the `<name> git hooks` row is `warn` with the reason and a fix.

---

### User Story 3 - The owner picks chain, skip or replace (Priority: P2)

**Independent Test**: `python -m pytest -q tests/test_git_hook.py -k mode`.

**Acceptance Scenarios**:

1. **Given** no `[worktree]` table, **Then** `worktree.git_hooks` is `"chain"`.
2. **Given** `[worktree] git_hooks = "skip"`, **Then** `worktree add` sets no hooks path for
   the worktree, prints the warning, records `worktree.hooks_skipped` with reason
   `worktree.git_hooks = "skip"`, still enables `extensions.worktreeConfig` so the identity
   stays per worktree, and does not refuse under strict.
3. **Given** `[worktree] git_hooks = "replace"` and a custom `core.hooksPath`, **Then** the
   worktree's `core.hooksPath` is `.wuwei/git-hooks` (today's behaviour without the refusal).
4. **Given** `git_hooks = "other"`, **Then** loading the config fails like any invalid
   choice.

---

### User Story 4 - Repositories with no custom hooks behave as today (Priority: P1)

**Independent Test**: `python -m pytest -q tests/test_worktree_command.py tests/test_git_hook.py`.

**Acceptance Scenarios**:

1. **Given** a repository with no `core.hooksPath` and only `.sample` default hooks,
   **Then** the worktree's `core.hooksPath` is `.wuwei/git-hooks`, no `wuwei-hooks`
   directory is written, and no warning or event appears.
2. **Given** the existing tests in `tests/test_worktree_command.py`, **Then** they pass
   unchanged.

---

### User Story 5 - Chain scripts are regenerated (Priority: P3)

**Independent Test**: `python -m pytest -q tests/test_git_hook.py -k regenerate`.

**Acceptance Scenarios**:

1. **Given** a chained worktree whose `<git-dir>/wuwei-hooks/pre-commit` was deleted,
   **When** `wuwei init --upgrade` runs (not `--dry-run`), **Then** the script is back.
2. **Given** `wuwei init --upgrade --dry-run` (and so `wuwei doctor`), **Then** no worktree
   hook is written and no `Would upgrade` line is added for hooks.
3. **Given** a second hook install on the same worktree, **Then** the chain scripts are
   rewritten (no refusal when they differ).

### Edge Cases

- `core.hooksPath` is relative (husky's `.husky/_`): it resolves from the worktree root, as
  git does. The directory may not exist yet (husky creates it on install); that is not a
  reason to skip, because the chain script exits 0 when the repository's hook is absent or
  not executable, as git does.
- `core.hooksPath` starts with `~`: expanded as git expands it.
- `core.hooksPath = /dev/null` exists and is not a directory: skipped with the warning (the
  issue names "not a directory" as a skip reason).
- A hook name WUWEI has no check for (`commit-msg`, `post-checkout`, any file in the
  repository's directory): its chain script only runs the repository's hook.
- Any git command failing (not a git repository, git missing, a malformed config line):
  exit 2 as today; only the named layouts are a skip.

## Requirements

### Functional Requirements

- **FR-001**: When the repository's own `core.hooksPath` (any scope but `worktree`) is set,
  or its default hooks directory holds a file not ending in `.sample`, `worktree add` in
  `chain` mode writes `<git-dir>/wuwei-hooks/<name>` for `pre-commit`, `pre-push`,
  `commit-msg` and every hook file in the repository's directory, and sets the worktree's
  `core.hooksPath` to that directory. The repository's setting is never written.
- **FR-002**: Each chain script is plain sh (contracts/chain-hook.md): for a name with a
  WUWEI shim it runs the shim with the same arguments and stdin and stops with the shim's
  exit code when non-zero; it then execs the repository's hook of the same name with the
  same arguments and stdin, or exits 0 when that hook is absent or not executable.
- **FR-003**: When chaining is impossible (the hooks path exists and is not a directory, a
  permission error reading it or writing `wuwei-hooks`, `core.bare` or `core.worktree`
  set), the adapter returns exit 1 with the reason; `install` then, outside strict, prints
  one warning, records `worktree.hooks_skipped` and still anchors the worktree; under
  strict it raises with the reason (exit 2). Any other failure stays exit 2.
- **FR-004**: `[worktree] git_hooks` takes `chain` (default), `skip` or `replace`, is
  validated by the schema and documented in `docs/site/configuration.md`.
- **FR-005**: `worktree_identity` never writes to the repository's shared config: when
  `extensions.worktreeConfig` is off it returns exit 1 with the reason, and
  `create_worktree` prints it as a warning instead of failing.
- **FR-006**: `wuwei doctor` shows one `<name> git hooks` row per configured repository:
  `ok` for WUWEI hooks only, chained, replaced or an explicit skip; `warn` with the reason
  when chaining is impossible; `unmeasured` when git could not run.
- **FR-007**: `wuwei init --upgrade` (not `--dry-run`) re-runs the hook install for every
  `worktrees/<item>` that has a `.git` file, so the scripts are regenerated each time.
- **FR-008**: Every new reason names a next step (#362 shape); seat-facing text has no
  "you", person-facing text has no "the owner".
- **FR-009**: `worktree.hooks_skipped` is reserved (named in `EVENT_PRODUCERS`) and has the
  intended tier `nudge`.

## Success Criteria

- **SC-001**: The owner's command exits 0 on a repository with `core.hooksPath` set, and
  both hooks run on commit.
- **SC-002**: The full suite passes; the existing `tests/test_worktree_command.py` tests are
  unchanged.

## Assumptions

- The notes name no dry-run workspace; the failure was reproduced in a scratch repository
  outside the repo with the adapter on main, which is the same code path.
- WUWEI has native checks only for `pre-commit` and `pre-push` (`git-hook` accepts those
  two). `commit-msg` and the other names get a chain script that only runs the repository's
  hook; "run WUWEI's check first" applies where a WUWEI shim exists.
- "The repository's own setting" is the last `core.hooksPath` value from the system,
  global and local scopes, read with `git config --show-scope --get-all` (git 2.26 or
  newer). The `worktree` scope is WUWEI's own write and is ignored, which also lets a rerun
  on an existing worktree find the original path.
- A relative or absent hooks directory is chained, not skipped; only an existing
  non-directory is "not a directory".
- `core.bare` and `core.worktree` become a skip in every mode, including a repository with
  no custom hooks (today they are exit 2); this is the issue's list.
- Under strict the refusal comes after git created the worktree, as any install failure does
  today; the reason says to fix the layout or set `worktree.git_hooks = "skip"`, then remove
  the worktree and add it again. Checking before `git worktree add` would read the layout
  twice and is left out.
- `skip` is the owner's choice: it warns and records the event but never refuses, even
  under strict.
- `[worktree]` is not added to `templates/workspace/config.toml`: an omitted key takes the
  default, and adding it would make every existing workspace's doctor report a template
  change.
- `init --upgrade` prints nothing for a successful regeneration; a failure ends the upgrade
  with exit 2 and the reason after the config and pointer writes, like any other upgrade
  error.
- The permission case shares the skip branch with "not a directory"; it gets no dedicated
  test because a test running as root cannot provoke it.

## Deferred

- Making `install` replace a stale `.wuwei/git-hooks` shim on `init --upgrade` (today it
  refuses when the shim differs). Out of scope for #472.
