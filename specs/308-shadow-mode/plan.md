# Implementation Plan: Shadow mode

**Branch**: `308-shadow-mode` | **Date**: 2026-10-02 | **Spec**: [spec.md](spec.md)

## Summary

One decision point: `hook.run` already collects every guard's refusal before turning them
into an exit code. Tag each refusal with its guard module, and after the loop, only when
something refused, read `guards.mode` once. In shadow mode, record each refusal from a
module outside `NEVER_SHADOWED` as `guard.would_refuse` and drop it; the rest go through
the unchanged `refuse` path. Everything else is a reader of those events (report, status)
or a writer of the config (init, interview), each a few lines in the function that already
owns that surface.

## Technical Context

Python 3.11+ stdlib only; pytest for tests. No new dependency, no new state key, no new
module outside `cli/wuwei/commands/shadow.py` (a command needs its own module).

## Constitution Check

- I stdlib: yes. II fail closed: an unreadable config enforces; an unrecordable shadow
  event enforces; a corrupt events file makes the report exit 2 (`watch.records`).
- III one behaviour, one function: shadow decision in `hook.shadow`; grouping in
  `report.shadow_lines`, used by both the day report and `wuwei shadow report`.
- IV test first: tasks.md orders every test before its code.
- V ponytail: no per-guard flag, no guard edits, N and the never-shadowed set are
  constants, `shadow_days` is the only new tunable besides the mode (the issue asks for it).
- VII security: records, integrity, owner actions and deploys never shadow (A3); the
  `pr` guard conflict is raised in spec A4, not resolved silently.

## Design

### 1. Config: `cli/wuwei/workspace.py`

- `SCHEMA` (after `"profile"`, line 107):
  `"guards": {"mode": (str, "enforce", ("enforce", "shadow")), "shadow_days": (int, 7, 1), "shadow_since": (str, "")},`
- `load_config`, next to the `deploy.deny` check (line 437): when
  `config['guards']['shadow_since']` is nonempty, `date.fromisoformat` it inside a
  `try`; on `ValueError` raise
  `ConfigError('guards.shadow_since: expected YYYY-MM-DD or ""')`. Also require the exact
  `YYYY-MM-DD` shape (`re.fullmatch(r'\d{4}-\d{2}-\d{2}', value)`), because
  `fromisoformat` accepts `20261002` and the report compares day directory names as
  strings.
- `templates/workspace/config.toml`: append at the end

  ```toml
  [guards]
  mode = "enforce" # enforce, or shadow: guards record what they would refuse; see wuwei shadow report
  shadow_days = 7 # days in shadow before one nudge asks to switch to enforce
  shadow_since = "" # YYYY-MM-DD the shadow week started; wuwei init --shadow sets it
  ```

  `init --upgrade` adds the table to existing workspaces through `_migrated_config`
  unchanged.

### 2. Never-shadowed set: `cli/wuwei/guards/__init__.py`

After `MODULES` (line 31):

```python
# Shadow mode (#308) never relaxes these modules: WUWEI's own records, config and owner
# actions (protect_state), the integrity gate, and the deployment ban (constitution VII).
NEVER_SHADOWED = frozenset({'protect_state', 'integrity', 'deploy'})
```

### 3. The decision point: `cli/wuwei/commands/hook.py`

- Import `NEVER_SHADOWED` with the existing guards import.
- In `run`, keep `reasons` but collect refusals with their module:
  line 76 becomes `refusals.append((guard.check.__module__.rsplit('.', 1)[-1], message))`
  (`reasons, context = [], []` becomes `refusals, context = [], []`). Right after the loop:

  ```python
  reasons = [message for _, message in refusals]
  if (refusals and args.event != 'SessionStart'
          and payload.get('session_id') != HEARTBEAT_SESSION):
      reasons = shadow(payload, refusals, root)
  ```

  The SessionStart branch and everything after it stay as they are and keep using
  `reasons`. `root` is the workspace `run` already resolved at its top (line 37-41).
- New functions in the same file:

  ```python
  def shadow(payload, refusals, root):
      """Shadow mode (#308): record refusals outside NEVER_SHADOWED; return the enforced reasons."""
      from wuwei import state, workspace
      try:
          shadowing = root is not None and workspace.load_config(root)['guards']['mode'] == 'shadow'
      except BaseException:
          shadowing = False  # An unreadable config enforces, exactly as before shadow mode.
      reasons = []
      for guard, reason in refusals:
          if not shadowing or guard in NEVER_SHADOWED:
              reasons.append(reason)
              continue
          try:
              state.append_event('guard.would_refuse', {
                  'guard': guard, 'reason': reason, 'target': target(payload),
                  'session': payload['session_id'], 'item': claimed(root, payload['session_id'])}, root)
          except BaseException as exc:
              print(f'wuwei hook: could not record shadow refusal: {exc}', file=sys.stderr)
              reasons.append(reason)
      return reasons


  def target(payload):
      """The normalised Bash command, else the file path, else the tool or event name."""
      inputs = payload.get('tool_input') if isinstance(payload.get('tool_input'), dict) else {}
      command = inputs.get('command')
      if isinstance(command, str):
          from wuwei import shell
          try:
              return '; '.join(shlex.join(found.argv) for found in shell.normalize(command))
          except Exception:
              return command
      return next((inputs[key] for key in ('file_path', 'notebook_path', 'path')
                   if isinstance(inputs.get(key), str)),
                  payload.get('tool_name') or payload['hook_event_name'])


  def claimed(root, session):
      """The first item this session claims today, or None; never blocks a shadowed refusal."""
      from wuwei import state
      try:
          claims = state.read_state(root).get('claims', {})
          return next((item for item, holder in sorted(claims.items()) if holder == session), None)
      except Exception:
          return None
  ```

  `shlex` is imported at module top. The mode is read at most once per process and never
  on a clean call, so the bench budgets do not move. `refuse` is unchanged: it still writes
  `hook.refusal` for the enforced reasons only.

### 4. Producer-only event

- `cli/wuwei/commands/event.py` `EVENT_PRODUCERS`: `'guard.would_refuse': 'wuwei hook (shadow mode)',`.
- `cli/wuwei/signal.py` `SILENT`: add `'guard.would_refuse'` (the owner reads it in the
  report; it never pages or nudges by itself).
- `tests/test_signal_status.py::test_emitted_kinds_have_intended_tiers` `expected`: add
  `'guard.would_refuse': 'silent'` (the emitted-kinds scan finds the new literal in
  `hook.py`).

### 5. SessionStart line: `cli/wuwei/guards/lifecycle.py`

In `session_start`, `root, _ = context` becomes `root, config = context`; after the memory
block append, when `config['guards']['mode'] == 'shadow'`:

```python
SHADOW_LINE = ('Shadow mode is on: guards record what they would refuse and let the call '
               'through. State, events, config, integrity, owner actions and deploys still '
               'refuse. bin/wuwei shadow report lists the would-be refusals.')
```

as a module constant; the guard returns 0 for it (it is context, not a finding).

### 6. Report: `cli/wuwei/report.py`

```python
FALSE_POSITIVE_AFTER = 3  # issue N: a form refused more than this with no later page


def shadow_lines(directories):
    """Shadow refusals in day directories (oldest first): per guard a count and its three
    most frequent forms, then forms refused more than FALSE_POSITIVE_AFTER times with no
    page-tier event after their first refusal. [] when there are none."""
```

- Read each directory with `watch.records(directory / 'events.jsonl')` (fails closed on a
  corrupt line); keep a running position over all events; a non-`guard.would_refuse` event
  with `signal.classify(event, {})[0] == 'page'` sets `last_page = position`.
- Form: `' '.join(str(payload.get('target', '')).split()[:3])`.
- Use `collections.Counter` for guards and per-guard forms; record each `(guard, form)`
  first position.
- Output (exact shape):

  ```
  - commit_push: 5 (git push --force: 4, git push origin: 1)
  - pr: 1 (gh pr create: 1)

  Candidates for a guard fix or a calibration proposal:
  - commit_push: git push --force (4 times, no later incident)
  ```

  guards by `most_common()`; candidates listed as `none` when empty.
- `build`: after the `## Carry` block (line 78-82) and before `if level == 'brief':`
  (line 83):

  ```python
  shadow = shadow_lines([day])
  if shadow:
      lines += ['', '## Shadow', *shadow]
  ```

  With no events the report text is unchanged.

### 7. Command: `cli/wuwei/commands/shadow.py` (new)

```python
"""Show what the guards would have refused in shadow mode."""

from wuwei import report, watch, workspace


def register(subparsers):
    parser = subparsers.add_parser('shadow', help='Show what shadow mode would have refused')
    parser.add_argument('action', choices=('report',))
    parser.set_defaults(func=run)


def run(args):
    root = workspace.find_workspace()
    since = workspace.load_config(root)['guards']['shadow_since']
    days = [day for day in reversed(watch.days(root)) if day.name >= since]
    print('\n'.join(['# WUWEI shadow report', '', *(report.shadow_lines(days) or ['none'])]))
    return 0
```

`'' <= name` holds for every day, so an empty `shadow_since` reads all days. Errors exit 2
through `__main__`.

### 8. Status: `cli/wuwei/commands/status.py`

- `scan`: after the planner-stale block (before `rows = sorted(...)`, line 174):

  ```python
  if (directory.parents[1] / 'config.toml').is_file():
      guards = workspace.load_config(directory.parents[2])['guards']
      if guards['mode'] == 'shadow' and guards['shadow_since']:
          days = (today - date.fromisoformat(guards['shadow_since'])).days
          if days >= guards['shadow_days']:
              current[('guards.shadow',)] = {'tier': 'nudge', 'source': 'guards.shadow',
                                             'lane': 'Work', 'reason': SHADOW_NUDGE.format(days=days)}
  ```

  `SHADOW_NUDGE = ('Shadow mode has run {days} days. To enforce the guards, set '
  'guards.mode = "enforce" in config.toml; to keep shadowing, raise guards.shadow_days. '
  'bin/wuwei shadow report lists what would have been refused.')`. Import `date`. One
  keyed row, so one nudge however often status runs.
- `snapshot`: after `config = ...` (line 208):
  `result['shadow'] = config is not None and config['guards']['mode'] == 'shadow'`.
- `line`: right after the nudges part, `if data.get('shadow'): parts.append('shadow')`.

### 9. Writers of the mode

- `cli/wuwei/commands/init.py`: `parser.add_argument("--shadow", action="store_true",
  help="start with guards in shadow mode")`. In `run`, first lines: `if getattr(args,
  'shadow', False) and (getattr(args, 'upgrade', False) or getattr(args, 'menu_bar',
  False)): raise ValueError('--shadow applies to a new workspace; set guards.mode in
  config.toml')`. After `shutil.copytree` (line 75-76), when `args.shadow`, rewrite
  `Path(staging) / 'config.toml'` with `.replace('mode = "enforce"', 'mode = "shadow"', 1)`
  and `.replace('shadow_since = ""', f'shadow_since = "{workspace.now().date().isoformat()}"', 1)`
  before `integrity.initialize`.
- `cli/wuwei/interview.py`: append to `QUESTIONS` after `verbosity`:

  ```python
  {'id': 'guards', 'scope': 'workspace', 'header': 'Guards',
   'question': 'How should the guards start on this project?',
   'choices': (
       ('Enforce', 'Every guard refuses from the first command.', {'guards.mode': 'enforce'}),
       ('Shadow first week', 'Guards record what they would refuse for guards.shadow_days days; '
        'state, integrity, owner actions and deploys still refuse.', {'guards.mode': 'shadow'})),
   'free': None},
  ```

  `settings`: build the list as today, then
  `if (('guards',), 'mode', 'shadow') in rows: rows.append((('guards',), 'shadow_since', workspace.now().date().isoformat()))`.
  Choice effects stay static, so `effects` and the widget test keep working.

### 10. Docs

- `docs/site/configuration.md`: rows for `guards.mode`, `guards.shadow_days`,
  `guards.shadow_since` (pinned by `test_every_template_config_key_is_documented`); the
  `guards` question in the owner interview section.
- `docs/site/reference.md`: `| \`bin/wuwei shadow report\` |` row in `## Commands` (pinned by
  `test_reference_lists_every_cli_command`); `init --shadow`; the `shadow` status-line part
  and the `guards.shadow` nudge; the `guard.would_refuse` event and its payload.
- `docs/site/concepts.md`: a `## Shadow mode` section after `## Guards`: what shadows, what
  never does (records, config, integrity, owner actions, deploys), the heartbeat exception,
  and that the merge-policy refusals shadow (spec A4).
- `docs/site/daily.md`: in `## 2. Configure`, the first-week path: `init --shadow`, read
  `bin/wuwei shadow report` and the day report, switch to enforce at the nudge.
- `README.md` `## Quick start`: offer `bin/wuwei init --shadow .` as the first-week path.

## What must not change

- Every guard module's code and its `GUARDS` table; `discover`, `MODULES`, `profile_result`.
- `hook.refuse`, the malformed and discovery-failure paths, the SessionStart branch, the
  heartbeat non-recording of `hook.refusal`.
- Enforce-mode output byte for byte: hook stdout and stderr, the day report text, the
  status line (only `status --json` gains `shadow: false`).
- No new `state.RESERVED` key; `guard.would_refuse` is not writable through `wuwei event`.

## Project Structure

```
cli/wuwei/workspace.py            SCHEMA guards table, shadow_since check
cli/wuwei/guards/__init__.py      NEVER_SHADOWED
cli/wuwei/commands/hook.py        shadow, target, claimed; refusals tagged by module
cli/wuwei/commands/event.py       EVENT_PRODUCERS entry
cli/wuwei/signal.py               SILENT entry
cli/wuwei/guards/lifecycle.py     SHADOW_LINE in session_start
cli/wuwei/report.py               shadow_lines, day report section
cli/wuwei/commands/shadow.py      new: wuwei shadow report
cli/wuwei/commands/status.py      shadow nudge in scan, shadow in snapshot and line
cli/wuwei/commands/init.py        --shadow
cli/wuwei/interview.py            guards question, shadow_since in settings
templates/workspace/config.toml   [guards]
docs/site/{configuration,reference,concepts,daily}.md, README.md
tests/test_shadow.py              new: hook, report, command, status, init, interview tests
tests/test_hooks.py, tests/test_signal_status.py, tests/test_interview.py, tests/test_workspace.py
```
