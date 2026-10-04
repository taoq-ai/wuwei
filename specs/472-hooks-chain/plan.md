# Implementation Plan: worktree add chains WUWEI's git hooks with a repository's own hooks

**Branch**: `472-hooks-chain` | **Spec**: `specs/472-hooks-chain/spec.md` |
**Contract**: `specs/472-hooks-chain/contracts/chain-hook.md`

## Summary

The fix sits in the one place that decides: `adapters/vcs/git.py::hooks_path`. Instead of
raising when the repository has its own hooks, it writes chain scripts under the worktree's
git directory and points the worktree's `core.hooksPath` at them. The layouts it cannot
chain become exit 1 (a finding) instead of exit 2, and `git_hook.install`, the only caller,
turns exit 1 into a warning plus an event, or a refusal under strict. A config key picks
`chain`, `skip` or `replace`; doctor gets one row per repository through a read-only port
`hooks_target`; `init --upgrade` re-runs `install` for existing item worktrees.

## Technical Context

Python 3.11+, stdlib only (`shlex`, `os`, `pathlib`). Git 2.26 or newer for
`git config --show-scope`. The vcs adapter stays the only code that runs git or touches git
config. New imports in `adapters/vcs/git.py` (`shlex`, `wuwei.workspace`) go inside the
function that writes the scripts, because the adapter is loaded on the PreToolUse hook path.

## Constitution Check

- I stdlib only: yes.
- II exits: a layout that cannot be chained is exit 1 with the reason; every git or file
  failure outside the named cases stays exit 2 (fail closed), as today.
- III one behaviour, one function: the chain decision lives in `_chain_target` in the
  adapter; the posture decision lives in `git_hook.install`; doctor and `init --upgrade`
  reuse them, they do not reimplement them.
- IV test first: tasks.md orders a failing test before each implementation task; the hook
  tests use a real git repository in `tmp_path` and marker hooks.
- V ponytail: no new module, no new class beyond one exception; reuse `atomic_write`,
  `repo_context`, `workspace.posture`, `state.append_event`, `_row`.
- VII security: the repository's own `core.hooksPath` is never written; the worktree
  identity never falls back to the shared config.

## Design

### 1. `cli/wuwei/workspace.py` `SCHEMA`: the config key

Add one table (anywhere among the tables):

```python
"worktree": {"git_hooks": (str, "chain", ("chain", "skip", "replace"))},
```

Not added to `templates/workspace/config.toml` (spec Assumptions).

### 2. `adapters/vcs/git.py`

**Exception and `_operation`.** Add next to `RebaseConflict`:

```python
class Skippable(ValueError):
    """A repository layout WUWEI cannot install into; exit 1, the caller decides (#472)."""
```

In `_operation`, after the `RebaseConflict` clause and before the generic one:

```python
        except Skippable as exc:
            return Result(1, None, f'git.{function.__name__}: {exc}')
```

(No stderr print: the caller prints the warning.)

**`_run` allowlist.** Replace the case `('config', '--get', 'core.hooksPath')` (used only by
`hooks_path`) with `('config', '--show-scope', '--get-all', 'core.hooksPath')`, and add
`('config', '--local', '--get', 'extensions.worktreeConfig')`. Both `allowed = True`.

**Helpers** (module level, above `hooks_path`):

- `_worktree_config(repo)`: the existing `core.bare` / `core.worktree` reads moved out of
  `hooks_path` (`git.py:516-519`); raises `Skippable('core.bare or core.worktree is set, and
  extensions.worktreeConfig would apply it to every worktree; move it into the main
  worktree config.worktree (git help config, extensions.worktreeConfig), then run
  bin/wuwei init --upgrade')`.
- `_chain_target(repo)`: returns the absolute directory of the repository's own hooks, or
  `''` when there is nothing to chain.
  - `lines = _run(repo, 'config', '--show-scope', '--get-all', 'core.hooksPath',
    missing=True).splitlines()`; `own = [value for scope, value in (line.split('\t', 1) for
    line in lines) if scope not in ('worktree', 'command')]` (a line without a tab raises
    `ValueError` in the unpacking: exit 2, fail closed).
  - When `own and own[-1]`: `target = Path(repo, os.path.expanduser(own[-1]))` (an absolute
    value wins over `repo`); if `target.exists() and not target.is_dir()`: raise
    `Skippable(f'core.hooksPath {own[-1]} is not a directory; point core.hooksPath at a
    hooks directory, then run bin/wuwei init --upgrade, or set worktree.git_hooks = "skip"
    in .wuwei/config.toml')`; else return `str(target)`. An absent directory is returned
    too (husky creates it later; the script skips a missing hook).
  - Else: the existing default-hooks read (`git.py:510-514`); return `str(default)` when it
    is a directory holding a name not ending in `.sample`, else `''`.
  - `PermissionError` from the filesystem checks becomes `Skippable(f'cannot read
    {exc.filename} ({exc.strerror}); fix its permissions, then run bin/wuwei init
    --upgrade')`.
  - The old `existing != path` comparison is dropped: a repository hooks path equal to the
    shims would only run WUWEI's check twice.
- `_write_chain(directory, shims, own)`: writes the scripts of
  `contracts/chain-hook.md` (names, two templates, `shlex.quote`), with
  `Path(directory).mkdir(exist_ok=True)` and `atomic_write(..., mode=0o755)`, both
  imported inside the function. `PermissionError` becomes `Skippable(f'cannot write
  {exc.filename} ({exc.strerror}); fix its permissions, then run bin/wuwei init
  --upgrade')`. The script templates are module constants.

**`hooks_path(repo, path, mode, root=None)`** (port gains `mode`):

```python
@_operation
def hooks_path(repo, path, mode, root=None):
    path = os.fspath(path)
    if mode not in ('chain', 'skip', 'replace'):
        raise ValueError('unknown git hooks mode; set worktree.git_hooks to chain, skip or replace')
    git_dir = ...; common_dir = ...; linked-worktree check      # unchanged, git.py:502-505
    _worktree_config(repo)
    _run(repo, 'config', '--local', 'extensions.worktreeConfig', 'true')
    if mode == 'skip':
        return {'git_dir': git_dir, 'chained': ''}
    own = _chain_target(repo) if mode == 'chain' else ''
    target = path
    if own:
        target = os.path.join(git_dir, 'wuwei-hooks')
        _write_chain(target, path, own)
    _run(repo, 'config', '--worktree', 'core.hooksPath', target)
    return {'git_dir': git_dir, 'chained': own}
```

Order matters: `_worktree_config` before enabling `extensions.worktreeConfig`; enabling it
before `_chain_target`, so a "not a directory" skip still leaves the worktree its own
identity. `replace` never reads the repository's hooks.

**`hooks_target(repo, root=None)`** (new read-only port, for doctor):

```python
@_operation
def hooks_target(repo, root=None):
    """The repository hooks a new worktree would chain ('' for none); exit 1 when it cannot."""
    _worktree_config(repo)
    return {'chain': _chain_target(repo)}
```

**`worktree_identity`**: before the two writes,

```python
    if _run(repo, 'config', '--local', '--get', 'extensions.worktreeConfig',
            missing=True).strip().lower() not in ('true', 'yes', 'on', '1'):
        raise Skippable('extensions.worktreeConfig is off (core.bare or core.worktree is set), '
                        'so a worktree identity would change the shared config; commits use the '
                        'repository identity; move core.bare or core.worktree into config.worktree, '
                        'then run bin/wuwei worktree add again')
```

This closes the one path where `git config --worktree` silently means `--local`: the
`core.bare` / `core.worktree` skip, which used to be a refusal.

### 3. `cli/wuwei/registry.py` `PARAMETERS['vcs']`

`'hooks_path': ('repo', 'path', 'mode')` and add `'hooks_target': ('repo',)`.

### 4. `cli/wuwei/commands/git_hook.py` `install(path, root, vcs)`

Signature unchanged (`tests/test_worktree_command.py` monkeypatches it with a three-argument
lambda). The shim writes and their refusal stay as they are. Replace line 48 onward:

```python
SKIPPED = ('git hooks skipped for {path}: {reason}; the Claude Code PreToolUse guard still '
           'checks git commit and git push; run bin/wuwei doctor for the fix')
STRICT = ('{reason}; posture strict refuses a worktree without WUWEI git hooks; after the fix, '
          'remove {path} with git worktree remove and run bin/wuwei worktree add again')

    config = workspace.load_config(root) if (root / '.wuwei/config.toml').is_file() else None
    mode = config['worktree']['git_hooks'] if config else 'chain'
    result = vcs.hooks_path(str(path), str(directory), mode, root=root)
    if result.exit == 1 or (result.exit == 0 and mode == 'skip'):
        reason = result.reason if result.exit else 'worktree.git_hooks = "skip"'
        if result.exit and mode != 'skip' and config and workspace.posture(config)[0] == 'strict':
            raise ValueError(STRICT.format(reason=reason, path=path))
        from wuwei import state
        print('wuwei: warning: ' + SKIPPED.format(path=path, reason=reason), file=sys.stderr)
        state.append_event('worktree.hooks_skipped',
                           {'worktree': Path(path).name, 'reason': reason}, root)
    git_dir = Path(guard.data(result)['git_dir'] if result.exit != 1 else
                   guard.data(vcs.repo_context(str(path), root=root))['path'])
    # then the existing absolute check and the wuwei-workspace anchor write, unchanged
```

Exit 2 still raises through `guard.data` (fail closed, `test_hook_failure_prevents_core_success`
unchanged). The literal first argument of `append_event` keeps the kind visible to
`tests/test_signal_status.py::emitted_kinds`.

### 5. `cli/wuwei/workspace.py` `create_worktree`

Replace the identity line (`workspace.py:734`):

```python
    if identity and identity['name'] and identity['email']:
        written = vcs.worktree_identity(str(path), identity['name'], identity['email'], root=root)
        if written.exit == 1:
            print(f'wuwei worktree: warning: {written.reason}', file=sys.stderr)
        else:
            data(written)
```

(`sys` import if the module lacks it.) Exit 2 still raises (`test_worktree_identity_failure_exits_2`).

### 6. `cli/wuwei/commands/event.py` `EVENT_PRODUCERS`

`'worktree.hooks_skipped': 'wuwei worktree add or wuwei init --upgrade'`. Its tier is the
default `nudge` in `signal.classify`; `signal.py` does not change.

### 7. `cli/wuwei/commands/doctor.py` `_workspace`

In the per-repository loop, right after the `{name} git` ok row (`doctor.py:286`):

```python
        mode = config['worktree']['git_hooks']
        found = vcs.hooks_target(str(path)) if mode != 'skip' else None
        chain = (found.data or {}).get('chain', '') if found and found.exit == 0 else ''
        rows.append(
            _row('workspace', f'{name} git hooks', 'ok', 'skipped (worktree.git_hooks = "skip"); '
                 'the PreToolUse guard still checks git commit and git push') if found is None else
            _row('workspace', f'{name} git hooks', 'unmeasured', found.reason,
                 f'run git -C {path} config --show-scope --get-all core.hooksPath and fix what it names')
            if found.exit == 2 else
            _row('workspace', f'{name} git hooks', 'warn', found.reason,
                 'fix what the value names, then run wuwei init --upgrade; or set '
                 'worktree.git_hooks = "skip" in .wuwei/config.toml') if found.exit else
            _row('workspace', f'{name} git hooks', 'ok',
                 f'chained with {chain}' if chain and mode == 'chain' else
                 f'replaces {chain} (worktree.git_hooks = "replace")' if chain else 'WUWEI hooks'))
```

Person-facing text: no "the owner".

### 8. `cli/wuwei/commands/init.py` `upgrade`: regeneration

New helper next to `_finish`:

```python
def _worktree_hooks(root):
    """Rewrite every item worktree's git hooks; the scripts follow the repository's hooks (#472)."""
    trees = sorted(tree for tree in (root / 'worktrees').glob('*') if (tree / '.git').is_file())
    if not trees:
        return
    from wuwei import registry
    from wuwei.commands.git_hook import install
    vcs = registry.load('vcs', workspace.load_config(root))
    for tree in trees:
        install(tree, root, vcs)
```

Call it in `upgrade` after `if args.dry_run: return CLEAN` and before `code =
_finish(destination.parent)`: `_worktree_hooks(destination.parent)`. A `ValueError` reaches
the existing handler (`wuwei init: <reason>`, exit 2). Dry run writes nothing and prints
nothing, so doctor's template row is unaffected.

### 9. Docs

- `docs/site/configuration.md`: add `` `[worktree]` `` to the first row of the Sections
  table; add a key row after `security.areas.<area>`:
  `` | `worktree.git_hooks` | `"chain"` | ... | `` saying: `chain` runs WUWEI's pre-commit
  and pre-push checks and then the repository's hook of the same name when the repository
  has its own `core.hooksPath` or real hooks in `.git/hooks` (a generated directory under
  the worktree's git directory; the repository's setting is never changed), else the
  worktree uses `.wuwei/git-hooks`; `skip` installs none, warns and records
  `worktree.hooks_skipped`; `replace` uses `.wuwei/git-hooks` and the repository's hooks do
  not run in the worktree, for a repository you own outright; when chaining is impossible
  (a hooks path that is not a directory, no permission, `core.bare` or `core.worktree`
  set) `worktree add` still creates the worktree, warns and records
  `worktree.hooks_skipped`, and refuses under `security.posture = "strict"`; the Claude
  Code PreToolUse guard checks `git commit` and `git push` either way; `doctor` shows a
  `git hooks` row per repository; `init --upgrade` rewrites the scripts.
- `docs/site/reference.md` Item worktrees paragraph (line 143): "It installs the managed
  pre-commit and pre-push hooks, chained with the repository's own hooks (see
  [`worktree.git_hooks`](configuration.md#workspace-and-repositories)), and the workspace
  anchor".

Person-facing: "you", never "the owner".

## Tests that change (they encode the bug or the old port)

- `tests/test_git_hook.py::test_hooks_path_preserves_custom_hooks` and
  `::test_existing_default_hook_is_not_disabled` assert the refusal: replace them with the
  real-git adapter tests of tasks T003. Keep a replay case where the first git call exits
  128: still exit 2.
- `tests/test_git_hook.py::test_hook_installer_writes_executable_safe_shims`: the recorded
  call becomes `('hooks_path', (repo, shims, 'chain'))`.
- `tests/test_adapters.py` `CALLS`: `('vcs', 'hooks_path', ('repo', 'path', 'mode'), False)`
  and a new `('vcs', 'hooks_target', ('repo',), True)`.
- `tests/fakes/vcs.py`: `hooks_path(self, repo, path, mode, root=None)` recording `(repo,
  path, mode)`; new `hooks_target(self, repo, root=None)`.
- `tests/test_vcs.py::test_worktree_identity_port`: one more replay step first (`{'stdout':
  'true\n'}`) and the recorded calls start with the `extensions.worktreeConfig` read.
- `tests/test_doctor.py` `ws` fixture: add `'hooks_target': Result(0, {'chain': ''})` to the
  vcs fake, so the all-ok workspace assertions stay true.
- `tests/test_signal_status.py::test_emitted_kinds_have_intended_tiers`: add
  `'worktree.hooks_skipped': 'nudge'`.

## What must not change

- The shim text under `.wuwei/git-hooks/` and its "differs; refusing to overwrite" check,
  the `wuwei-workspace` anchor, the `git-hook` command, `commands/worktree.py`.
- The repository's own `core.hooksPath` in any scope; the only repository-level write stays
  `extensions.worktreeConfig = true`, as today.
- The no-custom-hooks path: worktree `core.hooksPath` = `.wuwei/git-hooks`, no
  `wuwei-hooks` directory, no output.
- Every existing test in `tests/test_worktree_command.py`.
- `_run(local=True)` and its `core.hooksPath=/dev/null` for workspace commits.
- Hook-path imports: no new top-level import in `adapters/vcs/git.py` or anything the
  PreToolUse hook loads.
- Files #469, #470 and #471 are changing in parallel: `cli/wuwei/guards/outward.py`,
  `cli/wuwei/shell.py`, `cli/wuwei/guards/protect_state.py`, `cli/wuwei/rank.py`,
  `cli/wuwei/decision.py`. Do not touch them.

## Risks for the builder

- `atomic_write` writes through a temp file in the destination directory, so a partly
  written chain script is never executed.
- Tests that run real git must drop `GIT_*` variables (as the existing tests do) and give
  the repository an identity. `tests/conftest.py` already points `HOME` at a temporary
  directory, so a developer's global `core.hooksPath` does not leak into the plain-path
  tests (`_run` strips `GIT_CONFIG*`, so `HOME` is the lever, not `GIT_CONFIG_GLOBAL`).
- `git config --show-scope` needs git 2.26; CI and macOS ship newer.
- Running a chain script directly in a test (outside git) needs `stdin=subprocess.DEVNULL`,
  or `cat` waits for input.
