# Implementation Plan: control-plane interface with Remote Control and push as default

**Branch**: `057-control-plane-default` | **Date**: 2026-09-30 | **Spec**: spec.md
**Input**: spec.md, research.md

## Summary

One new core module, `cli/wuwei/control_plane.py`, holding the three interface functions,
the pending-decision reader, the renderer and the shared reply parser. The default
implementation is "no transport": Claude Code Remote Control and push deliver the planner's
question widget (research.md), so WUWEI renders text and sends nothing. A messaging
transport (Slack, #50/#65) is passed in; tests pass a fake. One config key, one event kind,
one silent-signal entry, and docs.

## Technical Context

Python 3.11+ stdlib only; pytest for tests. No subprocess, no network, no new adapter kind,
no new CLI command, no new state key. Tests in process with `tmp_path` workspaces and
`WUWEI_NOW`, following `tests/test_decision.py` (`ws`, `save`, `events` helpers and the
`VALID` record; copy the few lines needed rather than importing across test modules).

## Constitution Check

- I stdlib only: yes. II three-state exits: every function returns a `registry.Result`
  with 0, 1 or 2 and a reason. III one behaviour, one function, one test: parser, escalate,
  notify and poll each have one function and one test group. IV test first: tasks.md orders
  every test before its code. V ponytail: no interface class, no adapter kind, no listener;
  the transport is duck-typed and optional. VII security: only id and option are recorded;
  reply text is never stored; a reply is not an owner outcome (spec FR-006).

## Design

### Files and functions

1. `cli/wuwei/control_plane.py` (new). Imports `re`, and `decision`, `state`, `workspace`
   from `wuwei`, and `Result` from `wuwei.registry`.

   - `HELP = 'Not recorded. Reply approve D-n, option X on D-n, or drop it.'`
     Avoid words the outward lint refuses (`wuwei`, `agents`, `queue`, `the owner`): #65
     will send these lines through the chat port's `dm`, which is an
     `outward_operation`.
   - `pending(root) -> dict[str, dict]`: `data = state.read_state(root)`;
     `routes = data.get('decision_routes', {})` (not a dict: `ValueError('invalid decision
     ledger')`, as `commands/status.py:122-124`); for each id with
     `decision.answered(data, id) is None`: `path = decision.today_path(id, root)`, refuse a
     symlinked record or directory (as `commands/decision.py:59`), `fields, _ =
     decision.evaluate(path.read_text(encoding='utf-8'))`. Returns `{id: fields}` in route
     order. Errors propagate; callers turn them into exit 2.
   - `options(fields) -> list[[id, description]]`: `decision.table(fields['Options'],
     ['Option', 'Description'], 'Options')`. Reuse; do not re-parse the table.
   - `render(identifier, fields, content) -> str`:
     `summary`: first line `f'{identifier}: {fields["Question"]}'`, then one line per option
     `f'{option}: {description}'`.
     `none`: one line `f'{identifier} options: ' + ', '.join(option ids)`.
   - `parse(text, decisions) -> tuple[str, str] | None` (the shared reply parser, pure):
     normalise `reply = re.sub(r'[.!]$', '', ' '.join(text.split())).casefold()`.
     - `re.fullmatch(r'approve (d-[1-9][0-9]*)', reply)`: id `m[1].upper()`; if pending,
       return `(id, fields['Recommendation'])`.
     - `re.fullmatch(r'option ([a-z][a-z0-9_-]*) on (d-[1-9][0-9]*)', reply)`: if the id is
       pending and exactly one option id casefolds to `m[1]`, return `(id, that option)`.
     - `reply == 'drop it'`: if exactly one decision is pending and exactly one of its
       options has a description matching `re.match(r'(?i)(?:Do nothing|Defer)\b', ...)`
       (the same test as `decision.py:72`), return `(id, that option)`.
     - Anything else: `None`.
   - `escalate(decision_id, *, root=None, transport=None) -> Result`:
     `root = workspace.find_workspace(root)`; `decisions = pending(root)`; id not in it:
     `Result(1, None, f'control plane: {decision_id} is not pending')`, nothing sent.
     No transport: `Result(0, render(id, fields, 'summary'), 'ask as a question widget;
     Remote Control pushes it')`. With a transport:
     `content = workspace.load_config(root)['control_plane']['content']`, return
     `transport.dm(render(id, fields, content) + '\n' + HELP, root=root)` unchanged.
     `(OSError, UnicodeError, ValueError, RuntimeError)` becomes `Result(2, None,
     f'control plane: {exc}')`.
   - `notify(summary, *, root=None, transport=None) -> Result`: no transport:
     `Result(0, summary, 'shown in the session; Claude Code decides whether to push')`.
     With a transport: text is `summary` for `content = summary`, or the fixed line
     `'An update is waiting in the workspace.'` for `none`; return `transport.dm(text,
     root=root)`. Same error mapping.
   - `poll_replies(since, *, root=None, transport=None) -> Result`: no transport:
     `Result(0, [], 'replies arrive in the planner session')`. With a transport:
     `polled = transport.poll(since, root=root)`; `polled.exit != 0`: `Result(2, None,
     polled.reason or 'control plane: poll failed')`. `polled.data` must be a list of dicts
     each with a `str` `text`, validated before anything is recorded, else exit 2.
     `decisions = pending(root)` (errors: exit 2, nothing recorded). For each reply in
     order: `answer = parse(text, decisions)`; an answer appends
     `state.append_event('decision.replied', {'id': id, 'option': option}, root=root)` and
     is collected; otherwise send the echo once per reply, `'\n'.join([HELP, *(render(id,
     fields, content) for each pending)])` or `HELP + '\nNo pending decisions.'`, through
     `transport.dm`; a non-zero echo send returns `Result(2, answers, reason)`. Final:
     `Result(1 if any echo else 0, answers, '')` where `answers` is a list of
     `{'id', 'option'}`.

2. `cli/wuwei/workspace.py`: in `SCHEMA`, next to `"chat"`, add
   `"control_plane": {"content": (str, "summary", ("summary", "none"))},`. The existing
   `_validate` gives the default, the allowed-value finding and the unknown-key finding.

3. `cli/wuwei/commands/event.py`: add `'decision.replied': 'wuwei control plane
   poll_replies'` to `EVENT_PRODUCERS`. The kind is already refused by `wuwei event`
   (only `note` is free); this only names the producer in the refusal.

4. `cli/wuwei/signal.py`: add `'decision.replied'` to `SILENT`. The `decision.pending` nudge
   from state already carries the attention until the host outcome; an unknown kind would
   otherwise raise a second nudge.

5. Docs and template:
   - `templates/workspace/config.toml`: a `[control_plane]` table with
     `content = "summary"` and a one-line comment (`summary` or `none`; applies to messaging
     transports only).
   - `docs/site/configuration.md`: a row for `control_plane.content` (default `"summary"`,
     what each value sends).
   - `docs/site/daily.md` section 5 (Owner decisions): three or four sentences: to answer
     from the phone, run the planner session with Remote Control (`/remote-control` or
     `claude --remote-control`) and turn on "Push when actions required" in `/config`;
     questions stay open until answered; a phone answer is not yet an owner outcome, so
     `bin/wuwei decision outcome` still runs in a host terminal. Keep every phrase
     `tests/test_docs.py:244-254` asserts.

### Shared helpers reused (do not copy)

`decision.evaluate`, `decision.table`, `decision.today_path`, `decision.answered`,
`state.read_state`, `state.append_event` (locked append, redaction via `known_values`),
`workspace.find_workspace`, `workspace.load_config`, `registry.Result`.

### Must not change

- `decision_outcomes`, `decision_routes`, item phases and `wuwei decision outcome`
  (`commands/decision.py`). A reply never writes owner state.
- `guards/decision.py:check_question`: the default widget text must pass it as is.
- `adapters/chat/*`, `registry.PARAMETERS` and `tests/test_adapters.py::CALLS`: no new
  adapter kind or port operation.
- `commands/status.py` pending logic.

## Data

- Event `decision.replied`, payload `{"id": "D-3", "option": "B"}`, appended to today's
  `events.jsonl` through `state.append_event`. No state key, no reply text, no sender.
- Config `control_plane.content`: `"summary"` (default) or `"none"`.

## Complexity Tracking

None. Deliberate shortcut to mark in code: `# ponytail: transport is duck-typed (dm, poll);
promote to an adapter kind when a second messaging transport lands.`
