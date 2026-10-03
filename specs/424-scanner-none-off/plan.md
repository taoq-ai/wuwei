# Implementation Plan: adapters.scanner = none turns the MCP gate off with one nudge line

**Branch**: `424-scanner-none-off` | **Date**: 2026-10-03 | **Spec**: [spec.md](spec.md)

## Summary

Every MCP surface already routes through two functions in `cli/wuwei/mcp.py`: `check` (init,
init --upgrade, setup, `mcp check`, `plan propose`) and `cached` (the launch gate: `mcp.launch`,
the runtime adapters, `agent_launch.check_mcp`, `plan propose`, doctor). Fix it there: both get
one `adapters.scanner == "none"` branch right after their existing `mcp = "off"` branch.
`check` says the line once per day using the existing `mcp.checked` event as the marker. Then
one more branch in `check`: a scanner adapter that returns exit 2 with no data could not start,
so the check could not run and blocks under guarded and strict through the unchanged `_gate`.
Two small call-site edits (`plan.py` prints the line, `doctor.py` shows the covered rows) and
docs. No caller of `check` or `cached` changes for the exit code.

## Technical Context

Python 3.11+ stdlib only; pytest for tests. No new module, config key, event kind, state key
or import on the hook path. `mcp.py` already imports `registry`, `state` and `workspace`;
`check` uses `watch.records` through the lazy import `findings` already uses.

## Constitution Check

- I stdlib: yes.
- II three-state exits, fail closed: `none` returns 0 with "not measured", never "clean";
  an unreadable `events.jsonl` still fails closed (exit 2, `watch.records` raises inside
  `check`'s existing `except`). A configured scanner that cannot start now fails closed under
  guarded, which is stricter than today. Design spec section 7's sentence on `none` conflicts
  with the issue; raised in spec A7, not edited here.
- III one behaviour, one function: the off decision lives in `check` and `cached` only; every
  surface inherits it. The text is one constant.
- IV test first: tasks.md orders each test before its code.
- V ponytail: two one-line branches, one five-line block for the once-per-day marker, one
  five-line block for "could not start", two call-site edits, docs.
- VII security: nothing new is read from untrusted input; the could-not-run reason is the
  adapter's own constructed text (type name or its fixed `ValueError` messages).

## Design

### 1. `cli/wuwei/mcp.py`

**Constant**, next to `NOT_CHECKED` (line 20):

```python
NO_SCANNER = 'mcp: not measured (no scanner configured; set adapters.scanner = "ziran" to measure)'
```

**`cached`** (line 317), after `if level == 'off': return ...` (lines 326-327):

```python
    if config['adapters']['scanner'] == 'none':  # #424: no scanner is a choice, the gate is off.
        return registry.Result(0, reason=NO_SCANNER)
```

No import. Order matters: `off` first so its own reason wins.

**`check`** (line 488), after the no-servers short-circuit (`if _read(root) is None and not
discover(...)`), still inside the `try`. Built after the `off` return first; that made `init`
with no attached servers write the marker event and create a day directory
(`tests/test_workspace.py` `test_init_layout`), so the block moved below the short-circuit. An
empty registry under `none` stays silent and side-effect free, as on main:

```python
        if config['adapters']['scanner'] == 'none':  # #424: the gate is off; say so once a day.
            from wuwei import watch
            if any(row['kind'] == 'mcp.checked' and row['payload'].get('scanner') == 'none'
                   for row in watch.records(workspace.day_dir(root) / 'events.jsonl')):
                return registry.Result(0)
            state.append_event('mcp.checked', {'exit': 0, 'servers': {}, 'scanner': 'none'}, root)
            return registry.Result(0, reason=NO_SCANNER)
```

This runs before `_lock`, `_write` and `registry.load`, so no `status.json`, no
`adapter: none` event and no `scanner.mcp: unmeasured` print. `mcp.checked` is already a
reserved producer kind (`commands/event.py` line 22), its exit 0 is silent in `signal.tier`
(line 50-51) and clears `mcp.finding` rows in `status.scan` (line 96-98). Two concurrent
first checks may both print; harmless (mark with `# ponytail: racy marker, two first checks
both print`).

**`check` loop, could not start** (after the result validation at lines 531-533, before
`if result.exit != 2:` at line 534):

```python
                        if result.exit == 2 and result.data is None:
                            # #424: the scanner itself could not start (not on PATH, wrong
                            # version): the check could not run, not one unmeasured server.
                            record.update(unmeasured=[], decided=[],
                                          reason=f'MCP registry could not run: {result.reason}')
                            _write(root, record)
                            _recover(root, record)
                            return registry.Result(2, reason=record['reason'])
```

`record['exit']` is already 2 (written at line 500-506). With `unmeasured: []`, `_gate` line
310 returns exit 2 under every posture whose level is not `off`, and `cached` adds `(mcp: warn,
floor: scanner.mcp.block)` under guarded; observe keeps returning 0 (line 334-335). `_recover`
rolls every snapshot back because the record is exit 2 with no unmeasured server (line 469),
the same as for any check that could not run. No `mcp.checked` event, matching the existing
exception path. The adapter contract this relies on: `adapters/scanner/ziran.py` returns
`data=None` only from its outer `except` (find_workspace, storage, config, `_version`); every
per-server failure returns the `measured` dict. The test fakes in `tests/test_mcp.py`
(`fake_scanner` code 2) return a dict, so they keep the per-server path.

### 2. `cli/wuwei/plan.py` (`propose`, lines 118-124)

```python
    if measured.exit or measured.reason == mcp.NO_SCANNER:  # #351, #424
        print(measured.reason, file=sys.stderr)
    data['sweep']['mcp'] = measured.reason or gate.reason or 'MCP registry: no attached servers'
```

`gate.reason` only differs when `check` returned no reason: under `none` after the first check
of the day it is `NO_SCANNER`; under `ziran` with no servers and no record it is `''`, so the
fallback text is unchanged.

### 3. `cli/wuwei/commands/doctor.py` (`_gates`, lines 351-379)

After the legacy `mcp reports` row (line 362-365), before reading the record:

```python
    if config['adapters']['scanner'] == 'none':  # #424: no record rows; WUWEI's own servers stay covered.
        try:
            own = json.loads((integrity.PLUGIN / '.claude-plugin/plugin.json').read_text(encoding='utf-8'))
            names = sorted(own.get('mcpServers', {}))
        except (OSError, ValueError, AttributeError):
            names = []  # the install section already reports an unreadable manifest
        return rows + [_row('gates', f'mcp {name}', 'ok', 'covered by plugin integrity') for name in names]
```

The `mcp gate` row needs no change: `mcp.cached` returns `(0, NO_SCANNER)`, so it is `ok` with
the line. `json` and `integrity` are already imported (lines 7, 15).

### 4. Callers that need no change

- `commands/init.py` `_register_mcp` and `_finish`: print a non-empty reason, return the exit.
- `commands/setup.py` lines 325-335: `gate.exit` is 0, so nothing is owed; the reason prints
  once. `ending` already excludes the `mcp gate` doctor row; the new `mcp <name>` rows are
  `ok`.
- `commands/mcp.py`: prints the reason, returns the exit.
- `adapters/runtime/claude.py`, `adapters/runtime/codex.py`, `guards/agent_launch.py`: go
  through `mcp.launch` or `mcp.cached`.
- `brief.py`: `mcp.unmeasured` reads the record; with no record it is `[]`.
- `adapters/scanner/none.py`, `registry.record_none`, `scanner.py` (S2/S4): unchanged.

### 5. Docs

- `docs/site/security.md` line 5: replace "The `none` scanner reports unmeasured rather than
  clean." with: "With `adapters.scanner = \"none\"` the MCP registry gate is off and says
  `not measured`, never clean; trace and agent-surface checks report unmeasured."
- `docs/site/security.md` line 9 (ZIRAN integration), after "Do not treat an unavailable
  scanner as a clean audit.": "With `adapters.scanner = \"none\"`, the default, the registry
  gate is off: `init`, `setup`, `mcp check`, `plan propose` and the launch gate exit 0, and the
  first check of the day prints `mcp: not measured (no scanner configured; set adapters.scanner
  = \"ziran\" to measure)`. That gives up drift and tool-poisoning detection on every attached
  server. A configured scanner that cannot start (not on PATH, wrong version) is a check that
  could not run and blocks launches under `guarded` and `strict`."
- `docs/site/security.md` line 57 (posture floors): "unless it is `off`" becomes "unless it is
  `off` or `adapters.scanner = \"none\"`". The pinned phrases in `tests/test_docs.py`
  `test_security_posture_table_matches_the_code` (lines 855-856) are untouched.
- `docs/site/configuration.md` lines 337-339: replace "Missing tools or the `none` adapter are
  unmeasured when servers are attached." with the same two facts in configuration terms:
  "`none`, the default, turns the registry gate off: every MCP command and the launch gate exit
  0, the first check of the day prints `mcp: not measured (...)`, and doctor shows the gate ok
  and WUWEI's own servers as covered by plugin integrity. Nothing checks attached servers for
  tool drift or poisoning then. A configured scanner that is missing or the wrong version is a
  check that could not run (exit 2) and blocks launches under `guarded` and `strict`."
- `docs/site/configuration.md` line 150 (`adapters.scanner` row): append "`none` turns the MCP
  registry gate off."

### 6. Must not change

- `_gate`, `_cached`, `_result`, `discover`, `decide`, `migrate`, the posture table, the
  `scanner.mcp.block` default, the per-server unmeasured path for unpinned or unreachable
  servers, `security.areas.mcp = "off"` and its reason.
- The ziran and none adapters, `registry.record_none`, S2 (`scanner.trace_sweep`) and S4.
- The hook import map (`tests/test_hooks.py` `test_import_map_matches_guard_tables`,
  `test_hook_imports_no_unused_stdlib`): `cached` gains no import.
- `docs/specs/2026-09-24-wuwei-design.md` (owner-amended only; spec A7).
- `_pipeline/release.sh` is outside the repository (spec A6).

### 7. Existing tests that assumed `none` means unmeasured

Several tests leave `adapters.scanner` at its default `none` and expect unmeasured or a
refusal. They keep their intent by configuring `scanner = "ziran"` with a fake or absent
scanner, or by asserting the new `none` result. See tasks.md Phase 4 for the measured list.
`ziran` is on `PATH` on developer hosts, so a test that needs it absent sets `PATH` to a
`tmp_path` directory (as `tests/test_doctor.py` `ws` does) or replaces `registry.load`.
