# Implementation Plan: Profiles

**Branch**: `017-profiles` | **Date**: 2026-09-28 | **Spec**: [spec.md](spec.md)

## Summary

Extend Guard with a default-false profile_relaxable flag. The dispatcher alone translates
relaxable findings to warnings using the workspace config, and only after a finding exists.
Outward approval tiers and text lint become separate registered checks. Existing direct
outward callers retain check_call, composing the tier check with the lint check and reusing
the dispatcher's profile helper. This keeps the profile conditional in one place.

## Technical Context

Python 3.11+, stdlib runtime, pytest development only. Existing filesystem config and
refusal events are reused; no new persistent state. In-process hook tables and fake ports
cover the behavior. Preserve existing latency budgets and run the full suite using the
interpreter supplied with the task.

## Constitution Check

Before and after design: pass. No runtime dependencies, new subprocess boundary, trust
record, parser, scope helper or speculative layer. Errors remain exit 2. Tests precede
implementation. Existing outbound classification still owns approval-tier decisions.

## Design Decisions

- Add a bool field with a default so existing three-argument Guard records work unchanged.
- Validate the metadata during discovery; malformed metadata fails closed.
- Only the registered outward lint check opts in. Non-lint guards stay unchanged.
- Read profile through guard_scope and load_config only for relaxable exit-1 findings.
  Never parse Bash text or load profile globally for unrelated calls.
- Split shared outward checking into tier and lint functions. Retain check_call for direct
  callers and apply the same dispatcher helper there after the tier check passes.
- Keep warnings redacted and visible on stderr; continue running every matched guard.

## Project Structure

Changes: cli/wuwei/commands/hook.py, cli/wuwei/guards/__init__.py,
cli/wuwei/guards/outward.py, cli/wuwei/outward.py, tests/test_profiles.py,
specs/006-hooks-harness/contracts/hooks.md.
Feature documents: spec.md, plan.md, tasks.md and checklists/requirements.md.
Existing tests/test_outward.py, tests/test_outbound.py and tests/fakes cover shared behavior.
No separate research or data-model artifact is needed: no unknown dependency or new storage.

## Validation

Test metadata discovery and the profile/result matrix first, observing expected failures.
Then test actual outward hooks, direct ports, merge/approve/deploy commands and scope.
Run the full suite and inspect the diff for hygiene and unintended changes.

## Deferred

The existing merge policy stub refuses merges. Its replacement remains issue #77.
