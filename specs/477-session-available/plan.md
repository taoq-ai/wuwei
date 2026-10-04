# Implementation Plan: the owner's session is never blocked by work

**Branch**: `477-session-available` | **Spec**: `specs/477-session-available/spec.md` |
**Issue**: #477 | **Precondition**: #473 merged (background hand-back read from the transcript)

## Summary

Text first, one small CLI change, no new module, command, config key or state key:

1. Skills, the planner charter, agent.md, the constitution and the design doc say the owner's
   session is never blocked: seats with Agent in the background, long commands through Bash
   in the background, `build next` and `dispatch next` on the completion notification, each
   turn ends with `wuwei status --line`, only owner questions wait.
2. `wuwei build check <item>` records a fast check in flight (`check: {started_at, pid}` on the
   build record); `build next` and a second `build check` exit 2 while that process lives.
3. Two helpers in `cli/wuwei/state.py` list and format what runs (running seats, live checks);
   `wuwei next` and `status --line` use them.
4. A text test over skills, charters, agents and agent.md rejects blocking instructions; the
   headless fixture day asserts a planner turn between builder launch and stop and between
   check launch and result.

## Technical Context

Python 3.11+, stdlib only at runtime; pytest for tests. Run `python -m pytest -q` from the
repository root. The CLI is invoked only as `bin/wuwei` or `python3 -P -m wuwei`.

## Constitution Check

- I Stdlib: `os.kill`, `os.getpid`. Pass.
- II Three-state exits: a check in flight is exit 2 with its start time and the next step
  (the same class as "builder is still running", `build.py:113`). Pass.
- III One behaviour, one function: liveness in `state.check_running`, the running list in
  `state.in_flight`, its text in `state.in_flight_text`; `next`, `status`, `build next` and
  `build check` call them. Pass.
- IV Test first: every pair in tasks.md is test then implementation. Pass.
- V Ponytail: no new record type; the marker rides the existing producer-owned `builds`
  record; pid liveness carries a `ponytail:` comment for its reuse ceiling. Pass.
- VII Security: the marker steers display and `build next` only, never a guard, the push
  evidence or a metric; `builds` stays reserved to `wuwei build`; the new event kind is
  reserved in `EVENT_PRODUCERS`. Pass.

## Design

### 1. Shared helpers: `cli/wuwei/state.py`, next to `running_by_goal`

```python
def check_running(build):
    """The build's fast-check marker while another live process runs it, else None.
    The current process is never "another": a check that raised in this process is over.
    ponytail: pid liveness; a reused pid reads as running until it exits. Upgrade: store the
    process start time with the pid and compare it."""
    marker = build.get('check') if isinstance(build, dict) else None
    if not (isinstance(marker, dict) and type(marker.get('pid')) is int and marker['pid'] > 0
            and marker['pid'] != os.getpid() and isinstance(marker.get('started_at'), str)):
        return None
    try:
        os.kill(marker['pid'], 0)
    except ProcessLookupError:
        return None
    except PermissionError:
        pass
    return marker


def in_flight(data):
    """(started_at, role, item) for running seats and live fast checks, oldest first."""
    rows = [(seat.get('started_at') or '', seat.get('role'), seat.get('item'))
            for seat in data.get('seats', {}).values()
            if isinstance(seat, dict) and seat.get('status') == 'running']
    rows += [(marker['started_at'], 'checks', item) for item, build in data.get('builds', {}).items()
             if (marker := check_running(build))]
    return sorted(rows)


def in_flight_text(rows):
    return ', '.join(f'{role} {item} {at[11:16] if at else "start unrecorded"}'
                     for at, role, item in rows)
```

`os` is already imported in state.py. Excluding `os.getpid()` is what lets in-process tests
(and the Codex loop, which calls `check` in its own process) never see their own finished
or failed check as running; a real planner calls `build next` from a different process.
Tests that need a live marker use a sleeping child process's pid; a dead one uses a child
that has exited.

### 2. Marker: `cli/wuwei/commands/build.py`

- New `_busy(item, record)`: when `state.check_running(record)` returns a marker, raise
  `ValueError(f'fast checks for {item} are running since {marker["started_at"][11:16]} (pid {marker["pid"]}); run bin/wuwei build next {item} when that command exits')`.
  The message names a next step (`tests/test_reasons.py`).
- `next_action` (after the `running` check at line 112): `if record is not None: _busy(item, record)`.
- `check` (line 383): after the status check, `_busy(item, record)`; then
  `marked = {**record, 'check': {'started_at': workspace.now().isoformat(), 'pid': os.getpid()}}`,
  `_save(item, marked, root, 'build.check_started', record)`, and use `marked` as the
  `expected` passed to `complete_checks` (it is the current record; passing the old one
  raises the RACE error). `fast_checks.record` runs after the save, unchanged.
- `complete_checks` (line 329): `record = dict(expected)` then `record.pop('check', None)`, so
  the pass, continue and park saves all drop the marker. The SubagentStop reuse path passes a
  record without a marker; the pop is a no-op.
- Import `os` in build.py if it is not imported.

### 3. Event kind

- `cli/wuwei/signal.py` `SILENT`: add `'build.check_started'` beside `'build.checked'`.
- `cli/wuwei/commands/event.py` `EVENT_PRODUCERS`: `'build.check_started': 'wuwei build check'`.
- `tests/test_signal_status.py::test_emitted_kinds_have_intended_tiers` already fails when an
  emitted kind is unregistered.

### 4. Board: `cli/wuwei/commands/next.py` `step` and `cli/wuwei/commands/status.py`

`next.step` (lines 77-123):

- Keep `seats = brief.seats(data)` (it validates the records). Replace line 78 with
  `rows = state.in_flight(data)` and `running = {item for _, _, item in rows}`, so an item
  with a live check is skipped like an item with a running seat (Root cause 4).
- Replace the `names` list and the two `wait` rows (lines 113-123): keep `builders` and the
  "`{waiting}` waits: ... `{name}` started first (...) and is expected to free first" text,
  then end both rows with `Running: {state.in_flight_text(rows)}`; the second row is
  `_row('wait', f'Running: {text}; SubagentStop records each seat, and a background check reports when it exits.', 'wuwei status --line')`
  under `if rows:`.

`status`:

- `snapshot`: `result['running'] = state.in_flight(data)` (tuples serialize as lists).
- `line`: after the seats part, `if data.get('running'): parts.append('running ' + state.in_flight_text(data['running']))`.
  It shows before the gate too (the lead runs then).

### 5. Text: skills, charter, agents, docs

Keep `in the background` directly after `Agent` or `Bash` (the test's lookahead is
immediate). Edit only these sentences; #474 and #476 edit the same skill in parallel.

`skills/wuwei-plan/SKILL.md`:

- New paragraph after the "Owner questions." paragraph (line 12): "Availability. The owner's
  session is never blocked by work. Every seat runs with Agent in the background (the
  harness default), and every command that can run longer than a few seconds (the `check`
  command, `wuwei dispatch opinion`, `wuwei steward run`) runs through Bash in the
  background. While they run, take the next ready action or answer the owner from the board
  (`wuwei next`, `wuwei status --line`); never resume or interrupt a seat to answer. Call
  `wuwei build next <item>` or `wuwei dispatch next <item>` when a completion notification
  arrives, never in a polling loop. End every turn with the output of `wuwei status --line`
  as one line. Owner questions are the one thing that waits, because they wait for the
  owner."
- Line 25: replace "When the turn returns, do each item's next step (`check`, `receive`) and
  run `--all` again." with "When a seat's completion notification or a background command's
  exit arrives, do that item's next step (`check`, `receive`) and run `--all` again."
- Line 35: "For the steward, run `wuwei steward run --trigger close` (or `sweep` or
  `tool-calls`) through Bash in the background and use the `steward_launch` instructions it
  returns; they use the same formatter through runtime dispatch."
- Line 41: "- `launch`: pass `prompt` unchanged to Agent, `agent_type` as `subagent_type`,
  and a description. Launch it with Agent in the background with the rest of the launch set
  in one message (Parallel dispatch), then take the next ready action. PreToolUse registers
  the seat and SubagentStop records its result."
- Line 42: "- `continue`: use Agent in the background with `resume` set to ..." (rest unchanged).
- Line 43: "- `check`: run the returned `command` through Bash in the background, using the
  workspace's recorded executable in place of `wuwei`. ... While it runs, `build next` and a
  second `build check` exit 2 naming its start time. When it exits: exit 1 means measured
  failures ..." (rest unchanged).
- Line 49: replace "After each Agent or measured check returns, call `wuwei build next
  <item>` again." with "When the seat's completion notification or the check's exit
  arrives, call `wuwei build next <item>` again."
- Line 55: "for `continue`, do the same with Agent in the background and `resume` set to the
  returned `resume`" (today "with Agent `resume` set", which the pattern matches) and
  "Launch those seats with Agent in the background in one message so they run
  concurrently".
- Line 57: replace "Wait for all required verdicts before a fix or PR raise." with "The fix
  round and the PR raise start only once every required verdict is received."

`skills/wuwei-report/SKILL.md:12` and `skills/wuwei-retro/SKILL.md:12`: "launch that steward
with Agent in the background exactly as returned".

`charters/planner.md`: version `1.1.0` to `1.2.0`; Receive and sweep gains item 4: "Stay
available to the owner while seats and background commands run: answer from the board
(`wuwei next`, `wuwei status --line`), never by resuming or interrupting a seat. Only an
owner question waits." Item 2's steward sentence: "run `wuwei steward run --trigger
tool-calls` through Bash in the background and act on its launch prompt". Regenerate with
`bin/wuwei agents build` (`agents/planner.md`); `tests/test_agents.py` checks the drift and
`tests/test_charters.py` the one-home sentences.

`docs/site/agent.md`: a paragraph after "Run every action a command returns unchanged...":
"The owner's session is never blocked by work. Launch every seat with Agent in the
background and run every command that can take longer than a few seconds (fast checks,
`wuwei dispatch opinion`, `wuwei steward run`) through Bash in the background; act on each
completion notification with the next `build next` or `dispatch next`. End every turn with
`wuwei status --line`, which names what runs, and answer the owner from it, never by
resuming a seat. Only an owner question waits."

`docs/site/reference.md` (after the `health` bullet near line 191): "`status --line` adds
`running <role> <item> <HH:MM>, ...` while seats or fast checks run (`checks` for a `build
check` in flight), oldest first; `status --json` carries the rows as `running`, and
`bin/wuwei next` names them on its `wait` rows."

`.specify/memory/constitution.md` Constraints, new bullet: "The owner's session is never
blocked by work (design 5.2, #477): seats run in the background, any command that can run
longer than a few seconds runs in the background, the planner ends each turn with the board
in one line, and only an owner question waits. Skills and charters never tell the planner
to wait for a seat or a long command; a test reads them." Version `1.3.0`, Last Amended
`2026-10-04`.

`docs/specs/2026-09-24-wuwei-design.md` 5.2, after the Records paragraph: "Availability
(owner, 2026-10-04, #477). The owner's session is never blocked by work. Seats run in the
background; any command that can run longer than a few seconds (fast checks, `dispatch
opinion`, `steward run`, calibration) runs in the background, and the planner acts on its
completion notification. The planner's turn ends with the board in one line (`wuwei status
--line`, which names the running seats and checks with their start times), and the owner
can speak at any time; the planner answers from the board, never by resuming or interrupting
a seat. Owner questions are the one thing that waits, because they wait for the owner."

### 6. Text test: `tests/test_charters.py`

```python
BLOCKING = re.compile(
    r"\bwait(?:s|ing)?\s+for\s+(?:the\s+|its\s+|each\s+|every\s+|all\s+)?(?:required\s+)?"
    r"(?:agent|turn|seats?|builders?|sentinels?|checks?|verdicts?)\b"
    r"|\bblock\s+until\b|\bforeground\b|\bturns?\s+returns?\b"
    r"|\b(?:through|with)\s+bash\b(?!\s+in\s+the\s+background)"
    r"|\bwith\s+agent\b(?!\s+in\s+the\s+background)", re.I)
```

- `test_no_blocking_instruction_in_skills_or_charters`: every file in `skills/*/SKILL.md`,
  `charters/*.md`, `agents/*.md` and `docs/site/agent.md` has no match; the failure names the
  file and the matched text.
- `test_blocking_pattern_samples` (parametrized): the old sentences of spec Root cause 1 to 3
  plus "Block until the seat stops." and "Run the suite in the foreground." match; the new
  phrasings above (the line 41, 43 and 57 replacements, the steward line, "the planner stays
  available to the owner while seats run") do not.
- `test_never_blocking_rule_is_written_down`: "never blocked by work" in the constitution,
  the design doc and agent.md; "never by resuming or interrupting a seat" in
  `charters/planner.md`; "wuwei status --line" and "only once every required verdict is
  received" in the plan skill.

`"before X" blocks until X is met` (shepherd, pinned in `RULES`) does not match: the pattern
is `block until`, not `blocks until`.

### 7. Headless fixture day: `scripts/headless_e2e.py`

- `prepare`: `fast_checks = ["sleep 5 && test -s README.md"]`.
- `prompt` step 3: "Run build next A; pass its prompt UNCHANGED to Agent in the background
  and agent_type as subagent_type, with a description, then end your turn. When the
  builder's completion notification arrives, call build next A; run any returned check
  command through Bash in the background and end your turn; when it exits, call build next A
  until done; done moves A to gate."
- `validate`: compute `planner` before use and add

```python
def yielded(start, end):
    """A planner Stop between a start row and the first later end row."""
    for index, row in enumerate(hooks):
        if start(row):
            last = next((k for k in range(index + 1, len(hooks)) if end(hooks[k])), None)
            if last is not None and any(h['event'] == 'Stop' and h.get('session') == planner
                                        for h in hooks[index + 1:last]):
                return True
    return False
```

  with the builder pair (PreToolUse exit 0, tool `Agent`, `subagent_type` `wuwei:builder`;
  SubagentStop with `agent_type` `wuwei:builder`) and the check pair (PreToolUse exit 0, tool
  `Bash`, `build check A` in `input.command`; the `cli` row with `args == ['build', 'check',
  'A']`), findings "planner did not yield a turn between the builder launch and its stop"
  and "planner did not yield a turn between the check launch and its result".

The offline `evidence()` in `tests/test_headless_e2e.py` gains a planner Stop between the
builder launch and its SubagentStop, and the check rows with a planner Stop between them;
`test_missing_contract_evidence_fails_despite_success_prose` gains `no-builder-yield` and
`no-check-yield` mutations that drop each of those Stops.

## What must not change

- The SubagentStop guard and `build.stopped` (#473 owns them).
- The `check` action's shape and command (`wuwei build check <item>`), `fast_checks.record`,
  the push-guard evidence and its readers.
- `build next` exit 2 while a builder seat runs (its message at `build.py:113`).
- `next`'s one-row contract, its other rows and their commands; `status --line`'s existing
  parts and order (the new part is appended after `seats`).
- The `dispatch next --all` contract from #474; only the skill sentence about acting after a
  turn changes.
- The shepherd's pinned "blocks until" sentence.

## Files

| File | Change |
| --- | --- |
| `cli/wuwei/state.py` | `check_running`, `in_flight`, `in_flight_text` |
| `cli/wuwei/commands/build.py` | `_busy`, marker in `check`, pop in `complete_checks`, guard in `next_action` |
| `cli/wuwei/signal.py`, `cli/wuwei/commands/event.py` | register `build.check_started` |
| `cli/wuwei/commands/next.py` | running set and wait rows from the helpers |
| `cli/wuwei/commands/status.py` | `running` in snapshot and line |
| `skills/wuwei-plan/SKILL.md`, `skills/wuwei-report/SKILL.md`, `skills/wuwei-retro/SKILL.md` | background phrasing |
| `charters/planner.md`, `agents/planner.md` | availability rule, version, regenerated agent |
| `docs/site/agent.md`, `docs/site/reference.md` | rule, status part |
| `.specify/memory/constitution.md`, `docs/specs/2026-09-24-wuwei-design.md` | the rule |
| `scripts/headless_e2e.py` | slow fixture check, prompt, two yield assertions |
| `tests/test_charters.py`, `tests/test_build_next.py`, `tests/test_next.py`, `tests/test_signal_status.py`, `tests/test_headless_e2e.py` | tests |
