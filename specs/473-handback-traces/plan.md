# Implementation Plan: A background hand-back is read from the transcript, no seat is left running, traces redact only secrets, failed spans record a gap

**Branch**: `473-handback-traces` | **Date**: 2026-10-04 | **Spec**: [spec.md](spec.md)

## Summary

One helper, `brief.last_turn(path)`, reads the last assistant entry of an agent transcript,
SubagentHandback included. The SubagentStop hook fills a missing `last_assistant_message`
from it once, so every SubagentStop guard reads the background seat's report without being
edited; `build.stopped` uses the same helper for its completion binding. When the report
cannot be read, `agent_launch.stop` stops the seat as `unmeasured` instead of leaving it
running. The traces recorder remembers each subagent seat's transcript, so `brief.stuck`
can name seats that handed back with no stop; the heartbeat, `wuwei next` and `doctor` show
them with the new `wuwei seat stop` recovery command. Redaction keeps the text before the
first credential; a failed span becomes one `traces.gap` event counted by `status --line`
and `doctor`.

## Technical Context

Python 3.11+ stdlib runtime, pytest for tests. Reuse, do not re-implement:

- `brief.transcript_reference` (same module, same transcript reading style) and
  `brief.seats` (seat validation).
- `guards.agent_launch.stopping_seat` and `wuwei_role` (seat binding and role check).
- `state.stop_seat` (extended, the only seat-stop writer besides `build.record_result` and
  `dispatch`), `state._write_state`, `state.append_event`.
- `build._park` for a builder stopped unmeasured by the owner.
- `guards.discover` with `guards.SELECTION`, as `commands/hook.py` runs them, for
  `seat stop --verdict`.
- `verdict.lint_file` for a sentinel's verdict file.
- `integrity._host_confirm` (y/N at the host terminal, `HOST_TERMINAL` without one),
  `sessions.current()`, `workspace.posture`.
- `status.scan` rows (no new event read) for the gap count in `status --line` and `doctor`.
- Tests: the `seat` fixture of `tests/test_build_next.py`, the scripted `Day` of
  `tests/fakes/day.py`, the `trace_workspace`, `call_payload`, `run_hook` and `recorder`
  helpers of `tests/test_traces.py`.

Files outside this issue (built in parallel, do not edit): `cli/wuwei/guards/outward.py`,
`cli/wuwei/shell.py`, `cli/wuwei/guards/protect_state.py`, `cli/wuwei/commands/rank.py`,
`cli/wuwei/guards/decision.py`, `cli/wuwei/decision.py`, the vcs adapter,
`cli/wuwei/commands/git_hook.py`. Also leave `cli/wuwei/guards/lifecycle.py` alone (#476).

## Constitution Check

Stdlib only; no new dependency, port or config key. Exits: the hook still exits 2 when a
seat's report cannot be recorded (now after releasing the seat); `seat stop` exits 0, 1
(declined, wrong session, lint findings, wrong status) or 2 (no host terminal under strict,
unreadable file, bad reason). Never clean when unmeasured: an unreadable report is the
`unmeasured` seat status, never `stopped`. Scope: the fill and every guard stay inside a
workspace (`root is not None`, `wuwei_role`). Trust: `transcript`, `reason` and `by` live in
day state, which only the writer changes (seats cannot write `state.json`); `traces.gap` is
reserved to the hook. Test first. Passes.

## Design

### 1. The shared transcript helper (`cli/wuwei/brief.py`)

Add next to `transcript_reference`:

```python
HANDBACK = 'SubagentHandback'  # the harness's structured hand-back tool (#473)


def last_turn(path):
    """(completion, text, handback) of a transcript's last assistant entry. completion is
    [line index, sha256 of the line], the builder binding; text joins the text blocks, or is
    a SubagentHandback's input.message (a background seat's report, #473); handback says
    which. Read from the end, so a torn last line raises ValueError."""
```

- `lines = Path(path).read_text(encoding='utf-8').splitlines()`; walk indices from the end;
  `json.loads` each line (blank lines skipped), skip rows whose `type` is not `assistant`.
- `content = row['message']['content']`: a string is the text; a list gives `text` (text
  blocks joined by `'\n'`) and `handback` (the `input['message']` of the first `tool_use`
  block named `HANDBACK`, when it is a string). Return `handback` when present, else `text`.
- `completion = [index, hashlib.sha256(lines[index].encode()).hexdigest()]`, identical to
  today's `build.stopped` binding.
- `KeyError`/`TypeError` from a malformed row become `ValueError(f'malformed transcript
  entry; {PAYLOAD}')`; no assistant entry raises `ValueError(f'transcript has no assistant
  turn; {PAYLOAD}')`. Add `PAYLOAD` to the `wuwei.exits` import.

```python
def stop_text(payload):
    """A seat's final report: a non-blank last_assistant_message, else the last assistant
    turn of agent_transcript_path (#473). OSError or ValueError when neither reads."""
```

Raises `ValueError(f'missing or invalid agent_transcript_path; {PAYLOAD}')` when the path is
not a non-empty string.

```python
def stuck(data):
    """Seats that need bin/wuwei seat stop (#473), sorted: running with a recorded transcript
    whose last assistant entry is the hand-back (no process, no stop), or unmeasured by the
    hook (by is not owner)."""
```

A transcript that does not read is skipped (`OSError`, `ValueError`) with
`# ponytail: an unreadable transcript is no evidence of an end; the reservation timeout still
reports the seat`. Also: `seats()` accepts `'unmeasured'` as a seat status (line 128).

### 2. The hook fills the message once (`cli/wuwei/commands/hook.py`)

New function, called in `run` inside the discovery `try` right after `root` is known and
before `discover()`: `if args.event == 'SubagentStop' and root is not None:
fill_stop_text(payload)`.

```python
def fill_stop_text(payload):
    """#473: a background seat ends with a SubagentHandback and no last_assistant_message;
    every SubagentStop guard reads the report its transcript holds. Unreadable: left as is,
    and agent_launch.stop stops the seat as unmeasured with the reason."""
```

Return at once when the message is a non-blank string or
`guards.agent_launch.wuwei_role(payload.get('agent_type'))` is false (a non-WUWEI subagent
reads nothing). Otherwise import `wuwei.brief.stop_text` here (SubagentStop only, #346),
`payload['last_assistant_message'] = stop_text(payload)`, and on `(OSError, ValueError)` pass.
This is why `guards/verdict.py`, `guards/spec.py` and `guards/decision.py` need no edit.

### 3. No seat left running (`cli/wuwei/guards/agent_launch.py`, `cli/wuwei/state.py`)

`state.stop_seat(name, root=None, *, directory=None, agent_id=None, reason=None, by=None)`:
status `'unmeasured'` when `reason` is given, else `'stopped'`; pop stale `reason` and `by`,
then set them when given; event payload `{'name': name}` plus `status: 'unmeasured'` and
`reason` when unmeasured, plus `by` when given. Kind stays `seat stopped`.

`agent_launch.stop`, lines 255 to 263:

- Before the build branch, for a seat still `running`, call `brief.stop_text(payload)` (an
  unreadable report is unmeasured for every role; an empty but readable one is not). On
  `OSError` or `ValueError` call `state.stop_seat(name, root, directory=directory,
  agent_id=payload.get('agent_id'), reason=str(exc))` and return `(2, f'seat {name} stopped
  unmeasured: {exc}; record its report with bin/wuwei seat stop {name} --verdict <file>, or
  run bin/wuwei seat stop {name} --unmeasured "<reason>"')`. If that write also fails, return
  `(2, f'seat {name} could not be stopped: {exc}; {error}; run bin/wuwei doctor')`.
- Corrected during implementation: the existing `except` around `build.stopped` keeps its
  behaviour. Its other failures are refusals of the stop itself (an agent id that differs from
  the resumed builder, a build that changed because the builder was resumed, a message that
  differs from the transcript), and stopping the seat there would let a replayed or stale stop
  release a live seat (`test_replayed_stop_cannot_release_resumed_builder`,
  `test_delayed_stop_cannot_consume_a_resumed_iteration`). Only an unreadable report is
  unmeasured.
- `wuwei_role` moves to `cli/wuwei/guards/__init__.py` (re-exported by `agent_launch`), so
  `commands/hook.py` can call it without importing a guard module; hook tests replace the
  guards package path.

The hook does not park the build (spec A6).

### 4. The builder binding (`cli/wuwei/commands/build.py`, `stopped`)

Replace lines 283 to 295 with:

```python
from wuwei.brief import last_turn
completion, message, _ = last_turn(payload['agent_transcript_path'])
text = payload.get('last_assistant_message')
if not isinstance(text, str) or not text.strip():
    text = message  # #473: a background hand-back carries no message
elif message.strip() != text.strip():
    raise ValueError(f'SubagentStop has no matching assistant completion; {PAYLOAD}')
```

Everything after (`completion == record.get('completion')`, usage, `record_result`, checks)
is unchanged. `record_result` line 254 also pops a stale `reason` when it marks the seat
`stopped` (a hook-unmeasured builder recovered with `--verdict`).

### 5. The traces recorder remembers the seat transcript (`cli/wuwei/guards/traces.py`)

In `_record`'s `bind` (lines 67 to 72), for the matched seat also set
`seat['transcript'] = str(transcript_path)`. `transcript_path` is the subagent transcript
`check` computes (lines 101 to 108); nothing else changes in binding.

### 6. Failed spans (`cli/wuwei/guards/traces.py`, `check`)

At the top of `check` keep `span` (`payload['tool_name']` if a non-empty string, else
`'unknown'`) and `session` (`payload['session_id']` likewise) from the incoming payload.
Line 127 becomes `state.append_event('traces.gap', {'reason': reason, 'span': span,
'session': session}, root)`; the stderr line for a failed log says `could not log
traces.gap; run bin/wuwei doctor`. Return values are unchanged (spec A9). The security
evidence path (line 119) is unchanged.

`cli/wuwei/commands/event.py` `EVENT_PRODUCERS`: add `'traces.gap': 'wuwei hook
PostToolUse'`; `'seat stopped'` becomes `'wuwei hook SubagentStop, wuwei dispatch opinion or
owner wuwei seat stop'`. `signal.classify` already returns `nudge` for an unknown kind; no
change there.

### 7. Redaction (`cli/wuwei/redact.py`)

- `SECRET` line 55 becomes
  `r'--data[\w-]{0,40}(?:\s{1,40}|=)\S|(?:--json|(?<![\w-])-d)(?:\s{1,40}|=)[\'"{@]|'`:
  `--json` and `-d` count only with a quoted, brace or `@` value (gh field lists and
  `git branch -d` pass; curl bodies still match, and a field name inside a JSON body matches
  the first alternative anyway).
- Lines 53 and 54: the final `\S` of the first two alternatives becomes `(?!\[BODY )\S`, so
  a body marker is not itself a credential.
- Lines 101 and 102: keep the command words, replace only the body:
  `lambda m: m[0][:m.start(1) - m.start()] + body_marker(...)`.
- Lines 103 to 107: collect the start of the first `SECRET` match and of every qualifying
  `PHONE` match in `decoded`; with any, return `value[:min(starts)] + REDACTED` when
  `decoded == value`, else `REDACTED`. Comment:
  `# ponytail: everything from the first credential on is dropped (tool, subcommand and
  earlier paths stay); per-value redaction if traces need the tail.`

Corrected during implementation: the prefix is kept only with `redact(value, prefix=True)`,
which the trace recorder passes for `tool_input`. Every other caller (gate verdict findings,
refusal targets, inbound text) still replaces a string with a credential whole: with the
prefix kept, a scanner finding message could carry an injected `Verdict:` line into a gate
verdict file (`tests/test_dispatch.py::test_scanner_finding_text_cannot_inject_or_leak`).

Prototype checked against the corpus below and the existing private-text cases of
`tests/test_traces.py`: twenty ordinary commands unchanged, ten secrets gone, no
`private details` left.

### 8. Stuck seats on the owner surfaces

- `cli/wuwei/heartbeat.py`: append `('seats', 'no seat handed back or stopped unmeasured
  without a recorded result')` to `PROBES`; add `_seats(root)` returning `('ok', 'none
  stuck')` or `('failed', f'dead: {names}; run wuwei seat stop {first} --verdict <file>, or
  --unmeasured "<reason>"')` from `brief.stuck(state.read_state(root))`; add it to `during()`.
- `cli/wuwei/commands/next.py` `step`: right after the decision-routes loop, before the item
  loop: `stuck = brief.stuck(data)`; when non-empty return `_row('stuck', f'Seat {stuck[0]}
  ended with no recorded result; run the command with its report as the file, or stop it
  with --unmeasured "<reason>".', f'wuwei seat stop {stuck[0]} --verdict <file>')`.
- `cli/wuwei/commands/doctor.py` `_day`: after the heartbeat row, `_row('day', 'stuck
  seats', PROBE[probes['seats']['result']], probes['seats']['value'], 'wuwei seat stop
  <name> --verdict <file>, or wuwei seat stop <name> --unmeasured "<reason>"')`; after the
  nudges row, `gaps = sum(page['source'] == 'traces.gap' for page in found)` and
  `_row('day', 'traces', 'warn' if gaps else 'ok', f'{gaps} gaps today' if gaps else 'no
  gaps today', 'read the traces.gap reasons in wuwei nudges, then run wuwei doctor')`.
- `cli/wuwei/commands/status.py`: `snapshot` sets `result['trace_gaps'] = sum(row['source']
  == 'traces.gap' for row in active)`; `line` appends `f'traces: {n} gaps'` after the
  `health` part when non-zero.

### 9. The recovery command (`cli/wuwei/commands/seat.py`, new)

`wuwei seat stop <name> (--verdict FILE | --unmeasured REASON)`, one mutually exclusive
required group. `run(args)`:

1. `root = workspace.find_workspace()`, `data = state.read_state(root)`,
   `seat = brief.seats(data).get(name)`. Accept `running`, or `unmeasured` without
   `by: owner`; otherwise exit 1 `wuwei seat: <name> is <status>; nothing to stop; run wuwei
   next for the next step` (unknown: `not a seat today`).
2. `--unmeasured`: empty or multi-line reason exits 2 (`pass a one-line reason`).
3. Posture rule (`allowed`): `workspace.posture(workspace.load_config(root))[0] ==
   'strict'` asks `integrity._host_confirm(name, prompt=f'Stop seat {name}.')`; declined
   exits 1 (`seat stop declined; rerun it in a host terminal and answer y`); `OSError` exits
   2 with its text (`HOST_TERMINAL`). Otherwise `sessions.current()` must be `None` or
   `data['planner_session_id']`, else exit 1 (`seat stop runs from the planner session or a
   host terminal; run it there`).
4. `--unmeasured`: `state.stop_seat(name, root, reason=reason, by='owner')`; for a builder
   whose `builds[item]` has `seat == name` and `status == 'running'`, `build._park(root,
   item, dict(record), f'seat {name} stopped unmeasured: {reason}', record)`. Exit 0.
5. `--verdict FILE`: read the text; for a `sentinel-*` role run `verdict.lint_file(path,
   role=role, root=root)` and return its code and message when non-zero (seat untouched).
   Write a two-line transcript in a `tempfile.TemporaryDirectory()`: a user row whose content
   is `brief.REFERENCE_PREFIX + seat['brief']`, and an assistant row with one text block of
   the file text. Payload: `hook_event_name 'SubagentStop'`, `cwd str(root)`,
   `stop_hook_active False`, `agent_type 'wuwei:' + role`, `agent_id` (the build record's
   `agent_id`, else the agent part of the last `trace_sessions` entry, else the seat name),
   `agent_transcript_path`, `last_assistant_message` the text. No `session_id` (the
   registry guard then records nothing). Run every `discover()` guard whose event is
   `SubagentStop` under `SELECTION` `('SubagentStop', '')`; print messages (findings to
   stderr), exit with the highest code.

Register: `'seat stop'` in `WRITES` (`cli/wuwei/commands/__init__.py`, #348) and `seat` in
the `Recovery` group of `cli/wuwei/__main__.py` `GROUPS`. `tempfile`, `json` and the guard
imports stay inside the functions.

### 10. Docs (`docs/site/reference.md`)

- Command table: `bin/wuwei seat` row ("Recovers a stuck seat: records its report from a
  file, or stops it as unmeasured.").
- A short "Stuck seats" paragraph: the hand-back read, the `unmeasured` status, both
  forms, the posture rule (host terminal y/N under strict; planner session or host terminal
  under observe and guarded), and that `wuwei next`, `doctor` and the heartbeat name it.
- Heartbeat table: the `seats` row. Doctor Day list: `stuck seats` and `traces`.
- Status line: `traces: N gaps`. Traces: a span that cannot be written records `traces.gap`
  with reason, span and session; redaction keeps text before the first credential.

### Fixtures

- `tests/payloads/SubagentStop/handback.json`: `example.json` without
  `last_assistant_message`.
- `tests/payloads/SubagentStop/handback-transcript.jsonl`: the two recorded entries (the
  assistant SubagentHandback tool use, the user tool result with `toolEndsTurn`), neutral ids
  and text ending in the three retro lines. Tests prepend the brief reference row.
- `tests/payloads/README.md`: one line each, "shape recorded from a background subagent
  transcript, neutralised".
- `tests/fakes/day.py` `Runtime`: a `handback` flag (default False); when set, `dispatch`
  writes the assistant row as the recorded hand-back with `message` in `input.message`, then
  the tool result row, and calls the SubagentStop hook without `last_assistant_message`.

## What must not change

- A stop whose payload carries the message: the same events, completion binding and
  refusal of a message that differs from the transcript.
- `stopping_seat`, the brief-reference binding, and `seat stop unmatched` for an unbound
  stop.
- Hook imports: a non-WUWEI SubagentStop and every other event import nothing new;
  `tempfile` stays off the hook path; the #346 pins in `tests/test_hooks.py` stay green.
- What `redact` treats as a credential (other than `--json` and `-d` without a body value),
  body privacy, `[TRUNCATED ...]`, dict-key and private-file redaction.
- `dispatch receive` accepts only a `stopped` sentinel; an `unmeasured` one is not
  received.
- The traces exits and the security evidence path.
- The files of #469 to #472 and `guards/lifecycle.py`.

## Tests (files)

- `tests/test_handback.py` (new): helper unit tests, hook fill, unmeasured stop, stuck,
  next, heartbeat probe, `seat stop` (reuses the `seat` fixture of `tests/test_build_next.py`
  by import).
- `tests/test_e2e_day.py`: the background hand-back day.
- `tests/test_traces.py`: corpus, body prefix, `traces.gap` payload, transcript binding,
  renamed kind in existing assertions, adjusted exact-equality cases.
- `tests/test_signal_status.py`, `tests/test_steward.py`: renamed kind; `traces: N gaps`.
- `tests/test_doctor.py`: `stuck seats` and `traces` rows.
- `tests/test_heartbeat.py`: the `seats` probe row and its docs row.

Every new reason string names a next step (`tests/test_reasons.py`, #362).
