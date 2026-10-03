# Implementation Plan: posture profiles

**Branch**: `331-security-posture` | **Date**: 2026-10-03 | **Spec**: [spec.md](spec.md)

## Summary

The decision point already exists: `hook.shadow` (`cli/wuwei/commands/hook.py:146`) turns
each guard refusal into "enforce" or "record and allow" by guard module. Generalise it, do
not add a second one. One posture table in the config module resolves `security.posture`
plus `[security.areas]` into a level per area (`workspace.posture`); one guard-to-area table
next to `MODULES` says which area each guard check belongs to (`guards.AREAS`,
`guards.OWNER_ONLY`, `guards.level`). The renamed `hook.posture` reads the config only when a
guard refused (as `shadow` does today), drops `off`, records `warn` as `guard.would_refuse`,
enforces `block` with a posture line. The MCP gate applies the `mcp` level in `mcp.cached`
and `mcp.check`, the one place its two consumers (the Agent hook and the runtime adapters)
already share. Shadow mode becomes `observe`: `guards.mode = "shadow"` resolves to it and
`guards.shadow_days`/`shadow_since` stay the time box. Everything else is a reader of the
resolved posture (config check, status, SessionStart, why) or a writer of the key (init,
interview).

## Technical Context

Python 3.11+ stdlib only; pytest for tests. No new module in `cli/`; one new test file
`tests/test_posture.py`. No new state key, no new event kind (`guard.would_refuse` gains
three payload fields). Hook latency: a clean call reads no extra config.

## Constitution Check

- I stdlib: yes.
- II fail closed: an unreadable config or no workspace enforces every refusal (as #308); an
  unrecordable warning is enforced; a floor violation is a `ConfigError`, which fails every
  hook closed through the #326 path; a guard module with no area blocks. Owner ruling in
  #325 already narrowed II for per-server MCP measurements; this item extends that ruling to
  `observe` only (A4, A6 in spec).
- III one behaviour, one function: the posture table and resolver in `workspace.py`; the
  per-guard level in `guards.level`; the refuse-or-record decision in `hook.posture`; the MCP
  level in `mcp.cached` (and `mcp.check` for off).
- IV test first: tasks.md orders every test before its code.
- V ponytail: no per-guard flags in guard modules, no new config for anything fixed; the one
  guard edit (`agent_launch.check_mcp`) exists because a function is the table's key.
- VII security: records floor, owner-only floor (deploy, merge policy, approvals, approve-tier
  sends) in every posture; the conflict with the issue's `observe` publish row is raised in
  spec A3.

## Design

### 1. Config: `cli/wuwei/workspace.py`

- Module constants above `SCHEMA` (after `SURFACES`, line 36):

  ```python
  # #331: what warns and what blocks, per area, by where the plugin runs.
  AREAS = ('integrity', 'mcp', 'publish', 'records', 'outward', 'seats')
  AREA_LEVELS = ('off', 'warn', 'block')
  POSTURES = {
      'observe': {**{area: 'warn' for area in AREAS}, 'records': 'block'},
      'guarded': {'integrity': 'block', 'mcp': 'warn', 'publish': 'block', 'records': 'block',
                  'outward': 'warn', 'seats': 'warn'},
      'strict': {area: 'block' for area in AREAS},
  }
  # Floors no posture or override lowers; a lower override is a config finding.
  FLOORS = {'records': 'block'}
  ```

  (`LEVELS` is already the verbosity tuple; do not reuse the name.)
- `SCHEMA["security"]` (line 46) becomes
  `{"required": (bool, False), "posture": (str, "guarded", tuple(POSTURES)),
    "areas": {area: (str, "", ("", *AREA_LEVELS)) for area in AREAS}}`.
- `load_config`, after the `shadow_since` check (line 457):

  ```python
  for area, floor in FLOORS.items():
      value = config['security']['areas'][area]
      if value and AREA_LEVELS.index(value) < AREA_LEVELS.index(floor):
          raise ConfigError(f'security.areas.{area}: "{value}" is below its floor "{floor}"; '
                            f'{area} always blocks, remove the override')
  ```

  The outer handler prefixes `config.toml: `, so `config check` prints it and exits 1.
- New function next to `load_config`:

  ```python
  def posture(config):
      """The posture name and each area's level (#331); guards.mode = "shadow" (#308,
      deprecated) is observe."""
      name = 'observe' if config['guards']['mode'] == 'shadow' else config['security']['posture']
      return name, {area: config['security']['areas'][area] or level
                    for area, level in POSTURES[name].items()}
  ```

### 2. Guard areas: `cli/wuwei/guards/__init__.py`

Replace `NEVER_SHADOWED` (lines 34-37) with:

```python
# #331: the posture area of each guard check; 'module.function' overrides its module. A test
# pins the keys to MODULES. None: the check applies its own posture (the MCP launch gate in
# mcp.cached), so the hook enforces it as returned.
AREAS = {'agent_launch': 'seats', 'agent_launch.check_mcp': None, 'commit_push': 'publish',
         'decision': 'records', 'deploy': 'publish', 'integrity': 'integrity',
         'lifecycle': 'records', 'outward': 'outward', 'pr': 'publish',
         'protect_state': 'records', 'stop': 'publish', 'traces': 'records',
         'verdict': 'records'}
# Owner-only actions block in every posture (#331 floor): the deployment ban (4.7), the merge
# policy, approvals and owner markers (4.6), and approve-tier messages and canary egress (4.9).
OWNER_ONLY = frozenset({'deploy', 'pr', 'outward.check_tier'})


def level(check, levels):
    """(module, area, level, line) for one guard check under resolved area levels. A check
    with no area blocks with no posture line."""
    module = check.__module__.rsplit('.', 1)[-1]
    key = f'{module}.{getattr(check, "__name__", "")}'
    area = AREAS.get(key, AREAS.get(module))
    if area is None:
        return module, None, 'block', ''
    if key in OWNER_ONLY or module in OWNER_ONLY:
        return module, area, 'block', f'posture: {area} = block (owner-only action; no setting lowers it)'
    from wuwei.workspace import FLOORS
    if area in FLOORS:
        return module, area, 'block', f'posture: {area} = block (floor; no setting lowers it)'
    return module, area, levels[area], f'posture: {area} = {levels[area]} (set security.areas.{area})'
```

### 3. The decision point: `cli/wuwei/commands/hook.py`

- Import line 10: `NEVER_SHADOWED` out, nothing in (`posture` imports `level` lazily, like
  `shadow` imports `state`).
- `run`, line 89: collect the check, not only its module:
  `refusals.append((guard.check, message))`.
- Lines 92-96 become:

  ```python
  enforced = [(check.__module__.rsplit('.', 1)[-1], message, '') for check, message in refusals]
  if (refusals and args.event != 'SessionStart'
          and payload.get('session_id') != HEARTBEAT_SESSION):
      enforced = posture(payload, refusals, root)
  reasons = [f'{message}\n{line}' if line else message for _, message, line in enforced]
  ```

  and the `refuse(...)` call passes `refusals=[(guard, message) for guard, message, _ in enforced]`
  so `hook.refusal.refusals` keeps the raw guard reason (`why` splits it on `; `).
- `shadow` (lines 146-167) is replaced by:

  ```python
  def posture(payload, refusals, root):
      """#331: per refusal, off drops it, warn records guard.would_refuse and lets the call
      through, block enforces it with its posture line. Returns (guard, reason, line)."""
      from wuwei import state, workspace
      from wuwei.guards import level
      try:
          name, levels = workspace.posture(workspace.load_config(root))
      except BaseException:  # No workspace or an unreadable config enforces, as before #331.
          return [(check.__module__.rsplit('.', 1)[-1], reason, '') for check, reason in refusals]
      enforced, shown = [], None
      for check, reason in refusals:
          guard, area, decided, line = level(check, levels)
          if decided == 'off':
              continue
          if decided == 'block':
              enforced.append((guard, reason, line))
              continue
          try:
              if shown is None:
                  shown = redacted_target(payload, root)
              state.append_event('guard.would_refuse', {
                  'guard': guard, 'area': area, 'level': decided, 'posture': name,
                  'reason': reason, 'target': shown, 'session': payload['session_id'],
                  'item': claimed(root, payload['session_id'])}, root)
          except BaseException as exc:
              print(f'wuwei hook: could not record shadow refusal: {exc}', file=sys.stderr)
              enforced.append((guard, reason, line))
      return enforced
  ```

  `root is None` makes `load_config(None)` fall back to `find_workspace()`; guard it
  explicitly: `if root is None: raise LookupError` inside the `try`, or test `root` first.
  The config is read only when a guard refused, exactly as `shadow` did.

### 4. MCP gate as its own guard record: `cli/wuwei/guards/agent_launch.py`

- Extract lines 42-60 of `_check` (scope, `tool_input`, `subagent_type`, role) into
  `_seat(payload)` returning `(root, inputs, role)` or `None` when the launch is not a WUWEI
  seat in scope; `_check` starts with `seat = _seat(payload)`, returns `(0, '')` on `None`,
  and drops lines 61-64 (the `mcp.cached` call).
- New guard function, same error shape as `check`:

  ```python
  def check_mcp(payload):
      """The MCP launch gate (#325) as its own record: mcp.cached applies the mcp posture and
      its floor (#331), so the seats level never relaxes it."""
      try:
          seat = _seat(payload)
          if seat is None:
              return 0, ''
          from wuwei import mcp
          measured = mcp.cached(seat[0])
          return measured.exit, measured.reason
      except Exception as exc:
          return 2, f'agent launch could not run: {exc}'
  ```

- `GUARDS = [Guard('PreToolUse', 'Agent', check_mcp), Guard('PreToolUse', 'Agent', check),
  Guard('SubagentStop', None, stop)]` (MCP first, as it ran first inside `_check`).

### 5. MCP level: `cli/wuwei/mcp.py`

- Constant: `NOT_CHECKED = 'MCP registry: not checked (security.areas.mcp = "off")'`.
- `check`: right after `root = Path(root).resolve()` (line 359), load the config once
  (`config = workspace.load_config(root)`), and
  `if workspace.posture(config)[1]['mcp'] == 'off': return registry.Result(0, reason=NOT_CHECKED)`.
  No discovery, no scanner, no event, no status write. Reuse that `config` for the
  `discover` call on line 361 (the one inside the lock at 373 stays: the file can change
  while waiting for the lock).
- `cached` (lines 283-295) becomes a wrapper around today's body, renamed `_cached(root,
  block)` with `block` passed in instead of read on line 293:

  ```python
  def cached(root):
      try:
          root = Path(root).resolve()
          name, levels = workspace.posture(workspace.load_config(root))
      except (OSError, ValueError, TypeError, KeyError) as exc:
          return _failure(exc)
      level = levels['mcp']
      if level == 'off':
          return registry.Result(0, reason=NOT_CHECKED)
      block = workspace.load_config(root)['scanner']['mcp']['block']
      if level == 'block':  # strict: the pre-#325 list (spec A5)
          block = sorted({*block, 'critical', 'high', 'unmeasured'})
      result = _cached(root, block)
      if not result.exit:
          return result
      if level == 'warn' and name == 'observe':
          return registry.Result(0, reason=f'{result.reason} (mcp: warn, security.areas.mcp)')
      # Floor (#331): under guarded and strict, scanner.mcp.block findings and a check that
      # could not run block whatever mcp is.
      note = 'floor: scanner.mcp.block' if level == 'warn' else 'security.areas.mcp'
      return registry.Result(result.exit, reason=f'{result.reason} (mcp: {level}, {note})')
  ```

  (`load_config` is memoised per process; the second call is a dict lookup.) `launch`,
  `plan.propose` (`plan.py:113-118`) and the runtime adapters keep calling `cached`
  unchanged. `plan.propose` with `off`: `check` returns `NOT_CHECKED` (the sweep line),
  `cached` returns 0, the plan proceeds, no `mcp.checked` event means no nudge.
- `unmeasured`, `decide`, `_gate`, `_queue` and the queuing in `check` are unchanged.

### 6. Config check: `cli/wuwei/commands/config.py`

In `run`, after the Owner block (line 62), reported, not a finding:

```python
name, levels = workspace.posture(config)
print(f'Posture: {name}')
for area in workspace.AREAS:
    mark = (' (floor)' if area in workspace.FLOORS else
            ' (security.areas)' if config['security']['areas'][area] else '')
    print(f'  {area}: {levels[area]}{mark}')
print('  owner-only actions block in every posture: deploys, merges and approvals, '
      'approve-tier messages')
if config['guards']['mode'] == 'shadow':
    print('  guards.mode = "shadow" is deprecated: set security.posture = "observe"; '
          'guards.shadow_days and guards.shadow_since keep the time box')
```

Import `workspace` (the module already imports `load_config` from it). The floor finding
needs no code here: `load_config` raises and `run` already prints it and returns 1.

### 7. Status: `cli/wuwei/commands/status.py`

- `SHADOW_NUDGE` (line 13) text: `'Observe posture has run {days} days. To enforce, set
  security.posture = "guarded" in config.toml; to keep observing, raise guards.shadow_days.
  bin/wuwei shadow report lists what would have been refused.'`
- `scan` (lines 179-185): load the config once into `config`; condition
  `workspace.posture(config)[0] == 'observe' and config['guards']['shadow_since']`.
- `scan` key selection (line 114-121): add
  `elif kind == 'guard.would_refuse' and isinstance(payload, dict): key = (kind, payload.get('guard'))`,
  and for that kind the row reason is
  `f'{payload.get("guard")}: {payload.get("reason")} (warn: security.areas.{payload.get("area")})'`
  (set after the generic `reason = ...` on line 125, like the `pr.changed` special case).
- `snapshot` line 221: `result['posture'] = workspace.posture(config)[0] if config is not None else None`
  (replaces `result['shadow']`).
- `line` lines 269-270: `if data.get('posture') not in (None, 'guarded'): parts.append(data['posture'])`.
  Still one pass: `snapshot` already loads the config once.

### 8. Signal tier: `cli/wuwei/signal.py`

- Remove `'guard.would_refuse'` from `SILENT` (line 13).
- In `classify`, before the `SILENT` test:
  `if kind == 'guard.would_refuse': return ('nudge' if payload.get('posture') in ('guarded', 'strict') else 'silent'), lane`
  (old shadow events and observe warnings stay silent).

### 9. SessionStart line: `cli/wuwei/guards/lifecycle.py`

- `SHADOW_LINE` (lines 8-10) text: `'Observe posture is on: guards record what they would refuse
  and let the call through. Records (state, events, config, verdicts, decisions) and
  owner-only actions (deploys, merges, approvals, approve-tier messages) still refuse.
  bin/wuwei shadow report lists the would-be refusals.'`
- Line 39: `if workspace.posture(config)[0] == 'observe':`.

### 10. Why: `cli/wuwei/commands/why.py`

In `refusal` (line 186-193), for a `guard.would_refuse` with an `area`, append
`f'posture: {payload["area"]} = {payload.get("level")} ({payload.get("posture")})'` after
the guard/rule/fix lines. The header and the rest are unchanged.

### 11. Writers of the posture

- `cli/wuwei/commands/init.py`: `parser.add_argument('--posture', choices=tuple(workspace.POSTURES),
  help='security posture for a new workspace: observe, guarded or strict')`; keep `--shadow`
  with help `same as --posture observe`. In `run`, line 40:
  `posture = 'observe' if getattr(args, 'shadow', False) else getattr(args, 'posture', None)`;
  refuse it with `--upgrade`/`--menu-bar` (`'--posture applies to a new workspace; set
  security.posture in config.toml'`). Lines 87-92: when `posture` is set, replace
  `'posture = "guarded"'` with `f'posture = "{posture}"'` (count 1), and for `observe` also
  the `shadow_since = ""` line as today.
- `cli/wuwei/interview.py`: replace the `guards` question (lines 169-176) with

  ```python
  {'id': 'posture', 'scope': 'workspace', 'header': 'Posture',
   'question': 'Where does WUWEI run here, and how hard should the guards stop it?',
   'choices': (
       ('Observe', 'A first week or a personal sandbox: guards record what they would refuse; '
        'records and owner-only actions still refuse.', {'security.posture': 'observe'}),
       ('Guarded', 'A real project: records, publishing and integrity block; seats, outward '
        'text and MCP warn.', {'security.posture': 'guarded'}),
       ('Strict', 'A repository that deploys or shared credentials: everything blocks.',
        {'security.posture': 'strict'})),
   'free': None},
  ```

  `settings` line 226: `(('security',), 'posture', 'observe') in rows`.
- `cli/wuwei/profiles.py`: add `'security'` to `PRIVATE` (line 21) and `NOT_LITERALS`
  (line 36).
- `templates/workspace/config.toml` lines 224-230:

  ```toml
  [security]
  required = true
  posture = "guarded" # observe, guarded or strict: what warns and what blocks; see the posture table in the security docs.
  # Per-area overrides of the posture: off, warn or block. records always blocks.
  # [security.areas]
  # mcp = "off" # integrity, mcp, publish, records, outward, seats

  [guards]
  shadow_days = 7 # Days in observe before one nudge asks to switch to guarded.
  shadow_since = "" # YYYY-MM-DD observe started; wuwei init --posture observe sets it.
  ```

  `mode` leaves the template (deprecated); `SCHEMA` keeps it.

### 12. Docs

- `docs/site/security.md`: a `## Security posture` section before `## Threat model 9.1`:
  the area table (rows integrity, mcp, publish, records, outward, seats; columns observe,
  guarded, strict), what `off`/`warn`/`block` mean, the floors (records; owner-only actions;
  MCP `scanner.mcp.block` findings under guarded and strict), which guard belongs to which
  area, and where to run each: `observe` for a first week or a personal sandbox, `guarded` for
  a real project, `strict` for a repository that deploys or shared credentials.
- `docs/specs/2026-09-24-wuwei-design.md` 9.1: append a paragraph `Security posture
  (owner, 2026-10-03, #331)` with the same table and floors, and that the posture changes
  what the cooperative guards refuse, never the hard boundaries above.
- `docs/site/configuration.md`: rows for `security.posture` and `security.areas.<area>`;
  `guards.mode` marked deprecated (`"shadow"` means `observe`); `guards.shadow_days` and
  `shadow_since` reworded for observe; the interview row `posture` (line 275); calibration
  profiles paragraph (line 285) names `security` as never exported.
- `docs/site/concepts.md`: `## Shadow mode` (line 17) becomes `## Security posture`
  (observe is the old shadow mode); fix every `#shadow-mode` link (reference.md, daily.md,
  README.md).
- `docs/site/reference.md`: `init --posture` row (line 35); the paragraphs at 277-289
  (`guard.would_refuse` payload gains `area`, `level`, `posture`; the status part is the
  posture name; the nudge text; `why` prints the posture line; the deny reason's posture
  line).
- `docs/site/daily.md` lines 61-66 and `README.md` line 99: `bin/wuwei init --posture
  observe .`, at the nudge set `security.posture = "guarded"`.

## What must not change

- Every guard module's checks and messages (only `agent_launch` is restructured, with the
  same refusals and texts); `discover`, `MODULES`, `profile_result`, `Guard`.
- `hook.refuse`, the malformed, discovery-failure and #326 config-failure paths, the
  SessionStart branch, the heartbeat bypass, `target`, `redacted_target`, `claimed`.
- Hook stdout and stderr for a refusal from a module with no area (stubs) and when no
  config is readable: byte for byte. A clean call reads no extra config.
- `mcp._gate`, `mcp.check` queuing and events (except the off early return),
  `mcp.decide`, `scanner.py`, the `profile` key and `outward.check_call`.
- `report.shadow_lines`, `wuwei shadow report`, the `guard.would_refuse` producer-only
  reservation in `commands/event.py`.

## Project Structure

```
cli/wuwei/workspace.py            AREAS, AREA_LEVELS, POSTURES, FLOORS, SCHEMA security, floor check, posture()
cli/wuwei/guards/__init__.py      AREAS, OWNER_ONLY, level(); NEVER_SHADOWED removed
cli/wuwei/commands/hook.py        posture() replaces shadow(); refusals carry the check; posture lines
cli/wuwei/guards/agent_launch.py  _seat(), check_mcp guard record
cli/wuwei/mcp.py                  NOT_CHECKED, off in check, cached wraps _cached with the mcp level
cli/wuwei/commands/config.py      Posture section, deprecation line
cli/wuwei/commands/status.py      posture field and part, observe nudge, would_refuse nudge row
cli/wuwei/signal.py               guard.would_refuse tier by posture
cli/wuwei/guards/lifecycle.py     observe line
cli/wuwei/commands/why.py         posture line for a warning
cli/wuwei/commands/init.py        --posture, --shadow alias
cli/wuwei/interview.py            posture question
cli/wuwei/profiles.py             security private
templates/workspace/config.toml   [security] posture, [guards] without mode
docs/site/{security,configuration,concepts,reference,daily}.md, README.md, design spec 9.1
tests/test_posture.py             new: resolver, floors, hook levels, config check, status, init, interview
tests/test_hooks.py, test_e2e_day.py, test_mcp.py, test_shadow.py, test_workspace.py,
tests/test_interview.py, test_calibrate.py, test_signal_status.py, test_why.py, and any test
that depends on seats, outward or MCP blocking (pin strict)
```
