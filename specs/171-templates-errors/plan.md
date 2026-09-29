# Implementation Plan: Documented schemas and actionable errors

## Technical Context

Python 3.11+ standard library CLI, existing plan/rank/decision validators, existing adapters, pytest. No new dependencies.

## Constitution Check

Use three-state exits, adapter ports and existing scope helpers. Test first. No commits or external calls in tests.

## Implementation

1. Add CLI skeleton actions and stdin handling using current validators and workspace goals/config.
2. Add one site reference page and link it from the index; keep config defaults documented.
3. Improve messages at the existing source of each refusal. Give tool reads a bounded timeout in their adapters.
4. Run focused tests after each red/green change, then full suite.

## Deferred

None identified at planning time.
