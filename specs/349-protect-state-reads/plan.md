# Implementation Plan: protect_state blocks writes, never reads

**Branch**: `349-protect-state-reads` | **Spec**: `specs/349-protect-state-reads/spec.md`

## Summary

Make the state guard ask the shared classifier whether one command only reads, instead of
its private reader list. Two predicates already inlined in `shell._classify` move out as
small functions (`reads`, `inline_code`) that `_classify` and `protect_state` both call. The
guard then: skips operands of a read-only command and of an interpreter running a file;
keeps the "Opaque interpreter" refusal for inline code only; skips its records clauses in
the unparsed path when the shape is read-only; and returns a one-line reason naming the CLI
command for the refused record. The extraction also fixes the `IndexError` in `_classify`.
A prototype of these edits (in a scratch copy) passed every existing test in
`test_protect_state.py`, `test_cli_known_command.py`, `test_canary.py`, `test_owner_edits.py`,
`test_scope_first.py`, `test_posture.py`, `test_hooks.py`, `test_guard_mutation.py` and
`test_decision.py`, and the full suite apart from location-dependent status-line tests
that also pass in the worktree.

## Technical Context

Python 3.11+ stdlib only; pytest for tests. No new module, no new dependency. Latency: the
read check is set lookups and runs before the per-operand `_protected` calls it replaces, so
read commands get cheaper; `inline_code` is one regex per argument of an interpreter command.

## Constitution Check

- I (stdlib): yes. II (exits): only the read shapes in the spec change from 1 or 2 to 0;
  every write refusal keeps its code. III: the read rule lives once in `shell.reads`, used by
  the classifier and the state guard. IV: every behaviour has a failing test first (tasks).
- V (ponytail): two extractions of code that already exists, one six-branch hint function,
  one condition each at three spots. No new layer, no config.
- VII (security): the protected set, the owner-action table, credentials, the records floor
  and every write refusal are unchanged; only commands the shared classifier proves read-only,
  and interpreters running a file, stop counting operands as writes. Unknown programs keep
  today's conservative refusal.

## Changes

### 1. `cli/wuwei/shell.py` (FR-001, FR-002, FR-006)

- `READ_ONLY` (line 600): add `'less'`.
- New `reads(argv, cwd=None)`, placed above `_classify`: the body of today's `safe`
  computation, moved verbatim:
  - `sed`: options exactly `['-n']` and the first operand matches `[0-9,$]+p` (from lines
    881-884);
  - `find`: no `_FIND_ACTIONS` argument (lines 885-886);
  - otherwise `name in READ_ONLY`, or argv non-empty, no `$` in the arguments,
    `known_cli(argv[0], cwd)` and `commands.read_only(args)` (line 851).
  An empty argv returns False (this is the `IndexError` fix). Import `commands` inside the
  function as `_classify` does.
- New `inline_code(argv)`: True when `argv[0]` is an `_INTERPRETER` and an argument matches
  the inline flag pattern of lines 870-872 (`-c` for python and pypy, `_SNIPPET` letters for
  the others, `--eval`, `--eval=`). Do not name it `inline`: `_classify` has a local of
  that name.
- `_classify`: line 851 becomes `safe = reads(argv, cwd)`; delete the `sed` and `find`
  branches (now inside `reads`); the interpreter branch condition becomes
  `fed == 'heredoc' or inline_code(argv)`. Behaviour is unchanged: for `sed` and `find` no
  earlier `elif` branch applies, and the `literal` test only ever mattered for the CLI case
  (a write already makes the command non-read-only).

### 2. `cli/wuwei/guards/protect_state.py`

a. `_write_targets` (FR-001, FR-003), replacing lines 358-362:

```python
    # Reader arguments are text; their redirects are checked from command.writes.
    # rg --pre runs a command on each searched file, so those operands are checked.
    if program in _READERS and not (
            program == 'rg' and any(a == '--pre' or a.startswith('--pre=') for a in argv[1:])) or reads(argv, cwd):
        return []
    # #349: a file or module the interpreter runs is unseen; its operands are data. Inline
    # code naming state is refused in check_bash.
    if re.fullmatch(_INTERPRETER, program) and not inline_code(argv):
        return []
```

`'cat', 'less', 'jq'` leave this line: the shared set covers them. Import `reads` and
`inline_code` from `wuwei.shell` inside the function (the module keeps its lazy imports).
Reuse the module's existing `_INTERPRETER` (line 74).

b. `check_bash`, interpreter rule (FR-003), lines 479-482: the condition
`re.fullmatch(r'(?:python|pypy)...', program) and command.argv[1:4] != ['-P', '-m', 'wuwei']`
becomes `inline_code(command.argv)`; the state-mention test and the reason stay. Add
`inline_code` to the existing `from wuwei.shell import ...` line in `check_bash`.

c. `check_bash`, unparsed path (FR-004), line 454: prefix the refusal condition with
`not shape.readonly and (...)`. A read-only shape writes nothing (the classifier sets
`readonly` False for any write other than `/dev/null`, `/dev/stdout`, `/dev/stderr` and fd
duplication, and for any publisher, inline code or input-driven command), so none of the
three records clauses can apply. The `cd` rule, the `readonly` pass and the UNPARSED line
after it stay in their order.

d. Reason text (FR-005). Replace `_STATE_HINT` with the generic one-liner and add one
function next to `_protected_name`:

```python
_STATE_HINT = ('State and config files are protected; use the wuwei CLI for state changes; '
               'owner edits run outside agent tools.')


def _hint(path):
    """#349: the one-line reason for a refused write names the command that makes it."""
    parts = tuple(part.casefold() for part in path.parts)
    tail = parts[len(parts) - parts[::-1].index('.wuwei'):] if '.wuwei' in parts else ()
    if tail == ('config.toml',):
        return ('config.toml is protected: the owner runs wuwei config set <key> <value> '
                'in a host terminal, outside agent tools.')
    if tail[:1] == ('days',) and tail[-1:] in (('state.json',), ('state.snapshot.json',)):
        return ('Day state is protected: change it with the wuwei CLI, wuwei state set '
                '<path> <value> or wuwei state transition <item> <phase>.')
    if tail[:1] == ('days',) and tail[-1:] == ('events.jsonl',):
        return 'events.jsonl is protected: append with the wuwei CLI, wuwei event <kind> [payload].'
    if tail[:1] == ('ziran',):
        return ('Registry records are protected: wuwei mcp check writes them and the owner '
                'runs wuwei mcp decide in a host terminal, outside agent tools.')
    if tail in (('memory', 'goals.md'), ('memory', 'voice.md')):
        return ('goals.md and voice.md are protected: after the morning gate the planner runs '
                'wuwei goals edit --file <draft> or wuwei voice edit --file <draft>; other '
                'edits are the owner\'s, outside agent tools.')
    if tail[:1] == ('integrity',):
        return ('Integrity records are protected: the owner runs wuwei integrity reconfirm '
                'in a host terminal, outside agent tools.')
    return _STATE_HINT
```

The exact wording may change; each line must keep the substrings existing tests assert:
`CLI` for day `state.json` and `events.jsonl` (`test_file_guard`, `test_shell_state_guard`),
`owner` and `outside agent tools` for `config.toml` (`test_config_is_protected`),
`outside agent tools` for the generic reason (`test_calibration_snapshot_is_protected`,
`test_interview_answers_are_protected`). No newline in any reason.

Call sites:
- `check_file` line 296: `return 1, _hint(_path(value, cwd).resolve())`, where `value` is
  the field already read (bind it once: `value = _input(payload, field)`).
- `check_bash` lines 498-501: find the first protected target and return its hint:

```python
                hit = next((target for target in targets if _protected(
                    target, directory, root, program in ('rm', 'mv', 'chmod', 'chown'))), None)
                if hit is not None:
                    return 1, _hint(_path(hit, directory).resolve())
```

- `check_bash` line 496 (`git apply` in a workspace): keeps the generic `_STATE_HINT`.

### 3. `docs/site/agent.md` (seat guide)

Extend the bullet "Records under `.wuwei/` ... never through Edit, Write or a shell
redirect." with one clause: reading them (Read, Grep, `cat`, `grep`, `jq`, `ls`) is always
allowed. Keep the page at or under 100 lines (`test_agent_guide_ships_and_is_linked`); it
has 98 today.

## What must not change

- `_protected_name`, `_protected` and the protected set; the honeytoken decoy handling.
- `_OWNER_ACTIONS`, `_owner_action`, `_owner_relevant`, `_gate_edits` and `_READERS` (used by
  `_owner_action`).
- The `cd`, `pushd`, `popd` rules and `WORKSPACE_ROOT`; the #347 UNPARSED table and
  `shell.unread`.
- `GUARDS` matchers: Read, Grep and Glob are not matched, so they pass as before.
- `security.reads_honeytoken` and the traces guard; `tests/test_canary.py` unchanged.
- Every existing test expectation. If one has to change, stop: the design is wrong.

## Tests (all new, in existing files)

- `tests/test_protect_state.py`: one table through `wuwei.commands.hook.run` for the read
  shapes in User Story 1 across `observe`, `guarded`, `strict` (exit 0, no `hook.refusal` or
  `guard.would_refuse` event); one table of writes with the expected command substring and
  no newline in the reason (`check_file`, `check_bash`) plus the hook refusal in each
  posture; credentials writes refused; Read, Grep and Glob pass with no event.
- `tests/test_cli_known_command.py` or a small block in `tests/test_protect_state.py`:
  `shell.reads` and `shell.inline_code` tables, `shell.classify('less x').readonly`, and
  `shell.classify` on `for f in a; do cat $f; done > out.txt` returning a Shape (no raise).

Fixture notes: reuse the `workspace` fixture and `payload` helper in
`tests/test_protect_state.py`; write `[security]\nposture = "<p>"` to `.wuwei/config.toml`
per posture, as `tests/test_cli_known_command.py` does; read events from
`.wuwei/days/*/events.jsonl`; create `decisions/D-1.md`, `.wuwei/ziran/a/report.json`,
`.wuwei/charters/a.md`, `.wuwei/charters/b.md` and a `read_reports.py` that only reads,
inside `tmp_path`. Use the neutral fixture date the file already uses (`2026-09-28`).

## Deferred

- Widening the shared read set (`stat`, `file`, `du`, `echo`, `printf`, `cut`, `tr`, `rg`)
  for every guard: changes the #347 decision table for the publish guards.
- A PreToolUse read refusal for `.wuwei/env` or the credentials directory: a design change
  to the canary and honeytoken flow (#105), not this issue.
