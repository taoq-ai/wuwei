# Feature Specification: Seats commit in a WUWEI worktree without setting git identity by hand

**Feature Branch**: `246-worktree-identity`

**Created**: 2026-09-30

**Status**: Draft

**Input**: GitHub issue #246, "fix(team): seats can commit in a WUWEI worktree without
setting git identity by hand". Design spec sections 4.1, 4.3, 4.5 and 5.2. Builds on #164
(commit guard identity check), #216 (`wuwei worktree add`) and #225 (CLI arguments are data
to the state guard); all merged on `main`.

## Evidence (fourth operator dry run on the v0.6.1 asset, 2026-09-30)

Reproduced read-only through `bin/wuwei hook PreToolUse` in the dry-run workspace, and in a
fresh scratch workspace built the same way (template-derived `[[repos]]` entry, no global
git identity, `wuwei worktree add`, then `git commit -qm x` through PreToolUse).

1. The first builder commit in a worktree made by `wuwei worktree add` is refused with
   `GIT_AUTHOR_IDENT differs from configured identity`. The operator worked around it
   twice, both off the documented path: the builder passed `git -c user.name=... -c
   user.email=... commit`, and the owner ran `git config user.name/user.email` in the
   main checkout. Root cause: `workspace.create_worktree`
   (`cli/wuwei/workspace.py` lines 433 to 445) calls `vcs.worktree_add` and
   `git_hook.install`; `install` reaches `hooks_path` (`adapters/vcs/git.py` lines 480 to
   503), which enables `extensions.worktreeConfig` and writes only `core.hooksPath` to the
   worktree config. Nothing writes `user.name` or `user.email`, so git falls back to the
   host's user and hostname. The commit guard compares that fallback, read by
   `commit_context` (`adapters/vcs/git.py` lines 387 to 395), with `repos[].identity` from
   `config.toml` in `identity_check` (`cli/wuwei/guards/commit_push.py` lines 21 to 34)
   and refuses. After `git config --worktree user.name/user.email` with the configured
   values in that worktree, the same payload passes the commit guard, and the main
   checkout's config stays untouched.
2. The refusal text (`commit_push.py` line 27) says what differs but not what fixes it,
   and the template comment for `identity` (`templates/workspace/config.toml` line 11)
   says only "Required by Git guards".
3. `echo 'Read instructions <workspace>/.wuwei/generated/agents/x.md'` is refused by the
   state guard with "State and config files are protected". So are
   `echo .wuwei/generated/agents/arch.md`, `printf '%s\n' .wuwei/generated/agents/arch.md`,
   `cut -c1 .wuwei/generated/agents/arch.md` and `tr a b .wuwei/config.toml`, while
   `cat`, `grep` and `wc` on the same path pass. (`echo 'see .wuwei/generated/...'` with a
   relative path already passes on `main`, because the joined argument's first path
   segment is `see .wuwei`, not `.wuwei`; an absolute path or a bare path hits the rule.)
   Root cause: `_write_targets` (`cli/wuwei/guards/protect_state.py` lines 309 to 351)
   exempts only its own short reader list `('cat', 'head', 'tail', 'less', 'jq', 'grep',
   'wc')` at line 344; every other program falls through to `return protected`
   (line 351), which treats each argument that resolves to a protected path as a write
   target. `echo`, `printf`, `cut`, `tr` and `rg` are in the module's reader list
   `_READERS` (line 74, from #222) but not in that local tuple.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A builder commits in a fresh item worktree (Priority: P1)

The owner copies the `[[repos]]` example from the config template, including its example
identity, and runs `wuwei worktree add <item>` after the morning gate. The builder seat
runs a plain `git commit` in that worktree; the commit guard passes with no manual git
configuration.

**Why this priority**: every item's first commit hits it; today the day needs an
undocumented workaround before any builder can commit.

**Independent Test**: real git repository with no identity configured anywhere, a
workspace config whose `identity` line is the template's example, `wuwei worktree add`,
then `git commit -qm x` through PreToolUse in process; exit 0.

**Acceptance Scenarios**:

1. **Given** a worktree created by `wuwei worktree add` from a template-derived config,
   **When** `git commit -qm x` goes through PreToolUse in that worktree, **Then** the hook
   exits 0 with no manual git config.
2. **Given** the same worktree, **When** its config is read, **Then** `user.name` and
   `user.email` equal `repos[].identity` in the worktree scope, and the repository's main
   checkout has no `user.name` or `user.email` written by WUWEI.
3. **Given** a repository entry whose `identity` is left empty, **When** `wuwei worktree
   add` runs, **Then** the worktree is created as today and no identity is written (the
   commit guard keeps refusing with its existing "missing or malformed identity" reason).

---

### User Story 2 - A mismatched identity refusal names its fix (Priority: P1)

A seat whose commit identity differs from the configured one is told how to fix it.

**Why this priority**: the refusal is the only thing the seat sees; without the fix named,
the operator reaches for `-c` overrides or edits the main checkout.

**Independent Test**: `identity_check` with a differing author or committer returns a
reason naming `wuwei worktree add` and `git config user.name` / `git config user.email`
with the configured values; the same reason appears through PreToolUse.

**Acceptance Scenarios**:

1. **Given** a commit with a mismatched author or committer identity, **When** the commit
   guard (PreToolUse or the native pre-commit hook) refuses it, **Then** the reason keeps
   its `GIT_AUTHOR_IDENT` / `GIT_COMMITTER_IDENT differs from configured identity` prefix
   and names `wuwei worktree add` and `git config user.name <name>` then
   `git config user.email <email>` in this worktree, with the configured values.
2. **Given** the config template, **When** the owner reads the `identity` example, **Then**
   its comment says the commit guards compare commits against it and that
   `wuwei worktree add` writes it to each item worktree's git config.

---

### User Story 3 - Reading or quoting a protected path is not a state write (Priority: P2)

A seat or the planner echoes or prints text that names a file under `.wuwei/generated/`
(for example the instructions path it was given). The state guard lets it through; a
redirect into that path is still refused.

**Why this priority**: it blocks harmless probes and messages; the dry run hit it once.

**Independent Test**: PreToolUse Bash payloads in a secured test workspace, in process.

**Acceptance Scenarios**:

1. **Given** `echo 'see .wuwei/generated/agents/arch.md'` through PreToolUse, **Then**
   exit 0; the same for the bare path, for an absolute `<workspace>/.wuwei/generated/...`
   path, and for `printf`, `cut`, `tr` and `rg` naming a protected path.
2. **Given** `echo x > .wuwei/generated/agents/arch.md` through PreToolUse, **Then** exit 2.
3. **Given** `echo x | tee .wuwei/config.toml` or `echo .wuwei/config.toml | xargs rm`,
   **Then** still refused (the `tee` target rule and the spec 4.5 `xargs` bypass row are
   unchanged).

### Edge Cases

- The configured identity contains a newline, carriage return, NUL, `<` or `>`, is empty
  after stripping, or starts with `-`: the vcs operation refuses with exit 2 before
  spawning git, and `wuwei worktree add` exits 2 with that reason (the worktree and its
  hooks already exist; the refusal text of Story 2 names the manual fix).
- `--repo <name>` selects one of several repositories: the selected entry's identity is
  written.
- A reader with an output redirect (`echo x >> .wuwei/config.toml`, `printf x
  >.wuwei/days/<day>/state.json`) stays refused: redirect targets are checked from
  `command.writes`, independent of the program.
- A reader piped into an executor (`echo .wuwei/config.toml | sh`, `... | xargs rm`)
  stays refused, by the parser and the owner-action rule that run before
  `_write_targets` (today: exit 2, "missing shell -c script" and "Opaque owner action").
- A reader argument starting with `~` (`grep ~ notes.md`) is no longer refused with "use a
  literal path instead of tilde expansion", since reader arguments are no longer resolved
  as paths.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `wuwei worktree add` MUST write the selected repository's configured
  `identity` (`user.name`, `user.email`) to the new worktree's worktree-scoped git config
  (`git config --worktree`), after the managed hooks are installed, when both values are
  non-empty.
- **FR-002**: It MUST NOT write identity to the repository's shared or main-checkout
  config, and MUST NOT change the command's JSON output (`branch`, `path`) or its exits.
- **FR-003**: The vcs port MUST expose the identity write as one operation with a closed
  argv allowlist (`config --worktree user.name|user.email <value>`) and MUST refuse
  malformed values (empty, newline, carriage return, NUL, `<`, `>`, leading `-`) with exit
  2 and no git call.
- **FR-004**: The commit guard's author/committer mismatch reason MUST keep its current
  prefix and name the fix: `wuwei worktree add`, or `git config user.name <name>` and then
  `git config user.email <email>` (as separate commands) in that worktree, with the
  configured values shell-quoted.
- **FR-005**: The config template comment on the `identity` example MUST say that the
  commit guards compare commits against it and that `wuwei worktree add` writes it to each
  item worktree's git config; the `repos.identity` row in `docs/site/configuration.md`
  MUST say the same in one sentence.
- **FR-006**: The state guard MUST NOT treat the arguments of a reader program (the
  module's `_READERS`: `grep`, `rg`, `echo`, `printf`, `head`, `tail`, `wc`, `cut`, `tr`;
  plus `cat`, `less`, `jq`, which are exempt today) as write targets. Redirects on those
  commands MUST still be checked.
- **FR-007**: Every other state guard rule MUST stay as it is: targets of `tee`, `cp`,
  `mv`, `rsync`, `dd`, `rm`, `ln`, `install`, `truncate`, `sed -i`; the generic fallback
  for other programs; the parse-error branch; the interpreter opacity check; the
  owner-action rule; and the spec 4.5 bypass rows.

### Key Entities

- **Worktree identity**: `user.name` and `user.email` in the item worktree's
  `config.worktree`, copied from `repos[].identity`. No new state key, event, or config key.
- **vcs port operation `worktree_identity(repo, name, email)`**: the one new port call.

## Success Criteria *(mandatory)*

- **SC-001**: The three acceptance scenarios of issue #246 pass as automated tests through
  PreToolUse in process.
- **SC-002**: The full suite passes with no existing assertion weakened; existing tests
  change only where the port contract table lists the new operation.
- **SC-003**: No new module, dependency, config key, state key or event kind.

## Assumptions

- The issue's first scope bullet ("the config template's example identity `Builder
  <builder@example.test>` is what a copied template yields") needs no change to the
  example values; the template keeps them, and the acceptance test derives its identity
  line from the template itself, so the test tracks the template.
- The identity is written with `git config --worktree`, which `hooks_path` already makes
  valid by enabling `extensions.worktreeConfig` on a verified linked worktree. The write
  therefore runs after `install`, in `create_worktree`, the one shared spot every worktree
  creation goes through. Writing to the shared repository config would change the owner's
  own checkout, which the issue does not ask for.
- An empty configured identity is not an error for `worktree add`: the field defaults to
  empty in the config schema, existing workspaces and tests configure repos without it,
  and the commit guard already refuses every commit there with its own reason. Failing
  worktree creation for it would be a new refusal the issue does not ask for.
- The refusal names the plain `git config user.name` form the issue names, not
  `--worktree`: plain works in every checkout, and the guard only needs the effective
  identity to match. It asks for two separate commands because the commit guard refuses
  compound `git config` calls ("run configuration changes separately"). The configured
  name and email are shown because they are the repository's commit identity, already
  public in its history, not secrets.
- "Reuse its helper" in the issue is read as: reuse the reader concept `_READERS` that #222
  put in `protect_state.py`, placed next to the #225 early return in `_write_targets` (the
  same rule: arguments are data, redirects stay checked through `command.writes`). No new
  helper.
- A reader piped into an executor needs no special case in `_write_targets` (unlike the
  `feeds` rule `_owner_action` uses): a bare `sh`/`bash` reading stdin is a parse error
  ("missing shell -c script") and `xargs` with a path command is refused as input-driven,
  both before `_write_targets` runs, and both refuse when the script names `.wuwei`.
  Spec 9.1 (amended by #237) makes hooks cooperative mistake prevention; no further pipe
  analysis is added.
- The integrity page a development checkout raises in PreToolUse ("requires host
  reconfirmation") is unrelated; tests seed integrity with `fakes.integrity.seed` as the
  existing hook tests do.
- Out of scope: the "missing or malformed identity" reason, the `-c` and environment
  override reasons, and git's own normalisation of names (git strips some trailing
  punctuation from `user.name`, so a configured name ending in `.` never matches); none
  were hit in the dry run.
