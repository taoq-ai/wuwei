# Implementation Plan: plan accuracy

**Branch**: `claude/plan-accuracy` | **Spec**: `specs/plan-accuracy/spec.md`

## Summary

Validate the candidates file before adding, clear approval on a changed contract, require a reason
for `plan run`, and print the plan actions one per line.

## Technical Context

Python 3.11 stdlib, pytest. Runtime at 2,939 of 3,000 lines on main 1620583.

## Constitution Check

- I. Stdlib only: yes.
- II. Evidence over steps: `plan run` evidence must say what ran and what it showed.
- III. An auditor: no new door; the plan record only refuses bad input.
- V. Test first: the four new tests ran red (9 failed) before the change.
- VI. Budgets: runtime 2,939 to 2,947; no config key.

## Design

- `plan.add_from`: take `data["candidates"]` from a dict or `data` itself; if that is not a list of
  objects each with `id` and `title`, raise `ValueError` naming the shape and "nothing added".
- `plan.add`, update branch: before the update, if a given promise or acceptance differs from the
  stored one, set `approved` False. `board.compute` already shows "awaiting plan approval" for an
  open item that is not approved.
- `__main__.cmd_plan`: `run` without `--reason` raises `ValueError`; `main` prints it, exit 2.
- `__main__.main`: one `actions` table gives the subparser's choices, its one-line help and an
  `actions:` description printed with `RawDescriptionHelpFormatter`. The add branch reads the
  score names from `plan.FIELDS` instead of repeating them, freeing two lines.
- `.claude/`: rewritten by `setup.vendor('.')`.

## Rollback

Revert the commit; the plan file format is unchanged.
