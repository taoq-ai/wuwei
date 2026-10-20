# Implementation Plan: the board shows a registered Codex job's state

**Spec**: `specs/codex-job-state/spec.md` | **Item**: 1201 | **Tier**: standard

## Technical context

Stdlib Python 3.11+, runtime budget 6 lines (main at 3,351; the cap of 3,400 is shared by five PRs
today). Items 1200 and 1202 also edit `board.py`, so the change stays local.

## Design

1. `__main__.py`: `plan run` takes `--job <path>`; `--reason` or `--job` is required. The path is
   stored on the item as `job` through the existing `plan.mark(..., **fields)`; a run without
   `--job` leaves an earlier job in place.
2. `board.py`: `job(root, path)` reads the one registered file through `ws.read_json` (moved from
   `upgrade._json`, and catching RecursionError for deeply nested JSON), and returns `job <state>[, handoff <path>]`. The run row joins the reason and the
   job state.
3. Vendored copies under `.claude/wuwei/` take the same files; `charters/planner.md` tells the
   planner to register the job; `docs/design.md` and `docs/site/reference.md` describe it.

## Constitution check

Stdlib only, test first, no new module or dependency, no scan of another plugin's folders.
