# Implementation Plan: Owner-only actions are refused in indirect forms too

**Branch**: `222-indirect-owner-actions` | **Date**: 2026-09-30 | **Spec**: `specs/222-indirect-owner-actions/spec.md`

## Summary

Replace the six owner-action rules in `check_bash` with one table, one relevance function
and one argv walk, all in `cli/wuwei/guards/protect_state.py`, and run the same walk over
the script file a command runs (read with the existing `shell.script_text`). No change to
`cli/wuwei/shell.py`: relevance reuses `shell.mentions` (#205, including `script=True`),
parsing reuses `shell.normalize`, script discovery reuses `shell.script_text` and
`shell.script_path` (launcher excluded by #205). The net diff in `check_bash` is a
deletion: about 95 lines of per-action rules become about 25 lines of calls.

A prototype of exactly this design, run in a scratch copy of the tree, turned every cell
of the reproduction table into a refusal inside the workspace, kept every cell 0 outside,
kept all allow rows at 0, and passed the existing guard test files (protect_state,
decision, drafts, mcp, integrity, quiet_sweeps, launcher_relevance, owner_edits,
guard_mutation, shell, hooks) except the one decision row named below.

## Technical Context

**Language/Version**: Python 3.11+, stdlib only
**Testing**: pytest, in-process `check_bash` tables and in-process `wuwei.commands.hook.run`
**Constraints**: exits 0/1/2, fail closed, relevance before parsing, no new subprocess, no
file read for a command that does not run a local script, guard scope per spec 9.1

## Constitution Check

- One behaviour, one function: every owner-only action goes through `_owner_action`; no
  per-action copy remains (issue scope).
- Test first: each behaviour below has a failing test task ordered before it.
- Fail closed: a relevant command or script that cannot be parsed is exit 2; a non-literal
  subcommand is exit 2.
- Scope: refusals apply only when `workspace.guard_scope(payload)` finds a workspace, and
  that call happens only after the text or the walk found something (latency).
- Ponytail: no new module, no shell.py change, no config. One dict, two regexes, two
  functions.

## Changes

All in `cli/wuwei/guards/protect_state.py`.

### 1. `_wuwei_action(argv)` (line 33)

Recognise every python CLI form the mcp, drafts and watch walk (lines 342 to 345) already
accepted, so that walk can be deleted: after `python*`/`pypy*`, scan leading options; `-m`
followed by `wuwei` returns the rest; an option matching `-[A-Za-z]*mwuwei` (`-mwuwei`,
`-Pmwuwei`, `-PBmwuwei`) returns the rest; stop (return None) at the first non-option, at
`-c`, or at `-m` followed by anything else (`-m wuwei.__main__`, `-m pytest`).

```python
    if re.fullmatch(r'(?:python|pypy)[\d.]*', program):
        for index, arg in enumerate(argv[1:], 1):
            if arg == '-m' and argv[index + 1:index + 2] == ['wuwei']:
                return argv[index + 2:]
            if re.fullmatch(r'-[A-Za-z]*mwuwei', arg):
                return argv[index + 1:]
            if not arg.startswith('-') or arg in ('-c', '-m'):
                break
    return None
```

### 2. The owner table and its two regexes (new, module level)

```python
_OWNER_ACTIONS = {
    ('decision', 'outcome'): 'Decision outcomes require the owner terminal, outside agent tools.',
    ('drafts', 'approve'): 'Draft decisions require the owner terminal, outside agent tools.',
    ('drafts', 'drop'): 'Draft decisions require the owner terminal, outside agent tools.',
    ('mcp', 'decide'): 'MCP decisions require the owner terminal, outside agent tools.',
    ('integrity', 'reconfirm'): 'Integrity re-confirmation is an owner action on the host, outside agent tools.',
    ('state', 'recover'): 'State recovery is an owner action on the host, outside agent tools.',
    ('watch', 'uninstall'): 'Watch uninstall requires the owner terminal, outside agent tools.',
    ('goals', 'edit'): 'Owner memory edits are an owner action on the host, outside agent tools.',
    ('voice', 'edit'): 'Owner memory edits are an owner action on the host, outside agent tools.',
}
_OWNER_VERBS = tuple(sorted({verb for _, verb in _OWNER_ACTIONS}))
# A verb token; `_` may precede it so python snippets such as owner_edit( stay relevant.
_OWNER_VERB = re.compile(r'(?<![A-Za-z0-9])(?:' + '|'.join(_OWNER_VERBS) + r')(?![A-Za-z0-9])')
_OWNER_PAIR = re.compile(r'\b(?:' + '|'.join(rf'{g}[\s.]+{v}' for g, v in _OWNER_ACTIONS) + r')\b')
```

The reasons are the existing strings, unchanged, so every current reason assertion holds
(`owner` in the reason, `owner terminal` for watch exit 1).

### 3. `_owner_relevant(text, script=False) -> bool` (new)

Text only, no file read, no scope call:

```python
    stripped = re.sub(r"['\"\\]", '', text)
    return bool((_names_wuwei(stripped) or _OWNER_PAIR.search(stripped))
                and (_OWNER_VERB.search(stripped) or mentions(text, _OWNER_VERBS, script=script)))
```

The anchor must be literal (`_names_wuwei` or a literal pair such as `integrity.reconfirm`):
`mentions` alone answers True for any non-literal command word, which would make
`c{d,d} ..` relevant (a row in `tests/test_mcp.py` that must stay 0). `mentions` supplies
the dynamic verb cases (`$'...'`, substitutions, non-literal command words), as #205 left it.

### 4. `_owner_action(commands, text, relevant, script=False)` (new)

Returns `(code, reason)` or `None`:

1. If `relevant` and `mentions(text, ('xargs',), script=script)`: `2, 'Input-driven owner
   action; use the host terminal.'` (normalize drops `xargs`, so the walk cannot see that
   stdin supplies the verb).
2. For each command, `action = _wuwei_action(argv)`.
   - Not the CLI: if `relevant` and (`shell.is_opaque(argv)`, or the program matches
     `(?:python|pypy)[\d.]*|node|perl|ruby|php|lua`, or the program is not `grep`/`rg` and
     `_names_wuwei(' '.join(argv[1:]))`): `2, 'Opaque owner action; use the host terminal.'`
     Otherwise continue.
   - The CLI: `words = [w for w in action if not w.startswith('-')]` (drops options and
     `--`); `group, verb = (words + ['', ''])[:2]`. If `group` holds `$` or a backquote,
     or `group` is an owner group and `verb` holds `$` or a backquote: `2, 'Not a literal
     owner action; use the host terminal.'` If `(group, verb)` is in `_OWNER_ACTIONS`:
     `1, _OWNER_ACTIONS[group, verb]`.
3. `None`.

The non-literal check runs for every parsed command, relevant or not: it costs one loop
over argv lists that `normalize` already built, and it is how `bin/wuwei mcp $ACTION`
stays exit 2 without making loops such as `for i in A B; do bin/wuwei state transition
$i review; done` relevant (they are unparseable and must stay 0).

### 5. `check_bash` (line 261)

Delete lines 269 to 297 (the `mentions` import, `owner_action_text`,
`owner_outcome_relevant`, `owner_edit_relevant`, the integrity and state-recover early
returns, `mcp_relevant`, `drafts_relevant`, `watch_relevant`) and lines 311 to 367 (the
decision, owner-edit and mcp/drafts/watch walks). In their place:

```python
        from wuwei.shell import NonliteralPathError, ParseError, normalize, script_text
        from wuwei.workspace import guard_scope
        # ponytail: one script level; a script run by a script, or written and run in one
        # call, is not read. The next call that runs the saved script is.
        body = script_text(script, cwd) if root is not None else None
        if body is not None:
            relevant = _owner_relevant(script + '\n' + body, script=True)
            try:
                found = _owner_action(normalize(body), body, relevant, script=True)
            except ParseError:
                found = relevant and (2, 'Opaque owner script; use the host terminal.')
            if found and guard_scope(payload) is not None:
                return found
        owner_relevant = _owner_relevant(script)
        try:
            commands = normalize(script)
        except ParseError as exc:
            if ((owner_relevant and guard_scope(payload) is not None)
                    or _STATE_MENTION.search(script) ...   # rest of the fallback unchanged
                return 2, str(exc)
            return 0, ''
        found = _owner_action(commands, script, owner_relevant)
        if found and guard_scope(payload) is not None:
            return found
```

`root` (line 264) is already computed and is None outside a workspace, so no script file
is read there. The script text gets script-mode relevance over the command plus the body,
so `./fw.sh drafts approve x` with body `bin/wuwei "$@"` is relevant and exit 2.

## Must not change

- `cli/wuwei/shell.py`: `normalize`, `_unwrap`, `mentions`, `script_path`, `script_text`,
  `is_opaque`. No new parameter.
- `_names_wuwei`, `check_file`, `_protected*`, `_write_targets`, the directory and write
  checks after the owner rule, and the rest of the ParseError fallback in `check_bash`.
- The CLI host-terminal confirmations: `integrity._host_confirm` and its callers in
  `integrity.reconfirm`, `mcp.decide`, `commands/decision.py`, `commands/state.py`, and
  the drafts and watch commands. The guard is added defence, not a replacement.
- Every other guard; `hooks/`; no new config key, so no template or
  `docs/site/configuration.md` change.
- Existing refusal reason strings (they move into the table verbatim).

## Existing test rows that change

- `tests/test_decision.py::test_agent_tool_cannot_invoke_owner_outcome`, row
  `('python3 -mwuwei decision outcome D-3 A', 2)` becomes `1`: the shared recogniser
  treats `-mwuwei` as the CLI, as `tests/test_mcp.py` and `tests/test_drafts.py` already
  require for mcp and drafts. Still a refusal.

No other existing row changes (checked with the prototype).

## Project Structure

- `cli/wuwei/guards/protect_state.py`: `_wuwei_action`, the table, `_owner_relevant`,
  `_owner_action`, `check_bash`.
- `tests/test_owner_actions.py` (new): the issue's acceptance table.
- `tests/test_guard_mutation.py`: special mutation test for `_owner_action`.
- `tests/test_decision.py`: the one row above.

## Test fixture notes for the builder

- Workspace: `tmp_path / 'workspace'` with `.wuwei/config.toml` (empty), integrity seeded
  with `fakes.integrity.seed`, `WUWEI_WORKSPACE` and `CDPATH` removed with
  `monkeypatch.delenv(..., raising=False)`. Outside: `tmp_path / 'outside'`, a plain
  directory.
- Payload for `check_bash`: `{'cwd': str(cwd), 'tool_name': 'Bash', 'tool_input':
  {'command': command}}`.
- Script files: write `wrap.sh` with `f'#!/bin/sh\nbin/wuwei {group} {verb}\n'`, `chmod
  0o755`, into the cwd under test (workspace and outside), and run `./wrap.sh` and
  `sh wrap.sh`. Commands use the relative `bin/wuwei`; the guard never executes anything.
- Hook rows: as `tests/test_launcher_relevance.py::hook` does, monkeypatch `sys.stdin`,
  call `wuwei.commands.hook.run(SimpleNamespace(event='PreToolUse'))`; refused means
  return 2 and `permissionDecision == 'deny'`; allowed means return 0.
- Keep owner verbs (`approve`, `drop`, `edit`, `decide`, `outcome`, `reconfirm`,
  `recover`, `uninstall`) out of test function names and parametrize ids that reach
  `tmp_path`: pytest puts the test name in `tmp_path`, and any command or payload that
  carries that path would become relevant.

## Deferred

- A verb constructed at run time (`${A}stall`, `$(printf rec)over`) is not seen before
  parsing. The host-terminal confirmation anchors every action except goals and voice
  edit, whose `--file` form needs no terminal. A parse-independent anchor for owner memory
  (for example a tty check in `commands/_owner_edit.py`) belongs to a follow-up issue.
- Nested scripts and write-then-run in one call (see the `ponytail:` comment).
