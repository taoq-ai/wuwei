# Implementation Plan: A broken config.toml can be read and fixed from the session

**Branch**: `326-config-failure-mode` | **Date**: 2026-10-03 | **Spec**: [spec.md](spec.md)

## Summary

Three shared spots, one change each:

1. `hook.run` is the single point every guard result goes through. For PreToolUse and Stop,
   load the config once after resolving the workspace; a `ConfigError` (from that load or
   from scope resolution) goes to one new function, `config_failure`, before any guard
   runs. Stop prints and exits 0; PreToolUse lets `ToolSearch` and reads of the config and
   charters through and refuses the rest with one reason.
2. `workspace.load_config` already wraps every config error; add the `repos` hint there,
   so hooks, `config check`, `init --upgrade` and every command print it. `config check`
   needs no code.
3. The template drops `repos = []`; `init --upgrade` removes that line from an existing
   file when `[[repos]]` tables exist, before it parses the file.

No guard module changes.

## Technical Context

Python 3.11+ stdlib only; pytest for tests. No new module, no new dependency, no new
state key or event kind (the refusal reuses `hook.refusal`).

## Constitution Check

- I stdlib: yes.
- II fail closed: every PreToolUse call outside the read carve-out exits 2 with the
  reason; an `OSError` on the config read is left to the guards, which refuse as today.
  Stop exits 0 on purpose (the issue): a Stop refusal cannot fix the file and traps the
  turn.
- III one behaviour, one function: the failure mode lives in `hook.config_failure`; the
  hint lives in `load_config`; the repair lives in `init._without_empty_repos`.
- IV test first: tasks.md orders each test before its code.
- V ponytail: no new detector in `config check` (the hint in `load_config` is the
  detector); no per-guard carve-outs; no generic hint table for one known shape.
- VII security: the carve-out is reads only, of two workspace paths, plus `ToolSearch`.
  Shadow mode cannot relax the refusal because `hook.shadow` never runs on this path.

## Design

### 1. Hint: `cli/wuwei/workspace.py`

- `load_config(root=None)` becomes `load_config(root=None, *, raw=None)`; line 436
  becomes `raw = path.read_text(encoding="utf-8") if raw is None else raw`. Only
  `init --upgrade` passes it (section 3). The memo stays correct: it is keyed on the text,
  so the next disk read with different text re-parses.
- The `except` at lines 495-496 becomes:

  ```python
  except (ConfigError, tomllib.TOMLDecodeError, UnicodeError) as exc:
      hint = ''
      if "immutable namespace ('repos',)" in str(exc):  # #326: the template footgun
          line = _key_line(raw, ('repos',))
          if line:
              hint = f'; repos is assigned on line {line}; delete that line before using [[repos]] tables'
      raise ConfigError(f"config.toml: {exc}{hint}") from exc
  ```

  `raw` is always bound here: the message only comes from `tomllib.loads(raw)`.
  `_key_line(raw, ('repos',))` returns the first line that assigns or opens `repos`, which
  is the `repos = []` line, since a top-level assignment always precedes the tables
  (checked: line 5 of the template plus an appended table).

Resulting message for the trial shape:

```
config.toml: Cannot mutate immutable namespace ('repos',) (at line 229, column 8); repos is assigned on line 5; delete that line before using [[repos]] tables
```

### 2. Failure mode: `cli/wuwei/commands/hook.py`

- Module top: `from wuwei.workspace import ConfigError` (every non-malformed hook path
  imports `workspace` already).
- Constants:

  ```python
  # #326: events whose answer to a config.toml that does not load is config_failure.
  CONFIG_EVENTS = ('PreToolUse', 'Stop')
  # #326: with a broken config these reads still pass, so the session can show the line.
  REPAIR_READS = {'Read': 'file_path', 'Grep': 'path', 'Glob': 'path'}
  ```

- In `run`, inside the discovery `try` (lines 34-49), after `env.load(root)` (line 44),
  still under `if root is not None:`:

  ```python
  if args.event in CONFIG_EVENTS:
      try:
          workspace.load_config(root)
      except OSError:
          pass  # A missing or unreadable file stays the guards' to measure, as before.
  ```

- First lines of the discovery `except BaseException as exc:` (line 50), before the
  existing reason:

  ```python
  if isinstance(exc, ConfigError) and args.event in CONFIG_EVENTS:
      return config_failure(args.event, payload, str(exc))
  ```

  This catches both the load above and a `ConfigError` raised by
  `workspace.guard_scope` at line 42 (cwd outside the workspace, target or worktree
  anchor inside it; spec A8). Other events keep the generic path unchanged.

- New functions, next to `shadow`:

  ```python
  def config_failure(event, payload, reason):
      """A config.toml that does not load (#326): Stop prints it and lets the turn end;
      PreToolUse lets ToolSearch and reads of the config and charters through so the session
      can show the line, and refuses everything else with the error."""
      if event == 'Stop':
          print(reason, file=sys.stderr)
          return CLEAN
      if repair_read(payload):
          return CLEAN
      return refuse(event, reason, cwd=payload.get('cwd'),
                    record=payload.get('session_id') != HEARTBEAT_SESSION, payload=payload)


  def repair_read(payload):
      """ToolSearch, or a Read, Grep or Glob whose path is a workspace's .wuwei/config.toml,
      its .wuwei/charters directory or a file in it."""
      tool = payload.get('tool_name')
      if tool == 'ToolSearch':
          return True
      inputs = payload.get('tool_input')
      if not isinstance(tool, str) or tool not in REPAIR_READS or not isinstance(inputs, dict):
          return False
      value = inputs.get(REPAIR_READS[tool])
      if not isinstance(value, str) or not value:
          return False
      from wuwei import workspace
      try:
          target = (Path(payload['cwd']) / Path(value).expanduser()).resolve()
          base = workspace.find_workspace(target, use_environment=False) / '.wuwei'
      except (OSError, ValueError, RuntimeError):
          return False
      return target == base / 'config.toml' or target.is_relative_to(base / 'charters')
  ```

  `find_workspace` (not `guard_scope`) because `guard_scope` loads the broken config. The
  resolved target decides, as spec 9.1 says for file guards; a symlinked `.wuwei` raises
  `ValueError` and is refused.

Reuse: `refuse` (deny JSON, `hook.refusal` record, exit 2), `HEARTBEAT_SESSION`,
`workspace.find_workspace`. `refuse` is unchanged.

Latency: every PreToolUse and Stop call inside a workspace already loads the config in a
guard (`integrity.check`, `stop.check`); the extra call hits the per-process memo
(`_CONFIGS`), one file read and a deepcopy.

### 3. Template and upgrade

- `templates/workspace/config.toml` lines 5-6: delete `repos = []`; line 6 becomes
  `# Add one [[repos]] table per repository, for example:`. The commented example stays.
  `test_every_template_config_key_is_documented` still finds the `repos.*` keys through
  the commented `# [[repos]]` header.
- `cli/wuwei/commands/init.py`, next to `_migrated_config`, reusing `_sections`:

  ```python
  def _without_empty_repos(raw):
      """Drop a top-level one-line repos = [] that [[repos]] tables make a TOML error (#326)."""
      sections = _sections(raw)
      if not any(label == '[[repos]]' for label, _ in sections):
          return raw
      sections[0][1][:] = [line for line in sections[0][1]
                           if not re.fullmatch(r'\s*repos\s*=\s*\[\s*\]\s*(?:#.*)?\n?', line)]
      return ''.join(''.join(lines) for _, lines in sections)
  ```

  `sections[0]` is the root section, so a `repos = []` inside another table is never
  touched (it is an unknown-key error and keeps its own message).
- `upgrade` (lines 214-258):
  - after `raw = config_path.read_text(...)`: `text = _without_empty_repos(raw)`;
  - `tomllib.loads(raw)` becomes `tomllib.loads(text)`;
    `workspace.load_config(destination.parent)` becomes
    `workspace.load_config(destination.parent, raw=text)`;
  - `_migrated_config(raw, template)` becomes `_migrated_config(text, template)`;
    `config_changed = migrated != raw` stays (so the repair alone writes the file);
  - before the `for key in added:` print loop:
    `if text != raw: print(f'{prefix} config.toml: remove repos = []; the [[repos]] tables define the repositories')`;
  - the `No workspace changes needed` condition gains `and text == raw`.
  Dry-run validates the repaired text in memory and writes nothing; a real run writes
  through the existing `atomic_write`.
- Found during implementation: `upgrade` also calls `security.load`, which parses the
  on-disk `config.toml` with `tomllib` when `security.json` is missing (an older
  workspace). It gets the same keyword-only `raw=None` as `load_config`, and `upgrade`
  passes `raw=text`. Every other caller is unchanged.

### 4. Docs: `docs/site/configuration.md`

After the minimal `[[repos]]` example (line 64-73), one paragraph:

> Do not keep a `repos = []` line once you add `[[repos]]` tables: TOML rejects the two
> together. `bin/wuwei config check` names the line to delete, and `bin/wuwei init
> --upgrade` removes it. While `config.toml` does not load, every tool call in the
> workspace is refused with that error except `ToolSearch` and `Read`, `Grep` and `Glob` of
> `.wuwei/config.toml` and `.wuwei/charters`, so the session can show you the line; the
> Stop hook prints the error and lets the turn end.

## What must not change

- Every guard module and its `GUARDS`; `guards/__init__.py`; `hook.refuse`, `hook.shadow`,
  the malformed-payload paths, and SessionStart, PostToolUse, PreCompact and SubagentStop
  behaviour.
- Hook output for a valid config, byte for byte.
- The `config.toml:` prefix of every config error (pinned by
  `tests/test_records_after_dryrun4.py::test_config_error_names_config_toml`, which must
  pass unchanged).
- `commands/config.py`: no code change.
- `_migrated_config` and `_preserves_values`.
- A config with `repos = []` and no tables, including the upgrade of one.

## Tests that change

- `tests/test_workspace.py::test_upgrade_preserves_nonadjacent_repo_tables` anchors its
  first table on `'repos = []\n'`, which the template no longer has. Re-anchor it on
  `'[prioritisation]\n'` (insert the `b` table before it, ending with a blank line) so the
  test still covers two non-adjacent tables.

## Project Structure

```
cli/wuwei/workspace.py            load_config: raw keyword, repos hint
cli/wuwei/commands/hook.py        CONFIG_EVENTS, REPAIR_READS, config_failure, repair_read; two hooks in run
cli/wuwei/commands/init.py        _without_empty_repos; upgrade uses it
cli/wuwei/security.py             load: raw keyword, used by upgrade only
templates/workspace/config.toml   no repos key
docs/site/configuration.md        one paragraph
tests/test_config_failure.py      new: hook, hint, template, config check
tests/test_workspace.py           upgrade repair tests; re-anchored nonadjacent test
```
