# Implementation Plan: the registry gate measures servers declared inline in a plugin's plugin.json

**Branch**: `291-mcp-inline-servers` | **Date**: 2026-10-01 | **Spec**: `specs/291-mcp-inline-servers/spec.md`

## Summary

One shared spot: `mcp.discover` gains the second per-plugin source by calling its existing
`add(path, user=True)` on `<installPath>/.claude-plugin/plugin.json`, skipping WUWEI's own
file (recorded as covered). `mcp.check` writes each discovered plugin.json as an expanded
`{"mcpServers": ...}` file at a stable path under `.wuwei/ziran/plugins/` and passes that to
the unchanged scanner port, then appends one sentence to its reason when WUWEI's own file was
seen. No adapter, registry, decision or event code changes.

## Technical Context

- Python 3.11+ stdlib only (`hashlib`, `json`, `pathlib` already imported in `mcp.py`).
- Reused: `add` (validation of a `mcpServers` map), `_json`, `_path` (no-symlink storage
  under `.wuwei/ziran`), `workspace.atomic_write`, `integrity.PLUGIN`, the ZIRAN adapter's
  per-file snapshot keying, `protect_state`'s existing `.wuwei/ziran/` protection.
- Tests: `tests/test_mcp.py` (pytest, `tmp_path`, the autouse `HOME` sandbox in
  `tests/conftest.py`, the existing `own_workspace` and `COCKPIT` helpers and the PATH-stub
  ZIRAN pattern).
- Test command: `python -m pytest -q` from the repository root.

## Constitution Check

- I Stdlib only: yes.
- II Fail closed: invalid plugin.json input raises inside `discover`/`check` and becomes the
  existing exit 2 `MCP registry unmeasured: <type>`; a newly discovered server is exit 2 in
  `cached` until measured.
- III One behaviour, one function: discovery stays in `discover`, measurement input in
  `check`; no second discovery path.
- IV Test first: every task below has its failing test first.
- V Ponytail: one optional argument, one private helper, one constant; no new module.
- VII Security: a third-party server, lookalike or not, is never skipped; only the file at
  WUWEI's own install path is, and that file is in the signed manifest.

## Changes

### 1. `cli/wuwei/mcp.py`

Imports: add `from wuwei.integrity import PLUGIN` (integrity imports only `registry` and
`workspace`; no cycle). It must be a module attribute so the existing #281 test that does
`monkeypatch.setattr(core(), 'PLUGIN', plugin, raising=False)` and the new tests can move
WUWEI's install.

Constant, next to `DEFAULTS`:

```python
COVERED = 'WUWEI plugin.json servers covered by plugin integrity (signed manifest), not scanned'
```

`discover(root, config, covered=None)`: in the installed-plugin loop, after the existing
`add(directory / '.mcp.json')` (line 75):

```python
            manifest = directory / '.claude-plugin/plugin.json'
            if manifest.resolve() == PLUGIN / '.claude-plugin/plugin.json':
                # Signed manifest (7.1): integrity measures WUWEI's own servers, not the registry.
                if covered is not None:
                    covered.append(manifest)
            else:
                add(manifest, user=True)  # Inline servers under top-level mcpServers.
```

Nothing else in `discover` changes: scope rules, the missing-file rule (absent plugin.json
is skipped, a dangling symlink raises), map validation and de-duplication are `add`'s.

New private helper, after `_write`:

```python
def _expanded(root, path):
    """A plugin's inline servers as Claude Code starts them, at a path stable per plugin."""
    text = json.dumps({'mcpServers': _json(path)['mcpServers']}).replace(
        '${CLAUDE_PLUGIN_ROOT}', json.dumps(str(path.parents[1]))[1:-1])
    target = _path(root, 'plugins') / (hashlib.sha256(str(path).encode()).hexdigest() + '.json')
    target.parent.mkdir(exist_ok=True)
    workspace.atomic_write(target, text + '\n')
    return target
```

`path` is the resolved plugin.json returned by `discover`, so `path.parents[1]` is the
resolved install directory. `json.dumps(...)[1:-1]` is the JSON-escaped string body, so
quotes, backslashes and non-ASCII in the install path keep the file valid. A changed or
broken plugin.json between `discover` and `_expanded` raises (`ValueError`, `KeyError`),
caught by `check`'s existing handler as exit 2.

`check(root)`:

- Before the early return: `covered = []`, and pass it:
  `if _read(root) is None and not discover(root, workspace.load_config(root), covered):`
  `return registry.Result(0, reason=COVERED if covered else '')`.
- Replace `files = discover(root, config)` with

  ```python
  files = [_expanded(root, path) if path.parts[-2:] == ('.claude-plugin', 'plugin.json') else path
           for path in discover(root, config, covered)]
  ```

  before `_backup(root)` (unchanged order otherwise). The scanner call, result validation,
  findings, events, pending decision and recovery are untouched.
- In the final `record.update(...)`, append the sentence to the reason of both branches.
  Pull the existing conditional into a local first, or the `+` binds to the f-string only:

  ```python
  reason = ('MCP registry unmeasured: ' + (result.reason or 'scanner check incomplete')
            if result.exit == 2 else
            f"MCP registry measured: {len(data['findings'])} findings; reports in .wuwei/ziran")
  record.update(exit=result.exit, reason=reason + ('; ' + COVERED if covered else ''))
  ```

This design was prototyped in a scratch copy (not in the worktree): `tests/test_mcp.py`,
`tests/test_board_mcp.py` and `tests/test_integrity.py` passed with it, including the #281
tests unchanged and the acceptance tests below.

`cached`, `launch`, `decide`, `_read`, `_result`, `_queue`, `_recover`, `_backup`: unchanged.
`cached` calls `discover(root, config)` without `covered`; WUWEI's own file is simply absent.

### 2. `tests/test_mcp.py`

- Extract the PATH-stub ZIRAN script and its install (executable in `tmp_path`, prepended to
  `PATH`) from `test_path_stub_init_then_description_drift_before_morning_launch` into a
  module-level helper `ziran_stub(tmp_path, monkeypatch)`, used by that test and the new one.
  The stub body is unchanged (it reads `config['mcpServers']['docs']['description']`).
- New tests per `tasks.md`; one added assertion in
  `test_own_server_and_source_checkout_attach_no_discoverable_file`.

### 3. `docs/site/configuration.md`, section "MCP registry checks (S3)"

- Replace the sentence block at lines 243-246 with: WUWEI declares its own read-only board
  server in the signed `.claude-plugin/plugin.json`; the integrity check covers it, so the
  registry does not scan it and `bin/wuwei mcp check` reports it as covered by plugin
  integrity. A `.mcp.json` added to the install, one in a workspace or repo, and any other
  plugin's servers, including one named like the cockpit, are discovered and checked like
  any other.
- Lines 250-252: installations "contribute their `.mcp.json` and the `mcpServers` object
  of their `.claude-plugin/plugin.json`; `${CLAUDE_PLUGIN_ROOT}` in plugin.json servers is
  expanded to the install path in a copy under `.wuwei/ziran/plugins` that the scanner
  measures."

## What must not change

- `adapters/scanner/ziran.py` and `adapters/scanner/none.py`: no edits (file paths in,
  one snapshot directory per resolved file path).
- `.mcp.json` handling everywhere: same paths to the scanner, no expansion, so existing
  snapshot keys and baselines are kept.
- The #281 tests: `test_cockpit_lookalike_file_stays_unmeasured_and_refused`,
  `test_plugin_json_declares_one_stdio_server` (`tests/test_board_mcp.py`), and the
  existing assertions of `test_own_server_and_source_checkout_attach_no_discoverable_file`
  (`discover == []`, `cached` 0, `check` 0).
- `.claude-plugin/plugin.json`, `integrity.py`, `protect_state.py`, `commands/mcp.py`
  (it already prints a non-empty reason), status record shape and `_read` validation.

## Complexity Tracking

None. Deliberately not built: plugin.json path-form `mcpServers` (fails closed), expansion of
other variables, cleanup of stale expanded files.
