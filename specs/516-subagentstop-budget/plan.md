# Implementation Plan: SubagentStop back under its latency budget

**Branch**: `516-subagentstop-budget` | **Spec**: `spec.md`

## Summary

Remove the blocked time first: one SubagentStop that stops a seat today writes state once
(the session row rides in the seat-stop write, its two events in one append), and every
state write fsyncs its directory once instead of twice. That takes the common path from 8
fsyncs to 3. Then take the unused imports off the path (`wuwei.decision`,
`wuwei.commands.build`, `hashlib`) and read a missing report from the transcript's tail.
The latency test, its budgets and every guard result stay as they are.

## Technical Context

Python 3.11+ stdlib only; pytest dev-only. The new hook tests reuse the `seeded_workspace`
fixture of the latency test (the exact benchmark path) and the `LAUNCHER_MODULES` script
style of the #346 import-graph tests, run in a fresh interpreter. The tail-read test reuses
`tests/test_handback.py`'s `write` helper.

## Constitution Check

Exits 0/1/2 unchanged; no refusal added in any posture; the single writer stays
`state._write_state`; events stay append-only; no new event kind, state key or config.
Stdlib only. The durability argument for the shared directory fsync is in spec.md,
Assumptions. Pass.

## Changes

### `cli/wuwei/workspace.py`, `atomic_write`

- Add keyword `sync_dir=True`. When false, skip the directory open and fsync after the
  rename; everything else (temp name, file fsync, rename, cleanup) unchanged. The 70-odd
  other callers keep the default.

### `cli/wuwei/state.py`

- `_append_jsonl(path, *records)`: encode every record (each through `known_values`, each
  ending in a newline) and write them with the existing single `os.write`, the same
  leading-newline repair, short-write check and `ftruncate` on failure. `append_jsonl` and
  every current caller pass one record and see no change.
- `_append_event(kind, payload, directory, more=())`: build the main record and one record
  per `(kind, payload)` in `more`, all with the same `ts`, and call `_append_jsonl` once.
- `_write_state(..., more=())`: validate each extra payload with `_event_payload`; write
  `state.json` with `atomic_write(..., sync_dir=False)` and the snapshot with the default (its
  directory fsync makes both renames durable; one comment line says so); pass `more` to
  `_append_event` with the same `prs_seen` added to each extra payload (the main event keeps
  `phase_changes` as today).
- `stop_seat(..., session=None)`: `session` is `{'session_id', 'hook', 'cwd'}` or None. When
  given, `update` also calls `sessions.record(data, session_id, hook=hook, cwd=cwd)` (import
  inside the function; `sessions` imports `state` at module level), and `_write_state` gets
  `more=[('session.seen', {'session_id': ..., 'hook': ...})]`, the payload `sessions.touch`
  writes today.

### `cli/wuwei/guards/lifecycle.py`

- Extract `seen_row(payload, event)` from `_seen`: the session id check and the hook name,
  returning `{'session_id', 'hook', 'cwd'}` or None. `_seen` becomes
  `row = seen_row(...)`, then `sessions.touch(root, **row)` or None; behaviour unchanged.
- `RECORDED = 'wuwei_session_recorded'`: the payload key the seat stop sets.
- `subagent_stop`: skip `_seen` when `payload.get(RECORDED) == str(root)` for the root
  `scoped(payload)` returned (both sides compare the resolved root path).

### `cli/wuwei/guards/agent_launch.py`, `stop`

- Keep the state read: `data = state.read_state(directory=directory)`,
  `reserved = brief.seats(data)[name]`.
- Before the two `stop_seat` calls compute once
  `session = seen_row(payload, 'SubagentStop') if directory == workspace.day_dir(root) else None`
  (`from wuwei.guards.lifecycle import RECORDED, seen_row` inside `stop`; lifecycle is
  already loaded on SubagentStop and this keeps it off PreToolUse Agent). Pass
  `session=session` to both `state.stop_seat` calls (the unmeasured branch and the normal
  one); after a call returns and `session` is set, set
  `payload[RECORDED] = str(root.resolve())`.
- Builder branch: import `wuwei.commands.build` and call `build.stopped` only when
  `data.get('builds', {}).get(item)` is set; `build.stopped` already returns False when
  there is no record, so the outcome is the same. When it handles the stop, no fold and no
  marker (lifecycle touches as today).

### `cli/wuwei/guards/decision.py`

- Drop the module-level `from wuwei.decision import DECISION_ID, lint_file,
  record_rejection, today_path`; import the names used inside `check_write` (`lint_file`,
  `record_rejection`), `record_gate` (`DECISION_ID`, `today_path`) and `check_question`
  (`today_path`, `lint_file`). `check_stop` reaches `wuwei.decision` only through
  `check_question` when the message asks a question. Tests import these functions by name,
  never the moved names.

### `cli/wuwei/guards/verdict.py`, `check_retro`

- Move `from hashlib import sha256` from the top of the function to just before the digest
  is computed, after the charter check returns for agent types without a charter.

### `cli/wuwei/brief.py`

- Drop the top-level `import hashlib`; import it inside `last_turn` and `write` (the brief
  digest).
- `_entry(line)`: the per-line parse `last_turn` does today, returned as `None` (blank, not
  a dict, not `type: assistant`) or `(text, handback)` where `handback` is the
  `SubagentHandback` `input.message` string or None; raises `ValueError` (`malformed
  transcript entry`) as today, and `json.loads` errors propagate as today.
- `last_turn(path)`: unchanged contract (`[index, sha256]`, text, handback flag), its loop
  now calls `_entry`.
- `tail_turn(path)`: open the file in binary, seek from the end, read a window (64 KiB,
  then 4x per step); split on `b'\n'`, drop the first piece unless the window starts at 0,
  decode each line as UTF-8 and walk from the end with `_entry`; return `(text, handback)`
  of the first entry found; raise `ValueError('transcript has no assistant turn; ...')`
  after the window reached the start. A `ponytail:` comment names the ceiling (an assistant
  entry far back still reads most of the file).
- `stop_text`: call `tail_turn(path)` instead of `last_turn(path)`; return the hand-back
  message when present, else the text; the blank-report `ValueError` unchanged.

### Tests

- `tests/test_hooks.py`
  - `test_subagent_stop_loads_no_more_than_pretooluse(seeded_workspace, tmp_path)`: run the
    fixture's `commit` (PreToolUse Bash) and `SubagentStop` payloads twice each through
    `LAUNCHER_MODULES` in `-I -P -S` (the second run of each is measured, so pycache and the
    config cache are warm, with `reset()` before each); assert
    `subagent - pretooluse <= SUBAGENT_STOP_MODULES`, the allowlist in spec US1.4.
  - `test_subagent_stop_writes_state_once(seeded_workspace, tmp_path)`: a launcher variant
    that wraps `os.fsync` and `wuwei.state._append_jsonl` with counters before
    `runpy.run_module` and writes the counts at exit; run the fixture's SubagentStop once
    after `reset()`; assert exit 0, empty stdout, `fsync == 3`, `appends == 3`; the seat
    `builder-1` is `stopped` with `agent_id`; `sessions.abc123.last_hook ==
    'SubagentStop:wuwei:builder'`; the last four events (ignoring the fixture's `note`
    rows) are `seat stopped`, `session.seen`, `discovery.requested`, `spec.warned` with
    the payloads of spec US1.3.
- `tests/test_handback.py`
  - `test_stop_text_reads_the_tail(tmp_path)`: (a) a first line of invalid UTF-8 bytes,
    over 64 KiB of user lines, then `HANDBACK`: `stop_text({'agent_transcript_path': ...})
    == REPORT` while `last_turn` raises `ValueError`; (b) an assistant text entry followed
    by over 256 KiB of user lines: `stop_text` returns its text.
  - `test_unmatched_seat_stop_still_records_session(seat, monkeypatch, capsys)`: through
    `hook_stop` with `agent_type='wuwei:builder'`, `last_assistant_message` holding the three
    retro lines (`Blocked: none`, `Gap: none`, `Change: none`) and a transcript whose brief
    reference names no reservation: exit 0, `seat stop unmatched` recorded, the session `abc123` row present
    with `last_hook == 'SubagentStop:wuwei:builder'` and exactly one `session.seen` event.
  - `test_hook_reads_nothing_for_other_agents`: also patch `brief.tail_turn` with the same
    `unread` stub, so the test keeps guarding every report read.

## What must not change

- `test_workspace_hook_latency`, `assert_latency_budget`, `startup_floor`, the budgets and
  the latency job.
- Guard results, exit codes, refusals and posture handling; event kinds, payloads and
  `prs_seen`; the content of `state.json` and the snapshot after a stop.
- `brief.last_turn`'s return values (the build binding stores its index and hash),
  `brief.transcript_reference` and `stopping_seat`'s binding.
- `sessions.touch` and every other caller of `_seen` (SessionStart, Stop).
- The directory fsync of every `atomic_write` call outside `_write_state`.
- The order in which `discover()` imports guard modules.

## Shared helpers reused

`state._write_state` (the single writer), `state._append_jsonl` (the locked append),
`sessions.record` (the registry upsert), `workspace.atomic_write`, `brief.last_turn`'s
parser (as `_entry`), `lifecycle._seen`'s hook naming (as `seen_row`).

## Verification

`python -m pytest -q` with the task's interpreter, all green; then
`WUWEI_BENCH=1 python -m pytest -q tests/test_hooks.py -k latency -s` and report the printed
SubagentStop line (the wall figure on macOS does not show the fsync saving; the runner
does).
