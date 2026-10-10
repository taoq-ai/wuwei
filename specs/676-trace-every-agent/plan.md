# Implementation Plan: every subagent launched in a workspace is traced as a seat

**Branch**: `676-trace-every-agent` | **Date**: 2026-10-10 | **Spec**: `spec.md`

## Summary

The three guards that already see every subagent (Agent launch, PostToolUse traces,
SubagentStop) learn one more case: an untyped agent. The launch guard registers it as an
adhoc seat keyed by its prompt digest (or refuses it where `seats` blocks), the traces guard
binds its trace session to that seat by the same digest, and the stop guard stops it or
records `subagent.untraced`. Two small helpers in `brief.py` carry the digest match for all
three. `seat start --adhoc` records a digest the strict launch accepts; `why adhoc` and a
doctor row read what was recorded. Consumers that assume every seat has a brief skip adhoc
seats.

## Technical Context

Python 3.11+, stdlib only (`hashlib`); pytest for tests. The launch and stop guards run once
per agent; the traces guard runs on every tool call, so its extra work is limited to
subagent calls with no brief reference: one read of the transcript's first user row (the
brief path already reads that file) and one state read, with a state write only when an
adhoc seat matches.

## Constitution Check

- I (stdlib): `hashlib` only.
- II (exits): launch refusal is exit 1 (`brief.Refused`), a malformed untyped payload in a
  day is exit 2 (`DAMAGED`, as the brief path). The stop path never refuses (a blocked
  SubagentStop would trap the agent), matching the existing `seat stop unmatched` path.
- III (one behaviour, one function): the digest and the seat match live once in `brief.py`;
  the three guards call them.
- IV (test first): every behaviour has its test task before its implementation task.
- V (ponytail): no new state key, no new hook event, no new module. One reserved event kind
  for `seat start`, one for the stop. The two Deferred gaps are not built here.
- VII (security): the stored prompt line is redacted (`wuwei.redact.redact`) and capped; the
  trusted record (`seat adhoc`) is a reserved event kind written only by `wuwei seat start`
  and `events.jsonl` is already write-protected by `protect_state`.
- Guard rule change: adds invariant I36 to design 9.2 and `tests/test_invariants.py`
  (constitution, Workflow). Use the next free number on main at build time if I36 is taken.

## Design

### `cli/wuwei/brief.py` (shared helpers, next to `transcript_reference` and `seats`)

```python
def first_prompt(path):
    """#676: the first user message of a transcript: a subagent's launch prompt, or None."""
    # same row reading as transcript_reference (a list content joins its text parts)

def prompt_digest(text):
    """#676: the key an adhoc seat is matched by: sha256 of the stripped prompt."""
    return hashlib.sha256(text.strip().encode()).hexdigest()

def adhoc_seat(data, digest, session):
    """#676: the running adhoc seat of a subagent: the one already bound to its trace
    session, else the oldest with its prompt digest and no session yet; None when none."""
```

Factor the content extraction `transcript_reference` does today (str, or list of parts
joined by text) into one local so both readers share it; do not change
`transcript_reference`'s behaviour.

### `cli/wuwei/guards/agent_launch.py`

- `_check`: where `seat is None` returns `0, ''` (line 75), return `_adhoc(payload)` instead.
  `_seat` is unchanged (and so is `check_mcp`).
- New `_adhoc(payload)`:
  1. `inputs` not a dict: `0, ''` (`_seat` already raised for that inside a workspace).
  2. `root = workspace.guard_scope(payload)`; None, or no `state.json` in
     `workspace.day_dir(root)`: `0, ''` (never creates the day).
  3. `prompt` must be a nonblank str, else `ValueError(f'invalid Agent prompt; {DAMAGED}')`.
  4. `kind = subagent_type.strip()` when a nonblank str, else `'general-purpose'`.
  5. `digest = brief.prompt_digest(prompt)`; `started` = payloads of today's
     `brief.events(root)` rows with kind `seat adhoc` and `sha256 == digest`.
  6. If `workspace.posture(workspace.load_config(root))[1]['seats'] == 'block'` and not
     `started`: raise `brief.Refused(ADHOC)` where
     `ADHOC = ('untyped Agent launch is not a WUWEI seat; register it first with '
     'bin/wuwei seat start --role <role> --adhoc "<prompt>", then launch it with the same prompt')`
     (prefix the type: `f'{kind}: ' + ADHOC`).
  7. One `state._write_state(reserve, root, reserved=False, kind='seat launched',
     payload={'name', 'item', 'role': 'adhoc', 'type'})` where `reserve` picks
     `adhoc-<n>` (n = 1 + the highest existing `adhoc-<k>` today) and writes
     `data['seats'][name] = {'id': name, 'role': 'adhoc', 'item': name, 'type': kind,
     'label': started[-1]['role'] if started else kind, 'launcher': <role>,
     'prompt': redact(first line)[:200], 'prompt_sha256': digest, 'status': 'running',
     'started_at': workspace.now().isoformat()}`. `launcher` is
     `sessions.registered(data, session_id) or 'adhoc'` when `session_id` is a str, else
     `'adhoc'` (`registered` already returns `planner` for the planner session). Set the
     event payload's name inside `reserve` (the closure mutates the dict before the event is
     appended, as `_check` does with `event.update`).
  8. Return `0, ''`.
- `stop`: replace `if not wuwei_role(payload.get('agent_type')): return 0, ''` (line 254)
  with `return _stop_adhoc(payload, root)` for the untyped case.
- New `_stop_adhoc(payload, root)`: no `state.json` today: `0, ''`. Else inside one `try`:
  `digest` from `brief.first_prompt(payload['agent_transcript_path'])`, `name =
  brief.adhoc_seat(state.read_state(root), digest, f"{payload['session_id']}:{payload['agent_id']}")`,
  no name raises `LookupError('no adhoc seat matches its prompt')`, else
  `state.stop_seat(name, root, agent_id=payload.get('agent_id'))`. On any exception append
  `subagent.untraced` `{'agent_type': redact(str(type)), 'agent_id': redact(str(id)),
  'reason': str(exc)}` (a failure to append prints to stderr, as the `seat stop unmatched`
  path does). Always `0, ''`.

### `cli/wuwei/guards/traces.py` (`_record`, lines 61-73)

After `reference = ...`: when `reference is None` and `'agent_id' in payload` (a subagent
call; its `transcript_path` is the subagent transcript `check` derived), compute the digest
from `brief.first_prompt(transcript_path)` (unreadable: skip binding, keep the span), find
`brief.adhoc_seat(state.read_state(root), digest, payload['session_id'])`, and only when it
names a seat run one `state._write_state` whose closure re-finds the seat under the lock and
does what `bind` does for a brief seat: set `transcript`, append the session to
`trace_sessions`. Reuse `bind`'s body (pass the seat name or matcher) rather than copying it.

### `cli/wuwei/commands/seat.py`

- `register`: add `start` with `--role` (required) and `--adhoc PROMPT` (required),
  `set_defaults(func=start)`.
- New `start(args)`: `root = workspace.find_workspace()`; `brief.read_day(root)` (its
  ValueError names the morning plan, exit 2 through `main`); `brief.identifier(args.role)`;
  a blank prompt raises `ValueError('pass the agent prompt to --adhoc')`; append
  `seat adhoc` `{'role', 'sha256': brief.prompt_digest(prompt), 'prompt': redact(first
  line)[:200]}`; print
  `ad-hoc <role> recorded; launch it with the Agent tool (subagent_type general-purpose) and
  this same prompt; it runs as an adhoc seat and wuwei why adhoc lists it`; return `CLEAN`.
- `run`: when `args.verdict` and `seat['role'] == 'adhoc'`: `refuse(FINDINGS, f'{name} is an
  adhoc seat with no report to record; run wuwei seat stop {name} --unmeasured "<reason>"')`.

### `cli/wuwei/commands/why.py`

`run`: `elif target == 'adhoc': steps = adhoc(root)` before the item branch. New
`adhoc(root)` lists today's seats with role `adhoc`, one step each:
`adhoc seat <name>: <type> as <label>, launched by <launcher>, <status>; prompt: <line>;
traces: <sessions or none yet>` with `state.json` as the evidence path. None: raise
`Missing('no adhoc seat today; an Agent launch of a type outside the WUWEI seats registers one')`.
`render` already redacts.

### `cli/wuwei/commands/doctor.py` (`_day`, after the `traces` row, line 620)

```python
untraced = sum(page['source'] == 'subagent.untraced' for page in found)
rows.append(_row('day', 'untraced subagents', 'warn' if untraced else 'ok',
                 f'{untraced} stopped with no seat today' if untraced else 'none today',
                 'launch agents from a session inside the workspace after the morning plan; '
                 'under strict register them with wuwei seat start --role <role> --adhoc "<prompt>"'))
```

### Event kinds

- `cli/wuwei/commands/event.py` `EVENT_PRODUCERS`: `'seat adhoc': 'wuwei seat start'`,
  `'subagent.untraced': 'wuwei hook SubagentStop'`.
- `cli/wuwei/signal.py` `SILENT`: add `seat adhoc`. `subagent.untraced` stays a nudge (the
  default), which is what doctor counts through `status.scan`.

### Consumers that assume a brief

- `cli/wuwei/watch.py:183`: the `running` list for the brief/worktree check excludes
  `role == 'adhoc'`.
- `cli/wuwei/memory.py:104`: the current briefs line lists only seats with a `brief`.
- `cli/wuwei/scanner.py:71` (`_trace_response`): the `seat` test skips `role == 'adhoc'`, so
  #352 holds (tool-sequence decisions for item seats only; a planner subagent's chain stays
  one silent `traces.noted`). Line 86 needs no change.
- `seat stop --verdict` (above).

### Docs

- `docs/specs/2026-09-24-wuwei-design.md` 4.1 hook table, `Agent` launch row (line 172):
  add "under strict, an untyped launch (`general-purpose`, `Explore` or any type outside the
  WUWEI seats) that `bin/wuwei seat start --adhoc` did not record (#676); below strict an
  untyped launch is registered as an adhoc seat, never refused".
- Design 9.2: row I36 `| I36 | An untyped Agent launch in a workspace is never refused below
  strict and is registered as an adhoc seat; under strict it is refused naming seat start
  --adhoc unless that command recorded its prompt | per posture, agent_launch.check on a
  general-purpose launch with and without a seat adhoc record | #676 |`.
- `docs/site/reference.md`: in Stuck seats (line 312 to 314) a paragraph on adhoc seats
  (registration, `seat start --role <role> --adhoc "<prompt>"`, strict refusal,
  `why adhoc`, `seat stop --unmeasured` only); the doctor day rows list (line 235) adds
  `untraced subagents`; the `why` paragraph (line 398) adds the `adhoc` target; the command
  table row for `bin/wuwei seat` (line 69) mentions registering an ad-hoc seat.

## What must not change

- The brief path for WUWEI roles (`_seat`, everything after it in `_check`, `stopping_seat`,
  `check_mcp`), and its tests.
- Trace span content and the `traces.gap` path; a span is written whether or not a binding
  happens.
- No state write and no day creation for an untyped call when no adhoc seat matches.
- Untyped SubagentStop never exits nonzero.
- `hooks/hooks.json`, `guards.EVENTS`, `guards.MODULES` (no new event or module).
- `sessions.ROLES` and the session registry's `adhoc` session role (a different record).

## Existing tests whose contract changes

- `tests/test_agent_launch.py::test_unrelated_agents_pass_before_parsing` and
  `::test_default_general_purpose_agent_passes_before_validation`: they launch an untyped
  agent in a day with a broken config and no prompt and expect `0`. Under #676 an untyped
  launch in a day is relevant. Keep their intent where it still holds: without today's
  `state.json` the untyped launch passes without reading the prompt and writes nothing
  (remove `state.json` in the test); with a day, the registration tests below cover it.
  Correction at build time: deciding the day needs the launch's workspace scope
  (`workspace.guard_scope`), which loads `config.toml`, so a broken config now fails closed
  (exit 2) for an untyped launch inside a workspace, as it does for every other scoped guard;
  the first test asserts that.
- `tests/test_doctor.py::test_day_rows`: the pinned `day` row names gain
  `untraced subagents` after `traces`.
- `tests/test_signal_status.py::test_emitted_kinds_have_intended_tiers`: add
  `'seat adhoc': 'silent'` and `'subagent.untraced': 'nudge'`.
- `tests/test_invariants.py`: `INVARIANTS`, `READS` (`'I36': (0,)`) and the table test pick up
  I36.
