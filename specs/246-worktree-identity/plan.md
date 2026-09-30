# Implementation Plan: Seats commit in a WUWEI worktree without setting git identity by hand

**Branch**: `246-worktree-identity` | **Date**: 2026-09-30 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/246-worktree-identity/spec.md`

## Summary

Three small fixes at the shared spots the dry run hit:

1. `workspace.create_worktree` writes the configured repository identity to the new
   worktree's `config.worktree` through one new vcs port operation, right after `install`
   (which already enabled `extensions.worktreeConfig` on a verified linked worktree).
2. `commit_push.identity_check` names the fix in its mismatch reason; the config template
   comment and the `repos.identity` docs row say where the identity is applied.
3. `protect_state._write_targets` exempts every reader in the module's `_READERS` (plus the
   three it exempts today), placed next to the #225 CLI early return. Redirects stay
   checked through `command.writes`.

## Technical Context

**Language/Version**: Python 3.11+, stdlib only at runtime

**Primary Dependencies**: none; `git` reached only through `adapters/vcs/git.py`

**Storage**: the item worktree's git `config.worktree` (written by git itself)

**Testing**: pytest, in process. PreToolUse through `wuwei.commands.hook.run` with a
payload on stdin, as `tests/test_seat_command_forms.py` and
`test_discovered_guards_through_hook` do; integrity seeded with `fakes.integrity.seed`.
One real-git test (a `git init` repository, no identity anywhere; `HOME` is already a
temp dir through the autouse fixture in `tests/conftest.py`). Port tests with
`install_replay`.

**Target Platform**: macOS and Linux hosts running Claude Code

**Project Type**: CLI plugin

**Performance Goals**: two extra `git config` calls per `worktree add`; nothing on the hook
path except fewer `_protected` calls for readers.

**Constraints**: exits 0/1/2, fail closed with a reason; closed git argv allowlist; no
absolute local paths, em-dashes or emojis in anything written.

**Scale/Scope**: 7 source files (3 code, 1 fake, 1 registry, 1 template, 1 docs page), 5
test files.

## Constitution Check

- I Stdlib only: yes (`shlex` added to `commit_push.py`).
- II Three-state exits: the new port operation returns 0 or 2 through `_operation`;
  `worktree add` exits 2 on its failure (ValueError path of `wuwei.__main__`), 0 otherwise.
- III One behaviour, one function: identity write lives in one adapter function called from
  the one worktree creation function; the reader rule stays in `_write_targets`.
- IV Test first: every task below has its failing test first.
- V Simplicity: no new module, helper, config key or event. One port operation, one moved
  and widened line in the state guard, one message.
- VII Security: the identity values cross into a git subprocess only through the argv
  allowlist and a value check (no leading `-`, no newline, NUL, `<`, `>`); the write is
  worktree-scoped, so the owner's checkout is untouched. The state guard change widens an
  exemption only for programs that write no file by operand; redirects, `tee`, `xargs` and
  shell-stdin forms stay refused.
- Pre-flight: scope unchanged (guards still act only inside a workspace); no seat-writable
  record is trusted; no new reserved key.

## Project Structure

### Documentation (this feature)

```text
specs/246-worktree-identity/
├── spec.md
├── plan.md
└── tasks.md
```

No research.md, data-model.md, contracts/ or quickstart.md: the one contract change (a vcs
port operation) is fully described below.

### Changes by file

#### `adapters/vcs/git.py`

- `_run` allowlist: add
  `case ('config', '--worktree', 'user.name' | 'user.email', value): allowed = isinstance(value, str) and bool(value) and not value.startswith('-')`
  next to the existing `('config', '--worktree', 'core.hooksPath', path)` case (line 78).
- New `@_operation def worktree_identity(repo, name, email, root=None)` next to
  `hooks_path` (line 480): for each of `name`, `email` raise `ValueError('invalid identity')`
  unless it is a `str`, non-empty after `strip()`, does not start with `-`, and contains none
  of `\n \r \0 < >` (the same character rule as `commit_push._identity`); then
  `_run(repo, 'config', '--worktree', 'user.name', name)` and
  `_run(repo, 'config', '--worktree', 'user.email', email)`; return
  `{'name': name, 'email': email}`.

#### `cli/wuwei/registry.py`

- `PARAMETERS['vcs']`: add `'worktree_identity': ('repo', 'name', 'email')` after
  `'hooks_path'` (line 51).

#### `tests/fakes/vcs.py`

- Add `def worktree_identity(self, repo, name, email, root=None): return self._call('worktree_identity', (repo, name, email), root)`.

#### `cli/wuwei/workspace.py`

- `create_worktree(repo, branch, path, root, vcs, identity=None)` (line 433): after
  `install(path, root, vcs)` (line 444) add
  `if identity and identity['name'] and identity['email']:` then
  `data(vcs.worktree_identity(str(path), identity['name'], identity['email'], root=root))`.
  `data` is the `commit_push.data` already imported there; it raises `ValueError` with the
  port's reason on a non-zero result. Return value unchanged.

#### `cli/wuwei/commands/worktree.py`

- In `run`, pass `identity=repos[0]['identity']` to `workspace.create_worktree` (line 34).
  `load_config` fills the schema default `{'name': '', 'email': ''}`, so the key is always
  present.

#### `cli/wuwei/guards/commit_push.py`

- `import shlex`.
- `identity_check` (line 27): the author/committer mismatch reason becomes
  `f'GIT_{kind.upper()}_IDENT differs from configured identity; create item worktrees with wuwei worktree add, or run git config user.name {shlex.quote(owner[0])} and then git config user.email {shlex.quote(owner[1])} in this worktree'`.
  `owner` is the `(name, email)` tuple `_identity(expected)` already returns. The HEAD
  mismatch reason (line 31) is unchanged. Both callers (tool guard line 418 and
  `commands/git_hook.py`) get the new text with no change of their own.

#### `cli/wuwei/guards/protect_state.py`

- `_write_targets` (line 309): directly after the #225 `_wuwei_action` block (line 318 to
  321) add, with a one-line comment (reader arguments are text; redirects are checked
  from `command.writes`):
  `if program in (*_READERS, 'cat', 'less', 'jq'): return []`.
- Delete the old line 344 `if program in ('cat', 'head', 'tail', 'less', 'jq', 'grep', 'wc'): return []`
  (now covered).

#### `templates/workspace/config.toml`

- Line 11 comment becomes: `# identity = {name = "Builder", email = "builder@example.test"} # Commit guards compare commits against it; wuwei worktree add writes it to each item worktree's Git config.`
  Example values unchanged.

#### `docs/site/configuration.md`

- Row `repos.identity` (line 28): description becomes "Expected git identity for this
  repository; the commit guards compare commits against it. Set both values.
  `wuwei worktree add` writes it to each item worktree's Git config."

### Shared helpers reused

- `commit_push.data` (port result unwrapping), `_operation` and `_run` (adapter),
  `git_hook.install` / `hooks_path` (worktreeConfig and linked-worktree check, unchanged),
  `protect_state._READERS` (#222), the #225 early-return position in `_write_targets`.

### Must not change

- `worktree add` JSON output and exits; `worktree_add` and `hooks_path` adapter functions
  and their registry signatures; `install`.
- `identity_check` logic and exit codes, the HEAD reason, the `-c` / environment override
  reasons (lines 409, 413), the "missing or malformed identity" path.
- In `protect_state.py`: `_owner_action`, `_owner_relevant`, `_READERS` contents,
  `_STATE_MENTION`, `_protected`, `_protected_name`, the parse-error branch and the
  interpreter opacity check in `check_bash`, and every target rule for `ln`, `install`,
  `rsync`, `rm`, `cp`, `mv`, `tee`, `truncate`, `sed -i`, `dd`, and the generic
  `return protected` fallback.
- Files other in-flight issues own: `cli/wuwei/guards/__init__.py`,
  `cli/wuwei/commands/config.py`, `docs/site/reference.md`, `docs/site/index.md`,
  `docs/site/daily.md`, `tests/test_e2e_day.py`, `scripts/headless_e2e.py`,
  `tests/test_docs.py`, `tests/conftest.py`.
- Merge note: #243 also edits `cli/wuwei/registry.py` (the `code_host` block) and the
  `code_host` rows of `CALLS` in `tests/test_adapters.py`; this change touches only the
  `vcs` block and `vcs` rows, separate hunks.

## Reproduction for the builder

Before any change, each new test below must fail for the stated reason: the real-git
acceptance test is refused with `GIT_AUTHOR_IDENT differs from configured identity` (or,
on a host where git cannot guess an email, a commit-guard "could not run"); the reader
tests are refused with "State and config files are protected"; the reason test lacks
`wuwei worktree add`; the port and contract tests fail on the missing operation. Do not
reference any dry-run path from the repository.

## Out of scope

- Failing `worktree add` when no identity is configured; identity checks in
  `wuwei config check`.
- Pipe analysis for readers (`feeds`), `python -m wuwei` without `-P`.
- Git's normalisation of names with trailing punctuation.
