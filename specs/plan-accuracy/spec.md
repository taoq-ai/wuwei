# Feature Specification: the plan record refuses a wrong-shape file and a bare run, and a changed promise needs approval again

**Feature branch**: `claude/plan-accuracy`
**Item**: plan-accuracy, tier standard, goal G-2, covers #1073
**Input**: `plan add --from` silently added nothing from a file shaped `{"items": [...]}`. Re-adding
the approved item 1068 with a new promise kept its approval. `plan run <id>` recorded an empty
reason as run evidence.

## The promise in my words

Four fixes to the plan record, in `cli/wuwei/plan.py` and `cli/wuwei/__main__.py`:

1. `plan add --from <file>` accepts only a JSON list or `{"candidates": [...]}` whose every entry
   is an object with an `id` and a `title`. Anything else exits non-zero with a message naming the
   expected shape, and no item is added (the check runs before the first add).
2. Re-adding an item already in the plan with a promise or acceptance that differs from the stored
   one clears its approval. The board then shows "awaiting plan approval" for it. Re-adding with
   the same promise and acceptance (or none given) keeps the approval.
3. `wuwei plan run <id>` without `--reason` refuses and records nothing. With `--reason`, the item
   carries that reason as its run evidence.
4. `wuwei plan --help` lists each action on its own line.

Outside: retracting a run record (`plan restore` reopens the item).

## Acceptance scenarios

1. Given a candidates file `{"items": [...]}`, when `plan add --from` reads it, then it exits
   non-zero naming the expected shape and adds nothing.
2. Given approved item A re-added with a different promise, when the add completes, then A is not
   approved and the board shows "awaiting plan approval"; re-added with the same promise and
   acceptance, it stays approved.
3. Given `wuwei plan run A` without `--reason`, when it runs, then it refuses and records nothing;
   with `--reason "ran X, it showed Y"`, the item carries that reason.
4. Given `wuwei plan --help`, when it prints, then each action has its own line.

## Functional requirements

- FR-001: `add_from` validates the whole file before adding; a wrong shape raises `ValueError`
  naming `{"candidates": [{"id", "title", ...}]}`, which the command line prints with exit 2.
- FR-002: `add` sets `approved` to False on an existing item when a non-empty promise or
  acceptance differs from the stored value.
- FR-003: `cmd_plan` refuses `run` without `--reason` before calling `plan.mark`.
- FR-004: the plan subparser prints an `actions:` block, one line per action, from the same table
  that gives the argument choices.
- FR-005: `docs/site/reference.md` names the shape, the approval rule and `plan run`.

## Assumptions

- An empty list or `{"candidates": []}` is the expected shape with no candidates and adds nothing
  without an error. Overturned if the owner wants an empty file refused.
- An empty promise or acceptance on re-add means "unchanged", as the existing update already keeps
  the stored value. Overturned if a re-add should be able to blank the promise.
- A promise set for the first time on an approved item counts as a change and clears approval.
- The runtime grows by 8 lines against the estimate of 6; the help table is the difference.
