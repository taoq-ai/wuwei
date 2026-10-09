# Implementation Plan: fix rounds from a fresh Agent launch, analysis.md through the CLI

**Branch**: `614-fix-round-fresh-launch` | **Date**: 2026-10-09 | **Spec**: [spec.md](spec.md)

## Summary

Bug A: the launch guard treats a launch without `resume` of a brief whose continue is
pending as that continuation, and the builder binding forgets the replaced agent's id so the
fresh agent's SubagentStop is recorded. Bug B: one new plumbing command writes the analyze
report where a subagent cannot.

## Technical Context

Python 3.11+ stdlib only (constitution I). pytest dev-only. One new command module
(`cli/wuwei/commands/spec.py`), no new event kind, no config key.

## Constitution Check

- I stdlib: no new import beyond the package.
- II exits: the new command exits 0 or 2; the guard keeps exit 1 for a refused reuse.
- III one behaviour one function: `dispatch.delta_due` is the single delta-continue rule;
  the spec location is `specmode._location`; the write is `workspace.atomic_write`.
- IV test first: each change starts with a failing test (the scripted day for the real path).
- V simplicity: the continue actions keep their shape; only the binding and the text change.
- VII security: a reuse binds only the pending continue of its own stopped seat; a replaced
  agent's stop is ignored; the command refuses symlinks and paths outside the worktree.

## Design

### cli/wuwei/dispatch.py

- `delta_due(data, item, role, name)`: the item is in `delta`, `role`'s initial verdict is
  FIX from seat `name` (`gate-<name>.md`), no delta verdict is recorded, and the seat is
  `stopped` with an `agent_id` and a head that starts with the initial verdict's head.
- `_seats` (delta branch) skips a role unless `delta_due`.

### cli/wuwei/guards/agent_launch.py

- In `reserve`: `stopped` = the logged seat exists and is stopped. Builder: `pending` = the
  build is `ready`, action `continue`, `seat` is the brief's name; continuing when pending and
  either no `resume` or `resume` equals the build's `agent_id`. Other roles: with `resume`
  as today; without it, `dispatch.delta_due(data, item, role minus sentinel-, name)`
  (imported lazily, only on this path). `fresh = continuing and not resume` goes to
  `build.started`.

### cli/wuwei/commands/build.py

- `started(data, item, name, fresh=False)`: with `fresh`, `replaced = agent_id` (popped) and
  `completion` popped.
- `stopped`: after validating the payload's agent id, a stop whose id equals `replaced`
  returns handled without recording.

### cli/wuwei/commands/next.py

- `THEN['continue']`: launch a fresh Agent in the background with the prompt unchanged and
  `agent_type` as `subagent_type`; pass `resume` only where the harness offers it; then run
  wuwei next. `resolve` uses it for a build `continue`; `THEN['set']` adds the same clause.

### cli/wuwei/commands/spec.py (new)

- `spec analysis <item> [--file PATH]`: resolve the item (exact, else the one
  case-insensitive match) and its `worktree`; `specmode._location(tree, 'speckit', item)`
  must give one directory inside the worktree, not a symlink, with `spec.md`; the target
  `analysis.md` must not be a symlink; the report (stdin or the file) must not be blank;
  `workspace.atomic_write(target, text, mode=0o644)`; print the path relative to the
  worktree. Any refusal is exit 2.
- `commands.WRITES` gains `spec analysis`; `__main__.GROUPS` lists `spec` under plumbing.

### cli/wuwei/specmode.py

- The speckit `analyze` command: `/speckit.analyze, then save the report with bin/wuwei
  spec analysis {item} < report (a subagent cannot write analysis.md)`.

### Docs and skills

- skills/wuwei-plan and wuwei-report: the `continue` bullet.
- reference.md: the Delta continuation row, a `bin/wuwei spec` command row; daily.md step 4
  and 5; concepts.md Builder steps; configuration.md spec-kit steps; charters/builder.md
  (and the generated agents/builder.md) one line on the analyze report.

## Tests

- `tests/test_build_next.py`: a fresh launch binds a pending builder continue, a stop from
  the replaced id is ignored, the new id is recorded, and a fresh launch after `done` is
  refused; the existing idempotence test moves its "consumed brief" assertion after `done`.
- `tests/test_e2e_day.py` with `tests/fakes/day.py`: the scripted day with fresh Agent
  launches (no `resume`, new agent ids, new transcripts) for the fix round and the delta.
- `tests/test_agent_launch.py`: the existing sentinel test keeps a fresh launch outside the
  delta refused.
- `tests/test_next.py`: a build `continue` row carries `THEN['continue']`.
- `tests/test_spec_mode.py`: the command writes, refuses each case, satisfies the analyze
  step, and a builder seat's Bash call passes the hook.
