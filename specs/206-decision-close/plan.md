# Implementation Plan: An answered owner decision clears close, and Stop never traps the session

**Branch**: `206-decision-close` | **Date**: 2026-09-30 | **Spec**: [spec.md](spec.md)

## Summary

Add one reader, `decision.answered(data, identifier)`, and call it from the four places
that decide "answered" wrongly today (close, `pr act`, `pr disposition`, cockpit). Make
`decision outcome` also rewrite the record's `Outcome:` line. Make the planner Stop guard
return 0 on a Stop retry. No new modules, no new state keys, no new config.

## Technical Context

Python 3.11+ stdlib runtime, pytest dev-only. State is the day `state.json` read through
`state.read_state`; decision records are `days/<date>/decisions/D-<n>.md` read through
`decision.evaluate`. Tests use the existing in-process fixtures and fakes
(`tests/test_stop.py` `case`, `tests/test_pr_actions.py` `linked`, `tests/test_decision.py`
`ws`, `tests/test_dashboard.py` `workspace`). Owner confirmation is patched with
`monkeypatch.setattr('wuwei.integrity._host_confirm', lambda value, **kwargs: True)`,
as the existing owner outcome tests do.

## Constitution Check

- I stdlib only: `re` and existing modules only.
- II exits: close stays 0/1/2; `pr act` keeps its codes; Stop retry is 0; a non-bool
  `stop_hook_active` stays exit 2.
- III one behaviour, one function: "answered" lives only in `decision.answered`.
- IV test first: every change below has a failing test ordered before it in tasks.md.
- V ponytail: one helper of three lines, one-line call-site edits, one rewrite line.
- VII security: only an owner outcome (written by the host-confirmed
  `decision outcome` producer, reserved in `state.RESERVED`) counts; a seat outcome or an
  edited file line never clears an owner decision.

## Design

### 1. Shared reader, `cli/wuwei/decision.py`

Add next to `route`:

```python
def answered(data, identifier):
    """Return the owner's recorded option for a decision, or None while it is unanswered."""
    record = data.get('decision_outcomes', {}).get(identifier)
    return record.get('option') if isinstance(record, dict) and record.get('decided_by') == 'owner' else None
```

`data` is the day state mapping the caller already read. It returns the option string so
`pr act` can route on it; callers that need a yes/no use its truthiness (option ids are
nonempty by the evaluator).

### 2. Day close, `cli/wuwei/closing.py` `unresolved` (line 184)

`if identifier not in resolved:` becomes
`if identifier not in resolved and not decision.answered(data, identifier):`.
`data` is already read at line 160. Nothing else in `unresolved` changes: seat
dispositions, approved items and pushed branches keep their current rules.

### 3. PR actions, `cli/wuwei/pr_actions.py`

- `_verify` (lines 19-21): read `data = state.read_state(root)` once and reject only when
  `identifier in data.get('decision_outcomes', {}) and not decision.answered(data, identifier)`.
  Route, `Decided-by`, fingerprint and owner-comment checks are unchanged.
- `_thread` (lines 350-377): inside the `prior ... fingerprint` match, after the
  `path.is_file()` check, compute `option = decision.answered(state.read_state(root), path.stem)`.
  - `None`: keep today's `pending = ... owner_decision ...; continue`.
  - `'change'`: `return _fix(root, ref, item, measured, feedback=text)`.
  - otherwise: fall through to the reply step with `answer = {'decision': prior['path'], 'option': option}`
    merged into the `reply` JSON at line 380.
  The fix-request test at line 377 becomes `elif` so an answered scope thread is never
  reclassified by its wording. The new-decision branch (`decision.write`) is unchanged.
  Initialise `answer = {}` per owed key.

### 4. Owner outcome producer, `cli/wuwei/commands/decision.py` `owner_outcome`

After `state._write_state(...)` succeeds (line 107-110), before `return 0, args.option`:

```python
workspace.atomic_write(path, re.sub(r'^((?:#{1,6} )?Outcome:).*$', lambda m: f'{m[1]} {args.option}',
                                    text, count=1, flags=re.M))
```

Add `import re`. `text` is the confirmed record (already checked unchanged at line 88).
State is written first, so a failed state write never leaves a rewritten file; if the
file write fails after the state write, every reader still sees the answer through
`answered`. Mark the first-match rewrite with a `ponytail:` comment (ceiling: a record
with an inactive example `Outcome:` above the real field; upgrade: rewrite the active
line found by `verdict.active_text`).

### 5. Cockpit, `cli/wuwei/commands/dashboard.py` `cockpit_snapshot` (line 28)

`if fields['Outcome'].lower() != 'pending':` becomes
`if fields['Outcome'].lower() != 'pending' or answered(data, path.stem):` and import
`answered` with the existing `wuwei.decision` import. `data` is already read at line 20.

### 6. Stop guard, `cli/wuwei/guards/stop.py` `check`

First statement of `check`, mirroring `guards/lifecycle.py:69-70`:

```python
if payload.get('stop_hook_active') is True:
    return 0, ''
```

Delete the comment at line 35. Keep the boolean type check at lines 33-34 so a malformed
flag on a planner's Stop stays exit 2. Returning `(0, '')` prints nothing, so the refusal
text appears in the first block only.

### 7. Docs, `docs/site/concepts.md` "Day close"

Replace "Stop retry flags do not bypass these checks." with: the Stop hook blocks once
per stop attempt and exits 0 on Claude Code's retry, while `bin/wuwei close` still
reports every finding. Add one sentence: an owner decision answered with
`bin/wuwei decision outcome D-<n> OPTION` counts as resolved, and the command writes the
chosen option into the record's `Outcome:` line.

## Must not change

- `closing.check`, obligations, retro and PR-state findings; `wuwei close` output for
  anything other than answered owner decisions.
- `decision.evaluate`, `route`, `seat_outcome`, `decision route`, and every
  precondition and confirmation step of `owner_outcome`, including item resume.
- `report.build` and `steward.decision_queue` (already correct; pinned by tests).
- `watch` digest (seat outcomes only), `mcp` decision handling, `metrics`.
- `guards/lifecycle.py` and `guards/agent_launch.py` Stop/SubagentStop handling;
  `commands/hook.py` translation.
- `state.RESERVED` and event reservations (no new keys or kinds).

## Tests changed because the old behaviour was the bug

- `tests/test_stop.py::test_stop_table` `active_retry`: expected 1 becomes 0.
- `tests/test_stop.py::test_close_owner_decision_table`: with `retry=True` the expected
  code is 0 for every mode (the non-retry column keeps today's codes).
- `tests/test_stop.py::test_close_command_and_hook_retry`: first Stop with
  `stop_hook_active: false` exits 2 with a `block`; the retry with `true` exits 0 with
  empty stdout.
- `tests/test_pr_ownership.py::test_poll_produces_deadline_stop_and_signal`: call the
  guard with `stop_hook_active=False`; it tests deadlines, not retries.

## Validation

`python -m pytest -q` from the worktree root with the pipeline interpreter. Grep changed
files for em-dashes, emojis and absolute local paths.
