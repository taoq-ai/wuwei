# Implementation Plan: owner confirmations are y/N or a session question, and a decision is one command

**Branch**: `354-owner-confirm` | **Spec**: `specs/354-owner-confirm/spec.md`

## Summary

Three shared spots, each changed once:

1. `integrity._host_confirm` asks `Confirm? [y/N]` instead of reading back the digest. All
   nine callers keep their digest logic and only rewrite their prompt text.
2. A decision is one command. A new `wuwei decide` dispatches to the two existing paths
   (`mcp.decide`, `commands/decision.owner_outcome`). Both write the record through one new
   `decision.owner_record`. Under observe and guarded, the #357 gate allowance is widened
   from goals and voice to `D-n` ids, so the planner can record an answer it asked with
   AskUserQuestion. One `sessions.gate_topics` serves the hook and the CLI.
3. Workspace discovery. `wuwei --workspace <path>` sets `WUWEI_WORKSPACE`. `wuwei mcp`
   honours the explicit selection. The no-workspace reason names both, and `setup` prints
   the export line once.

## Technical Context

Python 3.11+ stdlib only; pytest dev-only. Run `python -m pytest -q` from the repository
root. No new module except `cli/wuwei/commands/decide.py` (a command needs its own module:
`__main__` discovers commands by module name). No new state key or event kind: `gate_asked`
and `gate.asked` exist (#357), as do `decision.decided` and `mcp.decided`.

## Constitution Check

- I stdlib: yes. II exits: the decide command returns 0/1/2 from the paths it calls; a bad
  `--note` or no workspace is 2 with a reason. III one behaviour, one function: confirmation
  in `_host_confirm`, record writing in `decision.owner_record`, session question lookup in
  `sessions.gate_topics`. IV test first: tasks.md orders each test before its code.
  V ponytail: no new abstraction beyond those three functions and one command module.
  VII security: seats stay refused by the hook (the `agent_id` check is unchanged), strict
  keeps the host terminal, and every `D-n` word in an allowed command must have been asked.

## Design

### 1. `cli/wuwei/integrity.py` `_host_confirm` (lines 285-304)

```python
def _host_confirm(fingerprint, *, prompt=None):
    # A local friction boundary, not proof against a same-uid process (spec 9.1). The caller
    # computes, records and compares the digest; the owner answers y/N and never types it (#354).
    ...  # /dev/tty open and isatty checks unchanged
            terminal.write((prompt or f'Plugin installation {fingerprint[:12]} on this host.')
                           + '\nConfirm? [y/N] ')
            terminal.flush()
            return reader.readline().strip().lower() in ('y', 'yes')
```

`reconfirm` (line 312) keeps calling `(confirm or _host_confirm)(result.data)` and keeps
recording the full fingerprint in `confirmation.json`.

### 2. Caller prompts (text only; digest code untouched)

Each prompt says what is confirmed and has no "type:". The helper adds `Confirm? [y/N]`.

| File:line | New `prompt=` |
| --- | --- |
| `mcp.py:591` `_proceed_unmeasured` | `f"Seats will use {', '.join(names)} without a registry measurement."` |
| `mcp.py:652` `decide` | `f'{identifier}: record {option}.\n{fields["Context"]}'` (use `fields, scores = decision.evaluate(text)` at line 646; `Context` holds the findings table and `Reports:`) |
| `drafts.py:148` | `f"Send this draft to {row['destination']}:\n{text}"` |
| `remote.py:131` | `f'Acknowledge the refused sender messages {", ".join(ids)} on this host.'` |
| `commands/config.py:199` | `f'Apply the {what} above.'` |
| `commands/state.py:34` | `"Restore today's state from its snapshot."` |
| `commands/doctor.py:662` | `'Apply the fixes above.'` |
| `commands/decision.py:114` | replaced by section 4 |
| `integrity.py:312` | default prompt (short fingerprint) |

### 3. `cli/wuwei/sessions.py`: `gate_topics(root, session_id)`

Move the body of `protect_state._gate_edits` (lines 116-125, minus the `agent_id` test)
here:

```python
def gate_topics(root, session_id):
    """(records today's planner session asked through the gate, caller is that planner);
    strict asks nothing, so the owner runs the command (#357, #354)."""
    if not session_id:
        return frozenset(), False   # before any state read: a host terminal has no session
    data = state.read_state(root)
    if session_id != data.get('planner_session_id'):
        return frozenset(), False
    if workspace.posture(workspace.load_config(root))[0] == 'strict':
        return frozenset(), True
    return frozenset(data.get('sessions', {}).get(session_id, {}).get('gate_asked', ())), True
```

`protect_state._gate_edits(payload, root)` becomes the `root is None or 'agent_id' in
payload` test plus `return sessions.gate_topics(root, payload.get('session_id'))`.

### 4. `cli/wuwei/decision.py`: `owner_confirm` and `owner_record`; `RECORD`

```python
RECORD = 'wuwei decide {id} <label>'   # line 146

def owner_confirm(root, identifier, digest, prompt):
    """Where the owner answered: the planner session's asked gate question, else y/N at
    the host terminal (#354); '' when declined. OSError without a terminal propagates."""
    from wuwei import sessions
    if identifier in sessions.gate_topics(root, sessions.current())[0]:
        return 'in the planner session'
    from wuwei.integrity import _host_confirm
    return 'at the host terminal' if _host_confirm(digest, prompt=prompt) else ''

def owner_record(text, option, where, note=None):
    """The record after the owner's answer: Outcome, Decided-by: owner and one Notes line."""
    text = set_outcome(text, option)
    text = re.sub(r'^((?:#{1,6} )?Decided-by:).*$', r'\1 owner', text, count=1, flags=re.M)
    stamp = workspace.now().isoformat(timespec='seconds')
    return text.rstrip('\n') + f'\nNotes: Decided at {stamp} {where}.' + (f' {note}' if note else '') + '\n'
```

`set_outcome` is unchanged (its test pins it).

### 5. `cli/wuwei/mcp.py` `decide` (lines 622-676)

- Signature gains `note=None`. When `identifier` is None and `option` is given (not the
  `servers` form), use `Path(waiting).stem` after the `waiting` check (line 637-639).
- Confirmation: `where = ('at the host terminal' if confirm(digest) else '') if confirm
  else decision.owner_confirm(root, identifier, digest, prompt)`, with the prompt from
  section 2. Keep the `confirm` parameter: tests pass `confirm=lambda digest: True`.
- Write: replace lines 658-660 with
  `workspace.atomic_write(path, decision.owner_record(text, option, where, note))`.
  The host-terminal Notes text stays byte-identical to today's (`test_mcp.py:1514`).
- `_proceed_unmeasured` keeps its own host-only `_host_confirm` call (no `D-n`, never
  session-allowed).
- Today the no-terminal `OSError` from the confirmation falls into the outer handler and
  `_failure` reports `MCP registry unmeasured: OSError; check configuration and scanner
  reports`, which hides the real reason. Wrap the confirmation in `decide` and
  `_proceed_unmeasured` as `drafts.py:145-150` does:
  `except OSError as exc: return registry.Result(2, reason=str(exc))`, so the owner reads
  `this is an owner action: run it in a host terminal`.

### 6. `cli/wuwei/commands/decision.py` `owner_outcome` (lines 90-140)

- Replace the `_host_confirm` call (line 114) with
  `where = owner_confirm(root, args.id, digest, f'{args.id}: {fields["Question"]}\nRecord {args.option}.')`;
  declined (`''`) keeps the `decision: owner confirmation declined` exit 1.
- Replace `set_outcome(text, args.option)` (line 139) with
  `owner_record(text, args.option, where, getattr(args, 'note', None))`.
- Workspace: unchanged `find_workspace()`.

### 7. `cli/wuwei/commands/decide.py` (new, about 30 lines)

```python
"""Record the owner's answer to today's decision D-n (#354): one command for every decision."""

def register(subparsers):
    parser = subparsers.add_parser('decide', help="Record the owner's answer to a decision")
    parser.add_argument('id')
    parser.add_argument('option')
    parser.add_argument('--note')
    parser.set_defaults(func=run)

def run(args):
    if args.note is not None and ('\n' in args.note or '\r' in args.note):
        print('wuwei decide: --note must be one line', file=sys.stderr)
        return 2
    root = workspace.find_workspace()
    waiting = mcp.pending(root)
    if waiting and Path(waiting).stem == args.id:
        result = mcp.decide(root, args.id, args.option, note=args.note)
        if result.reason: print(result.reason, file=sys.stderr)
        return result.exit
    code, message = decision_command.owner_outcome(args)
    print(message, file=sys.stderr if code else sys.stdout)
    return code
```

`find_workspace` raising `FileNotFoundError` reaches `__main__`'s handler: exit 2 with the
reason from section 9.

### 8. `cli/wuwei/commands/mcp.py` `run` (lines 20-42)

- Accept `decide <option>` (one word that is neither `proceed-unmeasured` nor a `D-n`) as
  `mcp.decide(root, None, option)`. A lone `D-n` stays a usage error. Update the usage line
  to `wuwei mcp decide [D-<n>] <option>`.
- Workspace (lines 28-31):
  ```python
  root = workspace.guard_scope({'cwd': str(Path.cwd())})
  if root is None:
      if args.action == 'check' and 'WUWEI_WORKSPACE' not in os.environ:
          return 0   # spec 035: outside a workspace the check is a no-op
      # The owner's explicit selection (#354); without one this raises the
      # no-workspace reason, which __main__ prints with exit 2.
      root = workspace.find_workspace()
  ```
  `guard_scope` stays first so a configured repository or an external worktree still finds
  its workspace as today.

### 9. `cli/wuwei/workspace.py:232` and `cli/wuwei/__main__.py`

- Reason: `f'No .wuwei/ found from {start}; run from the workspace, set WUWEI_WORKSPACE=<path> or pass --workspace <path> (wuwei init creates one)'`.
  Keep the `No .wuwei/ found` prefix (`test_why.py:290`).
- `__main__._main`, first statement after `argv` is set:
  ```python
  if argv[:1] == ['--workspace'] and len(argv) > 1:
      # ponytail: leading form only; it selects the workspace for this process (#354).
      os.environ['WUWEI_WORKSPACE'], argv = argv[1], argv[2:]
  ```

### 10. `cli/wuwei/guards/protect_state.py`

- `_OWNER_ACTIONS`: add `('decide', ''): 'Decisions require the owner terminal, outside
  agent tools.'` (whole group: `decide`'s verb position holds the `D-n`).
- `_pair(words)`: skip the word after `--workspace`:
  `[w for prev, w in zip(['', *words], words) if not w.startswith('-') and prev != '--workspace']`.
- `_GATE_EDITS` gains `('mcp', 'decide')` and `('decide', '')`. In `_owner_action`
  (lines 182-188) look the matched key up as `(group, verb)` or `(group, '')`; allowed when:
  - goals and voice: unchanged (`group in topics` and a `--file` word);
  - decisions: `ids = [w for w in action if re.fullmatch(DECISION_ID, w)]`, allowed when
    `ids and set(ids) <= topics`. Every `D-n` word must have been asked, so a `--note D-1`
    or an abbreviated option cannot smuggle an asked id past an unasked record.
  Otherwise the existing `f'{reason} Run it in a host terminal: {shlex.join(argv)}'`.
- `_STATE_HINT` text unchanged.

### 11. `cli/wuwei/guards/decision.py` `record_gate` (lines 119-150)

Add `D-n` topics: for each question, when `header` fullmatches `DECISION_ID`, the question
text cites it (the same `(?<![\w-])D-n(?![\w-])` test `check_question` uses) and
`today_path(header, root).is_file()`, add `header` to `topics`. Goals and voice stay as
they are. The planner and `agent_id` tests above it are unchanged.

### 12. `cli/wuwei/commands/setup.py` `_setup` (lines 200-206)

In the `except FileNotFoundError` branch, after `root = workspace.find_workspace()`:
`print('To run owner commands from any directory, add to your shell profile:\n'
f'export WUWEI_WORKSPACE={shlex.quote(str(root))}')`.

### 13. `cli/wuwei/commands/status.py:179`

`f'confirm with wuwei decide {identifier} {option}'`.

### 14. Text

Replace digest typing and `decision outcome` owner instructions with y/N and `wuwei
decide`:

- `docs/site/configuration.md` 412-435: proceed-unmeasured "answers y"; the D-n paragraph:
  "the owner runs `bin/wuwei decide D-<n> proceed` (or `defer`), or `bin/wuwei mcp decide
  D-<n> proceed`, from a host terminal and answers y. Under observe and guarded the planner
  asks it in the session and records the answer with the same command." Notes line text
  names both `<where>` forms. Add `--workspace` and `WUWEI_WORKSPACE` in one sentence.
- `docs/integrity.md:45`, `docs/site/index.md:68`, `docs/site/recovery.md:107`,
  `docs/site/rehearsal.md:66-67`, `README.md:152`: "answer y" instead of "type the
  (displayed) digest".
- `docs/site/concepts.md:42`: add `wuwei decide`; "The ones that ask y/N exit 2 without a
  terminal."; `concepts.md:103` `wuwei decide D-<n> OPTION`.
- `docs/site/reference.md`: host terminal actions list and the table near line 374 gain
  `bin/wuwei decide D-<n> <option> [--note <text>]`; the `--widget` paragraph near line 98
  says `record` is `wuwei decide D-n <label>`; one sentence on `--workspace`.
- `docs/site/daily.md` 147-169: `bin/wuwei decide`; "How you answer" names the session
  question under observe and guarded, the host terminal for strict and credentials
  (#359 T021).
- `docs/site/remote.md` 349-355: `bin/wuwei decide D-3 B`, the status reason, "ask y/N".
- `docs/site/agent.md:90`: add `decide`.
- `skills/wuwei-plan/SKILL.md` step 1: after the widget sentence, "Under strict the hook
  refuses the record command and prints it; show that line to the owner for a host
  terminal."

### 15. Tests that pin old behaviour (update with the change, not before)

- `tests/test_integrity.py:551` (pty test types the fingerprint): becomes the y/N test.
- `tests/test_owner_records_lint.py`: delete `PENDING_354` (the three sentences are already
  gone from main) and add `\btyp(?:e|es|ing) the (?:displayed )?digest\b|To confirm, type`
  to `PATTERN`.
- `tests/test_docs.py:214`: add `'decide'` to the host terminal command list.
- `tests/test_decision.py` and `tests/test_mcp.py` assertions on `record` strings and
  usage text.
- Tests calling `main([...])` in process with `--workspace` must `monkeypatch.delenv(
  'WUWEI_WORKSPACE', raising=False)` first so the variable `__main__` sets is restored.

## What must not change

- Digest computation, comparison and recording in every caller (`accepted-*.json`
  `digest`, `confirmation.json` `fingerprint`, draft and state re-read checks).
- `HOST_TERMINAL` text and the no-terminal `OSError`.
- Hook refusals for seats (`agent_id`), for every other owner action, and for every action
  under strict; `goals edit` and `voice edit` allowance behaviour (#357 tests).
- `decision outcome` CLI behaviour and owner-only status; `decision route`; event kinds
  and producers; `mcp.check` and `mcp.cached` semantics; `mcp.command` and `_waiting` text.
- `guard_scope` and `scope` (hook scope stays: an environment selection is context, not
  membership).
- `set_outcome` output (`test_decision.py:1082`).

## Project Structure

```text
cli/wuwei/integrity.py              _host_confirm y/N
cli/wuwei/sessions.py               gate_topics (moved from protect_state)
cli/wuwei/decision.py               RECORD, owner_confirm, owner_record
cli/wuwei/mcp.py                    decide: optional id, note, owner_confirm, owner_record; prompts
cli/wuwei/drafts.py, remote.py      prompts
cli/wuwei/workspace.py              no-workspace reason
cli/wuwei/__main__.py               leading --workspace
cli/wuwei/commands/decide.py        new command
cli/wuwei/commands/decision.py      owner_outcome via owner_confirm and owner_record
cli/wuwei/commands/mcp.py           one-word decide, workspace selection, usage
cli/wuwei/commands/config.py, state.py, doctor.py   prompts
cli/wuwei/commands/setup.py         export line once
cli/wuwei/commands/status.py        decide reason
cli/wuwei/guards/protect_state.py   decide row, _pair, D-n allowance
cli/wuwei/guards/decision.py        record_gate D-n topics
docs/..., README.md, skills/wuwei-plan/SKILL.md   text
tests/...                           see tasks.md
```

## Test approach

In-process tests (fixtures `configured`, `planner`, `gated` exist in `tests/test_mcp.py`,
`tests/test_decision.py`, `tests/test_owner_edits.py`). The real helper is tested once over
`pty.openpty()` as today (`tests/test_integrity.py:551`), reading the master side to check
the prompt. The session end-to-end test drives `record_gate`, then `check_bash`, then
`main(['mcp', 'decide', 'D-1', 'proceed'])` with `WUWEI_SESSION_ID=planner-1` and
`_host_confirm` patched to raise the no-terminal `OSError`, so a passing test proves no
terminal was needed.
