# Implementation plan: WUWEI morning plan

## Technical context

Python 3.11 standard library. Reuse `workspace.day_dir`, `workspace.atomic_write`, `state._write_state`, `state.read_state`, and command registration. pytest uses an in-process core path plus one CLI smoke path.

## Constitution check

The CLI remains the only state writer. Proposal is atomic; approval uses the locked state writer. Both commands return 0, 1 or 2 and print errors. No core subprocess imports or new runtime dependency. Test first.

## Design

Add `cli/wuwei/plan.py` for proposal validation, markdown rendering, approval and optional carry-over. Add `cli/wuwei/commands/plan.py` as argument and exit adapter. A JSON proposal is stored beside `plan.md` so approval can validate selected IDs and preserve lead details. Proposal input includes goals, candidates, source sweep, seat policy, CAP and envelope. Approval takes selected IDs and explicit `--goals-confirmed`; `--import-yesterday` imports unfinished items only when chosen, while recording `state.import`. Reserve the gate fields in the shared state writer, including nested item IDs through the top-level `items` namespace. Update existing state tests that exercised generic writes into newly reserved fields.

Add `skills/wuwei-plan/SKILL.md` to orchestrate measured inputs, lead discovery and one-question-per-decision gate, citing `days/<date>/plan.md`. No worktree action in this skill or either command. Reuse the existing morning question guard.

## Test strategy

Test proposal output and no state or worktree, approval selection and protected fields, explicit import and event, invalid input exits, and a CLI smoke invocation through `bin/wuwei` or `python -P -m wuwei`. Run the full suite with the issue interpreter.
