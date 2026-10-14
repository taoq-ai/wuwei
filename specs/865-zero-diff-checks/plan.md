# Implementation Plan: Skip fast checks for an empty item diff

**Branch**: `865-zero-diff-checks` | **Date**: 2026-10-14 | **Spec**: `spec.md`

## Summary

At `build check`, use the existing item diff reader and worktree status helper before invoking configured fast checks. For an empty diff and clean status, skip checks for that invocation and write `not applicable: no diff` into the build result and event. Keep configured commands on the build record so a later changed round still runs them. For a changed item, retain the existing runner. An unmeasured diff exits 2 with its reason.

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: Python standard library; pytest for tests  
**Storage**: Existing workspace state and event log  
**Testing**: Explicit pytest files with the pipeline interpreter  
**Target Platform**: WUWEI CLI on local worktrees  
**Project Type**: CLI bug fix  
**Constraints**: No edit to `_unbuilt`, no runtime dependency, no real check tool in tests  
**Scale/Scope**: One check path and its regression fixtures

## Constitution Check

- I: Runtime remains stdlib only; diff, status and checks go through existing ports.
- II: Unavailable or invalid diff/status returns exit 2 with a reason.
- III: The build check path owns the skip decision and uses the existing atomic state/event writer.
- IV: Add failing tests and observe expected failures before changing runtime code.
- V: Reuse `dispatch._changes` and `brief.status`; add no new adapter or configuration.
- VII: The existing no-change build rule and guard trust boundaries remain intact.

## Design

1. In `check`, determine whether the configured list is nonempty and the item's committed diff and dirty status are both empty. Pass the item's kind and build start to `dispatch._changes`, so a measurement uses its start instead of the origin merge base. The existing `brief.status` reader supplies dirty status. Reject an invalid diff shape.
2. When empty, bypass `fast_checks.record` for this invocation while keeping the configured commands on the build record. Pass the skip decision to completion and measured-head handling. Attach the skip reason to the completed build result and `build.checked` event; clear it before a retry. Existing completion and no-change logic still runs.
3. When changed or dirty, run configured checks unchanged. A failed read leaves no clean result.
4. Use a fake VCS and check port to prove no linter invocation on a clean empty diff, normal invocation with a changed or dirty worktree, and exit 2 on an unmeasured diff. Cover skip, continue, changed stop, then check, plus a measurement branch ahead of origin. Update existing fake VCS fixtures to return a nonempty diff where they exercise a normal build.

## Project Structure

```text
specs/865-zero-diff-checks/
  spec.md
  plan.md
  tasks.md
  analysis.md
  checklists/
cli/wuwei/commands/build.py
tests/test_fast_checks.py
tests/test_build.py
tests/test_build_next.py
```

## Verification

Run only test files importing `wuwei.commands.build` with explicit file arguments and the issue's pipeline interpreter. Inspect the diff for scope, forbidden characters, and absolute local paths.
