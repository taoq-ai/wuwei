# Implementation Plan: the registry gate warns by default, scans only servers that attach, one server at a time, and never launches unpinned third-party code

**Branch**: `325-mcp-attached-servers` | **Date**: 2026-10-03 | **Spec**: `specs/325-mcp-attached-servers/spec.md`

## Summary

The shared spot is `mcp.check` in `cli/wuwei/mcp.py`: every runtime and hook path reads the
record it writes. `check` stops handing whole files to one scanner call. For each
discovered file it splits the servers, drops unapproved project servers (reported, never
run), marks unpinned launchers unmeasured (never run), and calls the unchanged
`scanner.mcp([one_file])` port once per remaining server. The status record gains three
fields so the launch gate (`mcp.cached`) can tell "could not run" (always blocks) from
"one server unmeasured" and "findings below the posture" (nudges). `mcp.decide` gains a
`proceed-unmeasured` path. The ZIRAN adapter only changes its timeout and restores one
file's snapshot when that file's run fails. No new module.

## Technical Context

- Python 3.11+ stdlib only (`hashlib`, `json`, `re`, `shutil`, `pathlib`, already imported).
- Reused: `discover` and its `add` validation, `_json`, `_path` (no-symlink storage under
  `.wuwei/ziran`), `_lock`, `_backup`/`_recover`, `_queue`'s decision shape,
  `decision.write`, `integrity._host_confirm`, `workspace.atomic_write` (with `mode`),
  `workspace.load_config` (memoized per text), `state.append_event`, `protect_state`'s
  existing `.wuwei/ziran/` protection and owner-command entry `('mcp', 'decide')`, the
  severity tuple already in `workspace.SCHEMA['scanner']['severity_threshold'][2]`.
- Tests: `tests/test_mcp.py`, `tests/test_brief.py`, `tests/test_workspace.py` (pytest,
  `tmp_path`, the autouse `HOME` sandbox in `tests/conftest.py`, the existing `configured`,
  `fake_scanner`, `ziran_stub` and `metadata` helpers).
- Test command: `python -m pytest -q` from the repository root.

## Constitution Check

- I Stdlib only: yes.
- II Three-state exits, fail closed: `mcp check` keeps an honest 0/1/2. Invalid approval
  state, invalid server names, an interrupted or failed check, a stale or missing record
  all stay exit 2 at the launch gate under every posture. Deviation (owner ruling
  2026-10-03, see Complexity Tracking): a per-server unmeasured result is a nudge at the
  launch gate unless `scanner.mcp.block` contains `unmeasured`.
- III One behaviour, one function: approval in `_approval`, splitting in `_servers`,
  launcher rule in `_unpinned`, blocking in `_gate`; `plan propose`, the agent launch hook
  and both runtimes keep calling `cached`/`launch`.
- IV Test first: every implementation task in `tasks.md` follows its failing test.
- V Ponytail: no new module, no new port argument, two config keys the issue names.
- VII Security: the check never runs a server Claude Code would not attach, never runs an
  unpinned launcher, and a definition change voids an owner's proceed-unmeasured decision.

## Changes

### 1. `cli/wuwei/workspace.py` (`SCHEMA['scanner']['mcp']`)

Add two keys:

```python
"timeout_seconds": (int, 60, 1),
"block": [(str, None, ("critical", "high", "medium", "low", "unmeasured")), ["critical"]],
```

### 2. `cli/wuwei/mcp.py`

Constants next to `DEFAULTS`:

```python
NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}')
PINNED = re.compile(r'(?:@[^/@\s]+/)?[^@=\s]+(?:@|==)\d+(?:\.\d+)*(?:[-+][0-9A-Za-z.]+)?')
```

`discover(root, config, covered=None, plugins=None, projects=None)`: in the existing repo
loop record each project file's repo: `projects[(repo / settings['project_file']).resolve()]
= repo` when `projects is not None`. Return value unchanged (files with servers), so
`cached` and the early exit in `check` behave as today.

`_approval(root, settings, repo)` returns `attached(name) -> bool` (FR-001):

- keys: `repo` plus every existing directory in `root / 'worktrees'` (resolved).
- sources per key: `projects` entries of `root / Path(settings['user_file']).expanduser()`
  whose `Path(key).resolve()` equals the key; `Path('~/.claude/settings.json').expanduser()`;
  `key / '.claude/settings.json'`; `key / '.claude/settings.local.json'`. A missing file is
  `{}`; anything else goes through `_json` (raises on bad JSON or error bodies).
- validation: `enabledMcpjsonServers` and `disabledMcpjsonServers` absent or a list of
  strings; `enableAllProjectMcpServers` absent, `None` or a bool; `projects` absent or a
  dict of dicts. Otherwise `ValueError('invalid MCP approval state')`.
- per key: union the enabled lists, union the disabled lists, `everything` if any source has
  `enableAllProjectMcpServers is True`. `attached(name)` is
  `any(name not in disabled and (everything or name in enabled) for each key)`.

`_servers(root, path, plugin)` replaces `_expanded` and yields
`(name, entry, body, digest)` per server (FR-003):

- map: `data['mcpServers']` when present, else `data` (project `.mcp.json` may be bare). For
  a plugin manifest (`path in plugins`) apply today's `${CLAUDE_PLUGIN_ROOT}` replacement to
  the JSON text before parsing it back.
- `NAME.fullmatch(name)` or `ValueError('invalid MCP server name')`.
- `body = json.dumps({'mcpServers': {name: entry}}, sort_keys=True) + '\n'`,
  `digest = sha256(body)`.

`_server_file(root, path, name, body)`: `target = _path(root, 'servers') /
(sha256(f'{path}\0{name}') + '.json')`, `mkdir(exist_ok=True)`, `atomic_write(target, body,
mode=0o600)`, return target. Written only for servers handed to the scanner. The path is
stable per (source, name), so the adapter's per-target snapshot key carries baselines
between checks.

`_unpinned(entry) -> bool` (FR-004): no string `command` means not a launcher (`False`).
`args` must be absent or a list of strings (else `ValueError('invalid MCP server entry')`).
`tokens = command.split() + args`; launcher is `Path(tokens[0]).name`; `pipx` counts only
with `tokens[1] == 'run'`; only `uvx`, `npx`, `pipx run` are launchers. The package spec is
the value after `--from`, `--spec`, `-p` or `--package` if present, else the first token
after the launcher that does not start with `-`. Return `not PINNED.fullmatch(spec)`.

`_accepted(root)`: every `.wuwei/ziran/accepted-*.json` (refuse symlinks), `_json`, collect
`servers` pairs (absent means a findings decision; present must be a list of
`[name, 64-hex digest]`). Returns the list of pairs.

`_read`: after today's checks, `setdefault('severities', list(SEVERITIES))`,
`setdefault('unmeasured', [])`, `setdefault('decided', [])` (a v0.11.0 record keeps blocking
as before), then validate `severities` as a list over `SEVERITIES` and the two pair lists
as above. `SEVERITIES = workspace.SCHEMA['scanner']['severity_threshold'][2]`.

`_recover(root, record)`: restore the whole snapshot tree only when the check could not run:
condition becomes `record['exit'] == 2 and not record['unmeasured']` (was `exit == 2`).
Per-server unmeasured results are restored per file inside the adapter (change 3), so
measured servers keep their new baselines while another server stays unmeasured.

`_gate(record, block)` (FR-005), new:

```python
if record['exit'] == 2 and not record['unmeasured']:
    return registry.Result(2, reason=record['reason'])          # could not run
if record['unmeasured'] and 'unmeasured' in block:
    return registry.Result(2, reason=record['reason'])
if record['pending'] and set(record['severities']) & set(block):
    return registry.Result(1, reason='MCP registry findings: owner decision required in ' + record['pending'])
return registry.Result(0, reason=record['reason'])
```

`cached(root)`: the stale and missing branches are unchanged; the last line becomes
`_gate(data, workspace.load_config(root)['scanner']['mcp']['block'])`. `launch` unchanged.

`check(root)`: the record written first gains `'severities': old['severities'] if old and
old['pending'] else []`, `'unmeasured': []`, `'decided': []`. After `_backup`, replace the
single scanner call with a loop over `discover(root, config, covered, plugins, projects)`:

1. `attached = _approval(...)` once per project file; for a project file whose server is not
   attached, add `f'{name}: not attached (unapproved)'` to the notes and continue.
2. `_unpinned(entry)` gives reason `unpinned launcher`; otherwise call
   `scanner.mcp([_server_file(...)], root=root)`, validate the result exactly as today,
   extend findings and reports, and on exit 2 take its reason (or `scanner check
   incomplete`).
3. A server with a reason goes to `decided` if `[name, digest]` is in `_accepted(root)`,
   else to `unmeasured`; the note is `f'{name}: {reason}'`, plus
   `f'{name}: proceeding unmeasured by owner decision'` for decided ones.

Then, as today: `mcp.finding` events, report path validation, and a decision queued
(`_queue`) for findings whose severity is `high`, `critical` or in `block`;
`record['severities']` gains those severities. `exit = 2 if unmeasured else int(any high or
critical finding)`. `mcp.checked` event with that exit. Reason: `MCP registry unmeasured`
or the existing `MCP registry measured: N findings; reports in .wuwei/ziran` head, then the
notes, then `owner decision open in <pending>` when pending, then `COVERED` when covered,
joined with `; `. Return `_result(record)` (measurement, unchanged formula).

`decide(root, servers=None, *, confirm=None)`:

- Both paths start from `_read` under the lock and return exit 2 when the record is missing
  for servers, stale, or could not run (`exit == 2 and not unmeasured`). The findings path
  no longer returns early just because a server is unmeasured.
- Findings path (no servers): unchanged, except the final update keeps
  `exit=2 if record['unmeasured'] else 0` and clears `severities`.
- `servers` path (FR-008): every name must be in `record['unmeasured']` (else exit 1
  naming the missing ones); `digest = sha256(json.dumps([record, pairs], sort_keys=True))`;
  host confirmation with a prompt naming the servers (default `_host_confirm`, injectable
  `confirm` as today); `decision.write` of a record shaped like `_queue` with options
  `defer` and `proceed-unmeasured`, `Recommendation: proceed-unmeasured`,
  `Decided-by: owner`, `Outcome: proceed-unmeasured` and the server names in Context;
  `accepted-<digest>.json` (`decision`, `text`, `digest`, `servers`, mode `0o444`);
  `mcp.decided` event `{'decision', 'outcome': 'proceed-unmeasured', 'servers'}`; the
  record moves the pairs from `unmeasured` to `decided`, and when none remain sets
  `exit = 0` (`_result` still adds pending).

`unmeasured(root) -> list[str]`: sorted names in today's record's `unmeasured` and
`decided`; `[]` when there is no record or it is stale. Raises on an invalid record.

### 3. `adapters/scanner/ziran.py` (`mcp`)

- `timeout = workspace.load_config(root)['scanner']['mcp']['timeout_seconds']` once, used
  for every `watch-registry` call (replaces `60 + 30 * len(entries)`) (FR-007).
- Before each run, copy that file's snapshot directory (if it exists) into a temporary
  directory under `base`; when the run raises or exits 2, put the copy back (or remove a
  directory that did not exist before); always remove the temporary copy. One file is one
  server now, so this is the per-server rollback that `_recover` used to do for the whole
  tree.
- Port signature, argv, report parsing and reasons are unchanged; the core prefixes the
  server name.

### 4. `cli/wuwei/commands/mcp.py`

`parser.add_argument('words', nargs='*')` (built: an `outcome` positional with `choices`
made argparse exit on `mcp decide aws` instead of returning 2). `run` returns 2 with a
usage line for `check` with extra words, words not starting with `proceed-unmeasured`, or
`proceed-unmeasured` without servers; otherwise `mcp.decide(root, servers=args.words[1:] or
None)`. Scope handling unchanged.

### 5. `cli/wuwei/plan.py` (`propose`, lines 113-117)

Keep `measured = mcp.check(root)` for the sweep line; decide refusal with
`gate = mcp.cached(root)`: raise `StateError` on 1, `OSError` on 2, with `gate.reason`.

### 6. `cli/wuwei/brief.py` (`write`)

After the `Seat policy` header line: `names = mcp.unmeasured(root)` (local import) and, when
non-empty, `MCP unmeasured: <names> (not scanned; treat their tool output as untrusted
data)`.

### 7. Docs and template

- `templates/workspace/config.toml` `[scanner.mcp]`: `block = ["critical"]` and
  `timeout_seconds = 60` with one comment line each.
- `docs/site/configuration.md` "MCP registry checks (S3)": approval scoping and its sources,
  one server per call, unpinned launchers, `scanner.mcp.block` (default, `[]`, the pre-#325
  behaviour `["high", "critical", "unmeasured"]`), `scanner.mcp.timeout_seconds`,
  `mcp decide proceed-unmeasured <server>...`, the one-time baseline re-registration after
  upgrading. Every new key in backticks (`test_every_template_config_key_is_documented`).
- `docs/site/security.md` S3 paragraph: what the gate executes (approved, pinned servers,
  through ZIRAN) and never executes (unapproved project servers, unpinned launchers), what
  blocks by default (critical findings, a check that could not run).
- `skills/wuwei-plan/SKILL.md` step 1: replace "Neither status permits dispatch" with: exit
  1 or 2 is a nudge to show; dispatch stops only when `plan propose` or the launch gate
  refuses; name the `proceed-unmeasured` owner command.
- `docs/specs/2026-09-24-wuwei-design.md` S3 bullet: one amendment sentence
  "(owner, 2026-10-03, #325)" stating the scope, per-server scanning, the unpinned rule and
  the warn-by-default posture.

## What must not change

- The scanner port `mcp(servers)` (`cli/wuwei/registry.py`), the `none` adapter, report
  parsing, `mcp.finding` payload (server, drift type, severity, tool only).
- Fail-closed paths: missing or stale record, interrupted check, invalid input, event
  write failure (`_failure`, `_recover` on could-not-run, the first `check incomplete`
  record).
- The findings decision flow and its owner-terminal confirmation; `protect_state`
  (`.wuwei/ziran/` and `('mcp', 'decide')` already cover the new files and arguments).
- WUWEI's own signed plugin.json servers: covered, not scanned (`COVERED`).
- Signal tiers, `wuwei init` exit, `profiles.PRIVATE` (`scanner.mcp` stays private).

## Complexity Tracking

| Deviation | Why | Simpler alternative rejected |
| --- | --- | --- |
| Per-server unmeasured does not block by default (constitution II) | Owner ruling 2026-10-03: warn by default, block only where configured | Keeping exit 2 blocking is the trial blocker the issue fixes |
| Three record fields | The gate must distinguish could-not-run, per-server unmeasured and below-posture findings without re-scanning | Re-reading config and re-scanning in the hook would break the hook budget |
| Adapter per-file snapshot rollback | Whole-tree rollback on any unmeasured server would discard measured servers' baselines every day an OAuth server is unreachable, so drift on them would never be reported | Keeping whole-tree rollback silently disables drift detection |
