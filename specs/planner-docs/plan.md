# Implementation Plan: the planner reads tracker measures into the lead's brief

**Branch**: `claude/planner-docs` | **Spec**: `specs/planner-docs/spec.md`

## Summary

Add a step 4 to the plan skill: the planner reads tracker-state measures with its own MCP tools
and puts them, or "unmeasured" with the reason, in the lead's brief. Add the `pytest -q` fallback
to AGENTS.md and CONTRIBUTING.md. Re-vendor `.claude/`. Two docs tests hold the text.

## Technical Context

Markdown and pytest. No runtime code.

## Constitution Check

- I. Stdlib only: no runtime change.
- II. Evidence over steps: the brief carries states as read; an unread measure is unmeasured.
- III. An auditor: no new door, no new tool grant.
- V. Test first: both docs tests ran red before the edits.
- VI. Budgets: no config key; runtime unchanged.

## Design

- `skills/wuwei-plan/SKILL.md`: new step 4 before "Launch the lead"; steps 4 to 8 become 5 to 9.
- `AGENTS.md`, `CONTRIBUTING.md`: one clause each naming `pytest -q` where python3 lacks the module.
- `.claude/skills/wuwei-plan/SKILL.md`: rewritten by `setup.vendor('.')`.
- `tests/test_setup.py`: two docs tests.

## Rollback

Revert the PR. Only docs, the vendored copy and two tests change; nothing reads them at runtime.
