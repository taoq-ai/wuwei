# Implementation Plan: breaking: classification

**Branch**: `fix/1294-breaking-classification` | **Spec**: `specs/1294-breaking-classification/spec.md`

## Technical Context

Python 3.11 stdlib. Tests in tests/test_breaking.py and tests/test_hook.py. Runtime cap 4,000
lines; the item budgets +6.

## Constitution Check

- Stdlib only: yes. No new door, no config key.
- Test first: the new tests run red before the change.
- Owner paths: hook.py, evidence.py, guards.py; owner review at merge.

## Design

- `cli/wuwei/hook.py` `_answers`: for a `breaking:` question without "Announced at", record
  `breaking: yes` and `approved: False`.
- `cli/wuwei/evidence.py` `breaking_gaps`: collect the breaking rulings at this PR and head. The
  latest one with a `breaking` field overrides the arch verdict unless the PR declares the break.
  The confirmation clears only on an approved row without a `breaking` field.
- `cli/wuwei/guards.py`: the AskUserQuestion refusal names the classification shape.
- `charters/shepherd.md`: ask the classification first, the Proceed once announced; then
  `bin/wuwei agents build`. `docs/design.md` and the docs site name both shapes.
- Re-vendor `.claude/wuwei/` with `setup.vendor('.')`.
- Route corpus differential main vs head (guards.py text changes only in a refusal reason).
