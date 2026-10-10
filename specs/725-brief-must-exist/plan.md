# Implementation Plan: a launch whose brief does not exist is refused

**Branch**: `725-brief-must-exist` | **Date**: 2026-10-10 | **Spec**: `specs/725-brief-must-exist/spec.md`

## Summary

One existence check in the agent-launch guard, returning exit 2 with a reason whose
constant prefix joins the existing records floor list, and one line in the hook's posture
so that a records-floor reason actually blocks (today it is only labelled). No new module,
helper, config key or event kind.

## Technical Context

**Language**: Python 3.11+, stdlib only at runtime; pytest for tests.
**Touched runtime files**: `cli/wuwei/guards/agent_launch.py`, `cli/wuwei/guards/__init__.py`,
`cli/wuwei/commands/hook.py`.
**Tests**: `tests/test_agent_launch.py`, `tests/test_posture.py`, `tests/test_invariants.py`.
**Docs**: `docs/specs/2026-09-24-wuwei-design.md` (9.2 invariant row and the records floor
line), `docs/site/security.md`, `docs/site/reference.md`, `docs/site/concepts.md`.

## Constitution Check

- I stdlib only: yes, `Path.exists` only.
- II three-state exits: the refusal is exit 2 with its reason; `check` passes `_check`'s
  tuple through unchanged.
- III one behaviour, one function: the existence check lives only in `agent_launch._check`;
  the floor decision lives only in `hook.posture`.
- IV test first: every change below has its failing test first (tasks.md).
- V ponytail: reuse `RECORDS_FLOOR` and the posture loop; no new abstraction.
- VII security: closes a path where a seat ran with no brief and no record below strict.
- Workflow: the invariant goes into design spec 9.2 and `tests/test_invariants.py`.

## Design

### 1. `cli/wuwei/guards/agent_launch.py`, `_check`

Right after the existing brief path validation block (the `raise ValueError(f'invalid brief
path; {DAMAGED}')` at line 135) and before the `events.jsonl` read at line 136, add:

```python
if not path.exists():
    return 2, (f'brief {path.relative_to(root)} does not exist; '
               f'run bin/wuwei brief {role} <item> <name> first')
```

- `path` is already validated as `directory / 'briefs' / <name>.md` with no symlink and no
  traversal, so `path.relative_to(root)` is always `.wuwei/days/<day>/briefs/<name>.md`,
  normalised (a `./` or doubled slash in the prompt is gone).
- `role` is the third element `_seat` already returns (`subagent_type` after its last `:`).
- Returning, not raising: `check` maps `brief.Refused` to exit 1 and any other exception to
  `agent launch could not run: ...`; the issue wants exit 2 with this exact reason, and
  `_check` already returns tuples (`return 0, ''`, `return _adhoc(payload)`).
- Nothing is written: the return happens before `state._write_state(reserve, ...)`.
- This also replaces today's `FileNotFoundError` path at line 158 for a logged brief whose
  file was removed; line 158 stays as it is (it can still meet a race, which keeps the
  generic exit 2).

### 2. `cli/wuwei/guards/__init__.py`, `RECORDS_FLOOR`

Add the constant prefix of the new reason, with the issue number in the comment:

```python
RECORDS_FLOOR = ('outward: security.', 'owner disposition markers must be posted by the owner',
                 'brief .wuwei/days/')  # #725: a launch naming a missing brief
```

Update the comment above it (line 64) to say the launch case. No guard or other reason
starts with `brief .wuwei/days/` today (checked with grep over `cli/wuwei`).

### 3. `cli/wuwei/commands/hook.py`, `posture`

At line 279, the records floor branch sets the level as well as the line:

```python
if reason.startswith(RECORDS_FLOOR):
    decided, line = 'block', 'posture: records = block (floor; no setting lowers it)'
```

This is the root-cause fix of "labelled block, not blocked": every `RECORDS_FLOOR` reason now
blocks in every posture and through any area override (an `off` override is checked later,
`if decided == 'off'`, and no longer applies). The two existing members come from
owner-only checks that already block, so their result is unchanged
(`tests/test_posture.py::test_owner_only_line_below_strict`,
`tests/test_hooks.py::test_held_draft_posture_line_names_the_card` pin it).

### 4. Invariant and docs

- `docs/specs/2026-09-24-wuwei-design.md` 9.2 table: a new row, the next free number above
  the highest present (I56 at spec time): "An Agent launch naming a brief that does not exist
  is refused in every posture with the brief command and registers no seat | per posture,
  the PreToolUse hook on a launch naming a missing brief, then the day's seats and
  `seat launched` events | #725".
- The same file, the `records` bullet (line 1981), and `docs/site/security.md` line 60,
  `docs/site/reference.md` line 393 (the sentence on canary and markers) and
  `docs/site/concepts.md` line 178: add "a seat launch naming a brief that does not exist"
  to the records floor cases.
- `tests/test_invariants.py`: `i56(case, rules)` reading posture only (`READS['I56'] = (0,)`),
  registered in `INVARIANTS`; memoised per posture with `rules.memo`, it runs `rules.hook`
  on an Agent payload (`subagent_type` a WUWEI role, prompt `WUWEI brief: <today's
  briefs>/i56-missing.md`) and requires exit 2, `agent_launch.check` giving the exact
  reason, and no seat or `seat launched` event added. The table-order test (line 1514)
  requires the row order in the design spec to match `INVARIANTS` order, so the row goes
  last in both.

## What must not change

- The order and wording of every other `agent_launch` refusal, and their `seats` level.
- `_seat`, `_adhoc`, `check_mcp`, `reserve` and the SubagentStop path.
- `level()` in `guards/__init__.py` and `workspace.FLOORS`.
- The `hook.posture` result for any reason not starting with a `RECORDS_FLOOR` prefix.
- `brief.write` and the `bin/wuwei brief` command.

## Complexity Tracking

None. Three small edits in existing functions; no new files in `cli/`.
