# Implementation Plan: a fast check that names a per-worktree virtualenv runs in a fresh item worktree

**Branch**: `520-checks-venv` | **Spec**: `specs/520-checks-venv/spec.md`

## Summary

One shared helper in `cli/wuwei/fast_checks.py` resolves a fast check's relative interpreter
(worktree, then the repository's main worktree, with `[checks] python` overriding both).
`fast_checks.record` uses it to run the check and to record the interpreter; `worktree add`,
`doctor` and the builder brief call the same helper to bootstrap or warn, show, and name it.
A new `[checks]` config table carries `python` and `bootstrap`. Bootstrap runs through the
existing checks port, so the core still never imports `subprocess`.

## Technical Context

Python 3.11+ stdlib only (`shlex`, `pathlib`). Tests with pytest, `python -m pytest -q` from
the repository root. No new adapter, no new state key, no new event kind.

## Constitution Check

- I (stdlib): `shlex` and `pathlib` only. Bootstrap executes through `registry.load('checks',
  config).run(...)`, the existing adapter with its timeout and `GIT_*`-free environment.
- II (three-state exits): a check still returns the port's 0, 1 or 2. A bootstrap result of 1
  or 2 is a warning line; `worktree add` keeps its exit (0 after creation). No result is
  reported clean when unmeasured: a failed bootstrap leaves the next check to measure.
- III (one behaviour, one function): resolution lives only in `fast_checks.interpreter`; the
  four callers never re-derive it.
- IV (test first): every task pair below is test then implementation.
- V (ponytail): one helper, one rewrite, no new module. The record key is unchanged, so
  `build check`, the push guard and `complete_checks` need no change.
- VII (security, #530): no new refusal under any posture. `[checks]` is owner config, the same
  trust as `repos.fast_checks`, which is already executed as shell text.

## Design

### 1. Config: `[checks]` (cli/wuwei/workspace.py)

- Add to `SCHEMA` (next to `"worktree"`, line 77):
  `"checks": {"python": (str, ""), "bootstrap": (str, "")},`
- Bump `CONFIG_CACHE_VERSION` (line 571) by one. If main moved it meanwhile, take main's
  value plus one at merge.
- `templates/workspace/config.toml`: a commented example after `# [repos.shepherd]`:
  `# [checks]`, `# python = ".venv/bin/python"`, `# bootstrap = "python3 -m venv .venv && .venv/bin/python -m pip install -q -e ."`
  with a one-line comment. Keep commented so existing defaults are unchanged.

### 2. Shared helper: `fast_checks.interpreter` (cli/wuwei/fast_checks.py)

```python
RELATIVE = ('.venv/', 'venv/', 'node_modules/.bin/')

def interpreter(command, worktree, repo, root, config):
    """(path, source) when the check's first word is a relative interpreter, else None.
    source: checks.python, worktree, main worktree or missing."""
```

- `word = command.split(None, 1)[0] if command.strip() else ''`; not
  `word.startswith(RELATIVE)` returns `None`.
- `main = (Path(root) / Path(repo['path']).expanduser()).resolve()` (the expression
  `commit_push._context` and `doctor` already use).
- `config['checks']['python']` set and `Path(word).name.startswith('python')`:
  `(main / Path(setting).expanduser(), 'checks.python')` (an absolute setting stays absolute
  under `/`).
- Else the first of `Path(worktree) / word` (`worktree`) and `main / word` (`main worktree`)
  for which `.exists()` is true (a broken symlink is absent).
- Else `(Path(worktree) / word, 'missing')`.

### 3. Running and recording: `fast_checks.record` (cli/wuwei/fast_checks.py:36-47)

- Load the config once (`config = workspace.load_config(root)`, reused for `registry.load`).
- Per command: `found = interpreter(command, path, repo, root, config)`. When
  `found and found[1] in ('checks.python', 'main worktree')`, run
  `shlex.quote(str(found[0])) + command.lstrip()[len(word):]`; otherwise run `command`
  unchanged. The record stays keyed by the configured `command`.
- When `found` is not None, add `'interpreter': str(found[0]) if found[1] != 'missing' else None`
  to the record. Commands without a relative interpreter get no new key, so existing record
  assertions (`tests/test_fast_checks.py:52`) stay as they are.
- The first word is `command.split(None, 1)[0]`, recomputed inline where needed; the helper
  returns only `(path, source)`. No second public helper.

### 4. Worktree add: bootstrap or warn (cli/wuwei/commands/worktree.py:33-39)

After `create_worktree` succeeds and before printing the JSON:

- `path = root / 'worktrees' / item` (already the argument), `selected = repos[0]`.
- `bootstrap = config['checks']['bootstrap']`. When set:
  `found = registry.load('checks', config).run(str(path), bootstrap, root=root)`; when
  `found.exit != 0`, print to stderr
  `wuwei worktree warning: checks.bootstrap exited {found.exit}{": " + found.reason if found.reason else ""}`.
  Do not print `found.data` (command output).
- Else, for each command in `selected['fast_checks']`:
  `found = fast_checks.interpreter(command, path, selected, root, config)`; when
  `found and found[1] == 'main worktree'`, print to stderr
  `wuwei worktree warning: {word} is not in this worktree; fast checks will run {found[0]} from the main worktree (set [checks] bootstrap to build one per worktree)`.
- Exit stays 0. `adapters.checks` is validated at config load, so `registry.load` needs no new
  `try`; `adapters.checks = "none"` returns exit 2 from `run`, which is the warning above.
- Import `fast_checks` locally in `worktree.py`, `doctor.py` and `brief.py` (as `fast_checks.py`
  already imports `wuwei.brief` locally), so no hook path loads it and no import cycle forms.

### 5. Doctor row (cli/wuwei/commands/doctor.py:326-331)

After the `fast_checks` row, for each command `found = fast_checks.interpreter(command, path,
repo, root, config)` (here `path` is the main worktree, so the source is `checks.python`,
`worktree` or `missing`); for a non-None result append
`_row('workspace', f'{name} check interpreter', 'ok', f'{word}: {found[0]} ({source})')`,
with source `worktree` shown as `main worktree`, plus `; each new worktree runs [checks]
bootstrap` when bootstrap is set, else `; new worktrees use it until they have their own`.
For `missing`: `'warn'`, value `f'{word} not found in {path}'`, fix
`'set [checks] python or [checks] bootstrap in .wuwei/config.toml'`. Only repositories with a
relative interpreter get the row, so `tests/test_doctor.py:295` keeps its row list.

### 6. Builder brief line (cli/wuwei/brief.py:374-378)

Inside `if role == 'builder' or gate:` after the specmode line, for a builder only and when
`tree` and `repo` are set: for each command in `repo.get('fast_checks', [])` with
`found = fast_checks.interpreter(command, tree, repo, root, config)` not None, append
`f'Check interpreter: {command} runs with {found[0]} ({found[1]})'`, or for `missing`
`f'Check interpreter: {command} has no interpreter in the worktree or the main worktree; report it, do not build one'`.

### 7. Docs (docs/site/configuration.md)

- Add `` `[checks]` `` to the Workspace and repositories row of the Sections table (read by
  `tests/test_docs.py:768`).
- Two rows after `repos.fast_checks`: `checks.python` (`""`: interpreter for fast checks
  whose first word is a relative Python such as `.venv/bin/python`; absolute or relative to the
  repository's path; wins in every worktree) and `checks.bootstrap` (`""`: one command
  `worktree add` runs in each new worktree through the checks runner, for example creating the
  venv; a failure is a warning; use it when the package is installed editable in the main
  worktree's venv, because that interpreter can import the main worktree's code instead of
  the item's). Extend the `repos.fast_checks` row: a first word under
  `.venv/`, `venv/` or `node_modules/.bin/` resolves in the item worktree, then the main
  worktree; the record names the interpreter.

## What must not change

- The check record key (configured command) and every consumer: `commands/build.py`
  `check`, `complete_checks`, `stopped`, `guards/commit_push.py` `push_check`.
- `adapters/checks/local.py` and `adapters/checks/none.py` (no new port method).
- Commands without a relative interpreter: same command, same record, no row, no line.
- `calibrate.classify` keeps running commands in the configured checkout unchanged.
- No new refusal, state key, reserved key or event kind.

## Test fallout to expect

None for existing tests if the `interpreter` key, doctor row and brief line stay conditional.
`tests/test_docs.py:768` fails until `[checks]` is in the Sections table (task T010).

## Project Structure

- `cli/wuwei/workspace.py` (schema, cache version)
- `cli/wuwei/fast_checks.py` (helper, record)
- `cli/wuwei/commands/worktree.py` (bootstrap, warning)
- `cli/wuwei/commands/doctor.py` (row)
- `cli/wuwei/brief.py` (builder line)
- `templates/workspace/config.toml`, `docs/site/configuration.md`
- Tests: `tests/test_workspace.py`, `tests/test_fast_checks.py`,
  `tests/test_worktree_command.py`, `tests/test_doctor.py`, `tests/test_brief.py`
