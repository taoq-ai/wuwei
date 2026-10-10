# Implementation Plan: A slow traces hook is a warning, the trace read uses the writer's digest, and the status line keeps its budget

**Branch**: `659-traces-slow` | **Date**: 2026-10-10 | **Spec**: `specs/659-traces-slow/spec.md`

## Summary

Four small changes at the spots the root cause names. The traces guard sends a
`TimeoutError` to a slow tail (warning with elapsed ms, `traces.slow`, exit 0 below
strict). It keeps a digest of its own writes so a call reads neither `traces.jsonl` nor
`events.jsonl` below a steward boundary, skips the steward check once over budget, and
stops rewriting state for a seat that is already bound. The heartbeat tick renders the
status line into the watch state, and `status --line` prints that text when its compute
overruns its budget.

## Technical Context

Python 3.11+, stdlib only at runtime (`threading`, `time`, `json`), pytest for tests. No
new module, dependency or config key. One new event kind (`traces.slow`) and one new day
file (`traces.digest.json`). Line numbers are `main` at 35306d9.

## Constitution Check

- Test first: every behaviour has a test task ordered before its implementation
  (`tasks.md`).
- Three-state exits: a slow guard returns 0 below strict only after printing its reason
  and recording `traces.slow`; under strict it keeps today's exit 2. Principle VII (#530):
  this removes a wall below strict and adds none.
- Fail closed: an unreadable posture counts as strict; a failed compute prints
  `WUWEI ? unmeasured`, never the cache.
- No forgeable trust: `traces.slow` reserved to its producer; the digest is protected like
  the other day files and is a cache whose worst forged value delays an advisory nudge.
- Workflow: the changed guard rule gets a 9.2 row and its invariant check.

## Design

### 1. Slow tail in the traces guard (`cli/wuwei/guards/traces.py`, `check`, lines 84-133)

- `started = time.monotonic()` as the first line of `check` (import `time` at module
  level; it is already loaded by the interpreter).
- Before the inner `except (OSError, ValueError, TypeError, KeyError, RuntimeError):` at
  `:116`, add `except TimeoutError: raise` so the outer handler at `:121` takes it.
- In the outer `except BaseException as exc:` set
  `slow = isinstance(exc, TimeoutError)`; when slow, the reason is
  `f'wuwei traces: did not finish in time after {ms} ms (TimeoutError); the tool ran and its span may be missing; run bin/wuwei doctor'`
  with `ms = round((time.monotonic() - started) * 1000)`; otherwise today's reason.
- Tail at `:123-133`: the event kind is `'traces.slow'` when slow, else `'traces.gap'`;
  the slow payload adds `'elapsed_ms': ms`; the slow append passes `timeout=1`. The
  "could not log" stderr line names the kind it tried.
- Return: `if slow and not _strict(root): return 0, ''`, then today's
  `return (2, reason) if security_data is not None else (0, '')`.
- `_strict(root)`: `workspace.posture(workspace.load_config(root))[0] == 'strict'`, True on
  any exception. #601 adds the same function; if `main` has it when you build, reuse it.
- Rebase note for #601 (it replaces the inner early return with a `step` reason and an
  `inspect` flag): keep `except TimeoutError: raise` first in the inner handlers and keep
  this slow branch ahead of #601's posture return.

### 2. Bounded wait for the slow record (`cli/wuwei/state.py`, `append_event`, `:144-152`)

- Add keyword `timeout=30` and pass it to `lock_ex(lock, 'state.lock', timeout)`. Every
  existing caller keeps 30 s.

### 3. Writer's digest and the steward gate

`cli/wuwei/guards/traces.py`:

- `BUDGET_MS = 1000` with a comment: a hook that already ran a second is under load (a
  warm call takes 5 to 20 ms); ponytail: sustained load above it defers the steward nudge
  until a call fits.
- `_digest(directory, calls=0, steward=None)`: opens `directory / 'state.lock'`, takes it
  with `state.lock_ex` (the pattern in `heartbeat._state`, `specmode.py:222`), reads
  `traces.digest.json`. Valid means a dict whose `tool_calls` and `steward` are ints with
  `0 <= steward <= tool_calls`. Valid: `tool_calls += calls`, `steward = max(steward,
  value)` when one is given. Missing or invalid: `tool_calls` is
  `(directory / 'traces.jsonl').read_bytes().count(b'\n')` (0 when absent), `steward` is
  0 (or the given value). Writes it with `workspace.atomic_write(path, json.dumps(digest)
  + '\n', sync_dir=False)` and returns it.
- `_record` gains keyword `started=None`; `check` passes its `started`.
- Replace `:75-80` (the line count and the steward call) with, inside the same
  `try: ... except Exception: pass`:
  `digest = _digest(directory, calls=1)`; when `started is None` or elapsed ms is below
  `BUDGET_MS`, `base = steward.maybe_run_for_tool_calls(digest['tool_calls'], root,
  digest['steward'])` and, when `base != digest['steward']`, `_digest(directory,
  steward=base)`.
- The span append at `:55-58` stays `state.append_jsonl(...)` (tests replace it).

`cli/wuwei/steward.py`, `maybe_run_for_tool_calls` (`:253-266`):

- Signature `(count, root=None, base=0)`. After reading the interval, `if count - base <
  interval: return base` (no events read).
- Otherwise today's lines, then return `count` when it appended `steward.due`, else
  `max([last, *(due counts above last)])`. Today's return value (0) is unused.
- Why it is exact: the base is always a `steward.run` count or a `steward.due` count; when
  today's rule would append a due, every due is at or below `last`, so the base is at or
  below `last` and `count - base >= interval` holds. Changing the interval mid-day is
  covered because the gate reads the current interval.

### 4. Seat bind without a write when bound (`cli/wuwei/guards/traces.py`, `_record`, `:60-74`)

- Before `state._write_state(bind, root, reserved=False)`, read `state.read_state(root)`
  and skip the write when every seat whose `brief` equals `reference` already has
  `transcript == str(transcript_path)` and the session in `trace_sessions` (and at least
  one such seat exists; with none, `bind` changes nothing, so skip too).

### 5. Status line cache

`cli/wuwei/heartbeat.py`, `beat` (`:199-220`):

- After `probes = measure(root)`, render the line in process:
  `suffix = f' · as of {workspace.now():%H:%M}'`,
  `text = status.line(status.snapshot(workspace.day_dir(root), line=True), status.WIDTH - len(suffix)) + suffix`
  inside `try/except watch.ERRORS` (no text on failure). Import `status` from
  `wuwei.commands` inside `beat`.
- Add `'status_line': text` to the changes passed to the existing `watch.save` call at
  `:212` only when rendered. The event payload (`record`) is unchanged.

`cli/wuwei/commands/status.py`, `run` (`:338-354`):

- `LINE_BUDGET_MS = 100` next to `WIDTH`, commented: half of the heartbeat's 200 ms wall,
  the other half is interpreter start and printing.
- When `args.line and not args.json and args.width == WIDTH`: run `snapshot` in a daemon
  `threading.Thread` that stores `(True, data)` or `(False, exc)`; `join(LINE_BUDGET_MS /
  1000)`. If still alive, read `state.read_state(directory=workspace.day_dir()).get('watch',
  {}).get('status_line')` (any exception: no cache); a `str` is printed and `CLEAN`
  returned. Otherwise `join()` and continue with the result, re-raising a stored exception
  into today's `except` clause so `WUWEI ? unmeasured` is unchanged. Import `threading`
  inside this branch only.
- Every other mode (`--json`, full status, another width) is unchanged.

### 6. Reservations, protection, docs and invariant

- `cli/wuwei/commands/event.py`, `EVENT_PRODUCERS` (`:52`): add
  `'traces.slow': 'wuwei hook PostToolUse'` next to `traces.gap`.
- `cli/wuwei/signal.py`: no change (unknown kinds default to `nudge`); add
  `'traces.slow': 'nudge'` to the expected map in
  `tests/test_signal_status.py::test_emitted_kinds_have_intended_tiers`.
- `cli/wuwei/guards/protect_state.py:370`: add `'traces.digest.json'` to the protected day
  file names.
- `docs/site/reference.md:217`: one sentence each for `traces.slow` (warning with elapsed
  ms, exit 0 below strict) and the status line falling back to the heartbeat's cached line
  marked `as of HH:MM`.
- `docs/specs/2026-09-24-wuwei-design.md` 9.2 table: one row with id I50 (reserved for
  this item by the orchestrator): "Under observe and guarded a traces guard that did not finish in
  time never fails a tool call: a `TimeoutError` is a warning naming its elapsed
  milliseconds, recorded as `traces.slow`; strict refuses it", check "per posture,
  `traces.check` with the trace read raising `TimeoutError`", notes "#659; any other
  failure keeps the `traces.gap` path".
- `tests/test_invariants.py`: the check, memoised per posture as `i54` on #601's branch
  does (one workspace per posture, the read swapped by plain attribute assignment and
  restored in `finally`, no mock), in `INVARIANTS` and `READS` with `(0,)`.

## What must not change

- `AREAS['traces']`, `FLOORS`, `hook.posture`, `hook.run`.
- `state.lock_ex`'s default 30 s and every existing caller's wait.
- The could-not-read path: the inner return at `traces.py:117`, the `traces.gap` tail and
  its reasons; `tests/test_traces.py` and `tests/test_guard_mutation.py` pass unchanged.
- `state.append_jsonl`'s signature and the span's shape.
- Steward due semantics: `test_trace_threshold_marks_steward_due_without_launch` and
  `test_default_interval_is_250_tool_calls` pass unchanged.
- The security inspection runs on every call, whatever the elapsed time.
- `status --line` output at normal speed, `--json` and full `status`; the heartbeat probe
  list, its 200 ms budget and the probe adapter.

## Files

| File | Change |
|------|--------|
| `cli/wuwei/guards/traces.py` | slow tail, `_strict`, `BUDGET_MS`, `_digest`, steward gate, bind skip |
| `cli/wuwei/state.py` | `append_event(..., timeout=30)` |
| `cli/wuwei/steward.py` | `maybe_run_for_tool_calls(count, root, base)` gate and return |
| `cli/wuwei/commands/status.py` | `LINE_BUDGET_MS`, thread and cache fallback in `run` |
| `cli/wuwei/heartbeat.py` | `beat` renders and saves `status_line` |
| `cli/wuwei/commands/event.py` | reserve `traces.slow` |
| `cli/wuwei/guards/protect_state.py` | protect `traces.digest.json` |
| `docs/site/reference.md` | two sentences |
| `docs/specs/2026-09-24-wuwei-design.md` | one 9.2 row |
| `tests/test_traces.py` | slow per posture, digest, budget skip, bind skip |
| `tests/test_steward.py` | base gate |
| `tests/test_heartbeat.py` | beat writes the cache; `status --line` cache fallback |
| `tests/test_signal_status.py` | expected tier for `traces.slow` |
| `tests/test_protect_state.py` | digest write refused |
| `tests/test_invariants.py` | the new invariant |
