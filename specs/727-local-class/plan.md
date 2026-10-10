# Implementation Plan: the terminal and other local tools are a local class

**Branch**: `727-local-class` | **Spec**: `specs/727-local-class/spec.md`

## Summary

One new channel value, `local`, at the two shared spots that already decide a tool's channel and
a hook's view of a call:

1. `guards.outward.resolve` returns `{'local'}` for the built-in local shapes and for a server
   the owner aliased `local`; `_check` passes a local call (canary floor only).
2. `commands.hook.run` presents a `mcp__terminal__run_in_terminal` PreToolUse call to the guards
   as the Bash call it types, so every Bash guard judges the command with no change to any of
   them.

Then the small consumers: the schema choice, the learn card, `outbound tiers`, docs, the 9.2
invariant.

## Technical Context

Python 3.11+, stdlib only; pytest for tests. No new module, no new dependency, no new config
key. Run tests with `python -m pytest -q` from the repository root with the pipeline's
interpreter.

## Constitution Check

- I stdlib only: yes. II fail closed: a malformed terminal payload is exit 2 at the hook; the
  canary floor stays on local calls. III one behaviour, one function: `resolve` decides the
  class, `as_bash` decides the hook's view. IV test first: tasks.md orders each test before its
  code. V ponytail: no new layer; the Bash guards are reused by changing the payload they see,
  not by teaching four guards a second tool name. VII security: `local` is never learned
  without the owner's card; `--as` still cannot lower a resolving channel; exact server names,
  no substring match. Workflow (#530): the rule goes into design 9.2 and
  `tests/test_invariants.py`.

## Changes

### 1. `cli/wuwei/workspace.py`

- `:240` `outward.servers` choices: add `"local"` to
  `("slack", "tracker", "code_host", "docs", "mail", "other")`. This also widens
  `commands/outbound.py:127` `CHANNELS` (`--as local`) with no edit there.
- `:627` bump `CONFIG_CACHE_VERSION` by one (schema changed). If another item bumped it on main
  first, take the next number.

### 2. `cli/wuwei/guards/outward.py`

- Next to `VOCABULARY` (`:52-60`), add:

  ```python
  # #727: servers that act only on the owner's machine; never drafted, the command guards judge what runs.
  LOCAL_SERVERS = ('terminal', 'Claude_Preview', 'Claude_Code_iOS_Simulator', 'computer-use')
  LOCAL = (rf"mcp__(?:{'|'.join(map(re.escape, LOCAL_SERVERS))})__.*"
           r'|mcp__Claude_Browser__preview_.*')
  ```

  Exact server names, `re.fullmatch`, case-sensitive: `mcp__plugin_x_terminal__run_job` and
  `mcp__Claude_Browser__navigate` do not match.
- `resolve` (`:63-84`): after `if channels: return channels` (`:80-81`) and before the
  vocabulary (`:82`), add `if re.fullmatch(LOCAL, tool): return {'local'}`. Order stays: reads
  return first (unchanged), then the owner alias (an alias `local` returns `{'local'}` with no
  new code; an alias of a built-in local server to an outward channel wins), then the tool
  rules, then `LOCAL`, then the vocabulary.
- `_check`: after the scope recompute (`:162-163`) and before `if not channels: return
  _unmatched(...)` (`:164`), add:

  ```python
  if channels == {'local'}:  # #727: never drafted or blocked by the outward rules
      from wuwei import security
      return security.outbound(payload.get('tool_input'), root) if policy is outward.check_tier else (CLEAN, '')
  ```

  A local call outside a workspace already returns clean at `:159-161`. No draft, no tier row,
  no lint, no `outward.unknown_tool` event.

### 3. `cli/wuwei/commands/hook.py`

- Add a constant and one function near `validate` (`:359`):

  ```python
  TERMINAL = 'mcp__terminal__run_in_terminal'  # #727: types one shell command line


  def as_bash(payload):
      """#727: a terminal tab's command is judged as the Bash call it types, in the tab's cwd."""
      if payload.get('tool_name') != TERMINAL or payload['hook_event_name'] != 'PreToolUse':
          return payload
      inputs = payload.get('tool_input')
      if (not isinstance(inputs, dict) or not isinstance(inputs.get('command'), str)
              or not isinstance(inputs.get('cwd', ''), str)):
          raise ValueError(f'terminal command and cwd must be strings; {PAYLOAD}')
      cwd = Path(payload['cwd']) / Path(inputs.get('cwd') or '.').expanduser()
      return {**payload, 'tool_name': 'Bash', 'tool_input': {'command': inputs['command']}, 'cwd': str(cwd)}
  ```

- `run` (`:35-39`): inside the existing `validate` try, after `validate(payload, args.event)`,
  `payload = as_bash(payload)`. A raise there is the existing malformed refusal (exit 2). Every
  later step (scope at `:42-49`, `reaches_workspace`, `SELECTION` at `:63`, every guard, the
  refusal record and `posture`) then sees the Bash view. Nothing else in the hook changes.

### 4. `cli/wuwei/commands/outbound.py`

- `MODE_TEXT` (`:277-286`): add `'local': 'calls act only on your machine and are never drafted; the command guards still judge what runs.'`
- `record` (`:305-364`): with `local = proposal['channel'] == 'local'`:
  the question drops `, mode {default}` for local (`Connector <server> is local?`); the approve
  row's consequence is `MODE_TEXT['local']` without the `Mode <default>:` prefix; the mode
  option rows (`:333-334`) are skipped for local. Approve and Defer stay; `apply` needs no
  change (approve writes the `outward.servers` alias).
- `learn` (`:531`): `card = ... or channel in ('other', 'local')` so `learn = "auto"` never
  records `local` without the owner, in any posture.
- `tiers` (`:69-87`): after the umbrella line, print one line:

  ```python
  from wuwei.guards.outward import LOCAL_SERVERS
  owned = [name for name, found in config['outward']['servers'].items() if found == 'local']
  print(f"{'-':<6}{'local':<9}{', '.join([*LOCAL_SERVERS, 'Claude_Browser preview tools', *owned])}: "
        'local, never drafted or blocked by these rows; the command guards judge what runs')
  ```

### 5. Docs and template (FR-008)

- `docs/site/configuration.md:420`: the `outward.servers` row lists `local` and says local
  servers (built in: terminal, file preview, simulator, computer-use) pass the outward guard;
  the command guards judge the terminal's command.
- `docs/site/security.md:68`: one sentence after the channel order: the built-in local servers
  and a server aliased `local` act only on the owner's machine and pass (the canary floor
  stays); a `run_in_terminal` command is judged by the Bash guards.
- `templates/workspace/config.toml:199`: the alias comment lists `local`.

### 6. Design 9.2 and the invariant walk (FR-007)

- `docs/specs/2026-09-24-wuwei-design.md` 9.2 table, appended as the last row (the id is the
  id the orchestrator reserved for this item):
  `| I65 | A local tool passes the outward guard in every posture, and a run_in_terminal command is judged by the Bash guards as the same command through Bash | per posture, through the hook, run_in_terminal with a plain command and with a day state.json write, against the same command through Bash; check_tier on open_terminal_tab | #727; one shape in guards.outward.resolve and one view in hook.as_bash |`
- `tests/test_invariants.py`: `i65(case, rules)` memoized per posture like `i52`, using
  `rules.hook(posture, ...)` and `rules.bash(...)`; register it in the checks map (`:1324`)
  and `READS` with `(0,)`.

## What must not change

- `tool_kind`, `WRITES`, `READS`, `_unmatched`, `VOCABULARY`: an unknown non-local connector is
  refused or nudged exactly as today.
- `outward.classify`, `table`, `DEFAULT_TIERS`, `AUDIENCES`: `local` is not an audience and adds
  no tier row.
- The Bash guards (`commit_push`, `deploy`, `pr`, `protect_state`) and `guards.MODULES`: no
  edit; they see the Bash view.
- `--as` still cannot change a channel `resolve` already gives (`outbound.py:467-470`).
- PostToolUse, SessionStart and the other events: the hook rewrites only PreToolUse.
- Reads of local servers (`read_terminal`, `list_terminal_tabs`) pass as reads, as today.

## Tests (files)

- `tests/test_outward.py`: local pass per tool and posture, canary floor, exact shapes, alias.
- `tests/test_hooks.py`: `as_bash` view and the hook on run_in_terminal (plain, refused,
  cwd, malformed).
- `tests/test_outbound_learn.py`: `--as local` card, shape without `--as`, auto still cards,
  approve records the alias.
- `tests/test_outbound.py`: `test_outbound_tiers_prints_table` gains the local line (`len(lines)`
  14 to 15).
- `tests/test_invariants.py`: the 9.2 row and its check.
