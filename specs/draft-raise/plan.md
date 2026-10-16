# Implementation Plan: a draft PR opens before its gates, and the flip to ready waits for them

**Branch**: `claude/draft-raise` | **Spec**: `specs/draft-raise/spec.md`

## Summary

Let a draft create past the create door, and add a ready door that reads the PR once and reuses
`create_door` on its head when the PR is a draft. Route `gh pr ready`, `gh pr edit
--add-reviewer`, the CCR ready and `requested_reviewers` REST routes, and the MCP update and
Copilot review tools to it.

## Technical Context

Python 3.11 stdlib, pytest. Runtime is 2,962 of 3,000 lines on main 15c74df; the estimate was
+25 and the change is +37 (2,999), after folding the merge and ready REST branches and dropping
short-cluster unpacking.

## Constitution Check

- I. Stdlib only: yes.
- II. Evidence over steps: the ready door reads the same gate evidence as the create door.
- III. An auditor: no new evidence rule; the create door's hold moves from the create to the flip
  to ready, as the owner ruled.
- V. Test first: every new test runs red before the change.
- VI. Budgets: no config key; runtime under the cap.

## Design

- `cli/wuwei/guards.py`
  - `_draft(args)`: reads gh pr create's flags as pflag does (value flags take the next word,
    `=value` with ParseBool's values, last wins) and returns true only for a draft without
    reviewers, `--recover`, an unknown flag, a positional or a short cluster.
  - `_api` also returns whether the body carries a JSON `draft: true`: from the top level of the
    `--input` JSON object when given, else from the last `-F`/`--field` `draft=true`.
  - `API` gains `pulls/<n>/ccr/ready_for_review` and `pulls/<n>/requested_reviewers` (POST) to
    the `ready` door. `MUTATIONS` gains `markPullRequestReadyForReview` and `requestReviews`.
  - `gh_command`: a draft create skips `create_door` but keeps the note once; `gh pr ready`
    without undo and `gh pr edit --add-reviewer` go to `ready_door`.
  - `create_door(..., act)`: the refusal text for a create names `gh pr create --draft`; the ready
    door passes its own text.
  - `ready_door(root, repo, number)`: names the PR or stays shut; reads `gh.pr`; passes a PR that
    is not a draft; else `create_door` on its head, base and body.
  - `DOORS['ready']` and a `pre_tool` branch for `update_pull_request` (draft not true, or
    reviewers) and `request_copilot_review`; MCP `create_pull_request` with `draft` true and no
    reviewers passes.
- Charters `_way.md`, `builder.md`, `shepherd.md`; `bin/wuwei agents build`.
- Docs `docs/design.md`, `docs/site/concepts/doors.md`, and the lines that still said the PR opens
  after the gates: `charters/planner.md`, `charters/_gate.md`, `skills/wuwei/SKILL.md`,
  `skills/wuwei-watch/SKILL.md` and `docs/site/concepts/evidence.md`.
- `tests/fixtures/routes.json`: `gh pr edit 5 --add-reviewer alice` keeps its pass (PR 5 is not
  a draft); new routes with sources.
- Re-vendor `.claude/` with `setup.vendor('.')`.
