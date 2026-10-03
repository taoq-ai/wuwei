# Implementation Plan: Keys from a newer template warn instead of refusing, and setup and doctor say when to restart Claude Code

**Branch**: `353-config-transition` | **Spec**: `spec.md`

## Summary

One change at the shared spot: `workspace._validate` collects unknown keys and
`workspace.load_config` decides, after the posture is known, whether they raise
(`strict`, template not newer) or come back as warnings. Every hook, guard and command
already goes through `load_config`, so none of them changes for the main fix. Three small
helpers in `cli/wuwei/integrity.py` (plugin version, other versions with markers, the
restart text) feed the hook event, `doctor`, the status line, `setup` and `init
--upgrade`. One stamp helper in `cli/wuwei/commands/init.py` writes `template_version`.

## Technical Context

Python 3.11 stdlib only (`difflib`, `json`, `re`, `tomllib`). Tests: pytest, in process,
existing fixtures (`tests/test_doctor.py::ws`, `fakes.integrity.seed`, the hook replay
pattern of `tests/test_config_failure.py`). No new dependency, no new module.

## Constitution Check

- I stdlib only: yes. II exits: unchanged; recording failures in the hook never refuse
  and never pass silently (stderr). III one behaviour one function: unknown-key policy
  lives only in `load_config`; restart detection only in `integrity.restart`.
- IV test first: tasks.md orders each test before its code. V ponytail: no migration
  framework, one key and one comparison. VII security: `strict` keeps refusing; the
  newer-template exception is bounded by a version the hook reads from its own signed
  `plugin.json`; the event kind is reserved.

## Design

### 1. `cli/wuwei/workspace.py`

- `SCHEMA`: add `"template_version": (str, "")` at top level.
- `_validate(value, schema, path, raw, unknown=None)`: in the unknown-key branch build
  the text as today, with the suffix chosen by
  `difflib.get_close_matches(str(name), [k for k in schema if k != '*'], n=1)`:
  `f"; did you mean {'.'.join(map(str, (*path, near[0])))}?"` when found, else the
  existing `"; remove it or use a documented key"`. If `unknown is None`, raise
  `ConfigError(text)` (today's behaviour for `calibrate.apply` and `profiles._template`);
  else append the text and `continue`. Pass `unknown` through the three recursive calls.
- `load_config(root=None, *, raw=None, warnings=None)`:
  - `unknown = []`; `config = _validate(parsed, SCHEMA, (), raw, unknown)`. When
    `_validate` raises after collecting an unknown key, the first unknown key is raised
    instead (a typo such as `pth` usually explains the `required` error after it; this is
    the order every posture saw before #353).
  - After the existing checks, before memoizing:
    `if unknown and posture(config)[0] == 'strict':` lazily
    `from wuwei import integrity` and `if not integrity.newer_template(config): raise
    ConfigError(unknown[0])` (inside the `try`, so it gets the `config.toml: ` prefix as
    today).
  - Memo becomes `_CONFIGS[path] = (raw, config, tuple(unknown))`; the cache hit returns
    the same. When `warnings` is a list, extend it with
    `f'config.toml: {text}'` for each text (hit or miss).
- Nothing else in `workspace.py` changes. `scope`, `guard_scope` and every guard keep
  calling `load_config(root)` with no `warnings`.

### 2. `cli/wuwei/integrity.py`

Add next to `MARKERS`:

```python
RESTART = "Restart Claude Code so only this version's hooks run"

def version():
    """This plugin's version from .claude-plugin/plugin.json, or '' when unreadable."""

def release(text):
    """A dotted-integer version as a tuple, or None (re.fullmatch(r'\d+(?:\.\d+)*', text, re.ASCII))."""

def newer_template(config):
    """(plugin, template) when config['template_version'] is newer than this plugin, else None."""

def other_versions():
    """Sorted names of PLUGIN.parent's other directories whose .in_use/ holds an entry; [] on OSError."""

def restart(config):
    """'plugin <old> running against template <new>: restart Claude Code', or ''.
    old: other_versions(), plus this version when newer_template(config); new:
    config['template_version'] or version(). config may be None."""
```

All read `PLUGIN` at call time so the existing monkeypatches in tests apply. No caching:
each hook is its own process and reads `plugin.json` once, only on PreToolUse.

### 3. `cli/wuwei/commands/hook.py`

In `run`, the `CONFIG_EVENTS` block (lines 51-56): keep the `except OSError: pass`, add an
`else:` that, for `PreToolUse` and a session other than `HEARTBEAT_SESSION`, calls a new
`newer_template(root, payload, config)`:

- `found = integrity.newer_template(config)`; return if None.
- Read `watch.records(workspace.day_dir(root) / 'events.jsonl')`; return if any row has
  kind `config.newer_template` and `payload['session'] == payload['session_id']`.
- `state.append_event('config.newer_template', {'plugin': found[0], 'template': found[1],
  'session': payload['session_id']}, root)`.
- Any exception: print `wuwei hook: could not record config.newer_template: <exc>` to
  stderr and continue (same shape as the shadow recorder in `posture`).

`config_failure` and the rest of `run` do not change.

### 4. `cli/wuwei/commands/event.py`

`EVENT_PRODUCERS['config.newer_template'] = 'wuwei hook PreToolUse'`.

### 5. `cli/wuwei/commands/config.py`

`run`: `found = []`, `config = load_config(warnings=found)`, then print each as
`wuwei config check: warning: <text>` to stderr. Status unchanged by them.

### 6. `cli/wuwei/commands/doctor.py`

- `diagnose`: `found = []`; `workspace.load_config(root, warnings=found)`; pass `found` to
  `_workspace(root, config, error, found)`.
- `_workspace`: when `config` loaded and `found`, the `config` row is
  `_row('workspace', 'config', 'warn', f'loads; {len(found)} unknown keys',
  'remove or rename each key named below in .wuwei/config.toml', detail=found)`; else as
  today.
- `_install`: `notice = integrity.restart(config)`; when set, the `in_use` row is
  `_row('install', 'in_use', 'warn', notice, integrity.RESTART,
  docs='docs/site/configuration.md#workspace-and-repositories')`; else today's row.

### 7. `cli/wuwei/commands/status.py`

`snapshot`: `result['restart'] = integrity.restart(config) if config is not None else ''`.
`line`: after the posture part, `if data.get('restart'): parts.append(data['restart'])`.

### 8. `cli/wuwei/commands/init.py`

- `_stamp(text)`: `mine = integrity.version()`; `current =
  tomllib.loads(text).get('template_version', '')`; return `text` unchanged unless
  `integrity.release(mine)` and (`integrity.release(current)` is None or older). Then
  replace the first `(?m)^template_version\s*=.*$` with `template_version = "<mine>"`, or
  prepend that line when absent (top-level keys must precede tables).
- New workspace (`run`): stamp the staged `config.toml` (next to the posture edit).
- `upgrade`: `migrated = _stamp(migrated)` after `_migrated_config`; when the stamp
  changed it, print `{prefix} config.toml: template_version <mine>` and count it as a
  change for `No workspace changes needed`. `load_config(..., raw=text, warnings=found)`
  and print each as `wuwei init: warning: <text>` to stderr. After `_finish` (not dry
  run): `if integrity.other_versions(): print(integrity.RESTART)` as the last line.

### 9. `cli/wuwei/commands/setup.py`

- `_setup`: `staged = init._stamp(repo_tables(raw, found['repos']))`, so the stamp is in
  the diff the owner confirms.
- `run`: wrap the existing `try` in `try/finally`; in `finally`,
  `if integrity.other_versions(): print(integrity.RESTART)`. That makes it the last stdout
  line on every path.

### 10. Template, release, docs

- `templates/workspace/config.toml`: line 1 comment becomes
  `# Defaults apply when settings are omitted. Unknown keys warn (strict posture: errors).`
  Add a root line after `profile`:
  `template_version = "" # Plugin version that last wrote this file; init, setup and init --upgrade set it.`
- `.github/workflows/release.yml`, step "Attach signed archive to release": add
  `append_body: true` and `body: "Restart Claude Code so only this version's hooks run."`.
- `docs/site/configuration.md`: the line 9 sentence on unknown keys; a
  `template_version` row in the Workspace table.
- `docs/site/reference.md`: the Doctor paragraph (the `in_use` row can warn with the
  restart), the status line paragraph (`restart` part), and one sentence on
  `config.newer_template`.

## What must not change

- `strict` with an unknown key and no newer template: same refusal path (#326
  `config_failure`, repair reads still pass).
- Every other `ConfigError` (types, constraints, floors, duplicates, adapters, TOML
  syntax) raises as today in every posture.
- `calibrate.apply` and `profiles._template` keep strict validation (no `unknown` list).
- Integrity measurement, `_prune` and the `.in_use` rules (#324) are untouched; US4 only
  adds a test.
- No guard, posture level or floor changes; the hook reads no new file except
  `plugin.json` on PreToolUse.

## Tests that change

- `tests/test_workspace.py::test_unknown_key_line`: from `config check` exit 1 to
  in-process `load_config` with `[security]\nposture = "strict"` appended (line numbers
  unchanged); assert the key and `line <n>` in the error. Two cases (`repos.1.pth`) also
  miss a required field, so a warnings list could not hold them.
- `tests/test_workspace.py::test_owner_verbosity` (`retro` now warns),
  `test_decisions_config` (strict appended), `test_config_defaults_and_independence`
  (`template_version` default), `test_init_layout` (stamped template),
  `tests/test_doctor.py::test_workspace_config_does_not_load` (an invalid adapter value
  instead of an unknown adapter key), `tests/test_records_after_dryrun4.py`
  (`nonsense = 1` under strict) and `tests/test_signal_status.py` (the new kind is a
  nudge).
- `tests/test_workspace.py::test_unknown_key_without_known_line`: add
  `[security]\nposture = "strict"` so it still raises.
- `tests/test_workspace.py::test_upgrade_rejects_unknown_key_without_writes`: set
  `security.posture = "strict"` in the fixture text so it still refuses with no writes.
- `tests/test_config_failure.py::test_other_config_errors_have_no_repos_hint`: same,
  strict.
- `tests/test_doctor.py::test_install_rows`: unchanged expectations (no sibling markers).
- Any test asserting `No workspace changes needed` on a workspace written without
  `template_version` now sees the stamp line; update the expectation, not the code.

## Project Structure

```text
cli/wuwei/workspace.py          _validate, load_config, SCHEMA
cli/wuwei/integrity.py          RESTART, version, release, newer_template, other_versions, restart
cli/wuwei/commands/hook.py      newer_template event on PreToolUse
cli/wuwei/commands/event.py     reserved kind
cli/wuwei/commands/config.py    print warnings
cli/wuwei/commands/doctor.py    config and in_use rows
cli/wuwei/commands/status.py    restart part
cli/wuwei/commands/init.py      _stamp, upgrade warnings and restart line
cli/wuwei/commands/setup.py     stamp, restart line
templates/workspace/config.toml
.github/workflows/release.yml
docs/site/configuration.md, docs/site/reference.md
tests/test_config_transition.py (new), tests/test_integrity.py, tests/test_workspace.py,
tests/test_config_failure.py
```

Merge note: #355 (same wave) also edits `templates/workspace/config.toml`, `init.py`
`upgrade` and `doctor.py`; keep these edits to the lines named here.
