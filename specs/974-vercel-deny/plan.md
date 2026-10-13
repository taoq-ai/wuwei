# Implementation Plan: Narrow Vercel host permissions

**Branch**: `974-vercel-deny` | **Date**: 2026-10-13 | **Spec**: [spec.md](spec.md)

## Summary

Change the shared `PERMISSIONS_DENY` list in `cli/wuwei/guards/edges.py` and migrate old entries through `cli/wuwei/commands/init.py`. Use the existing settings reader and atomic writer. No new runtime module or dependency.

## Technical Context and Constitution Check

Python 3.11+ stdlib runtime. `init` owns workspace settings writes. TDD is required. Upgrade and dry run must retain their current exit and write behavior. The owner-only design file stays untouched. The issue's explicit test-file command takes precedence over the constitution's full-suite instruction.

## Root Cause

`edges.py` `PERMISSIONS_DENY` contains broad Vercel rules, which the host applies before the #947 guard. `init.py` `upgrade()` never revisits `.claude/settings.json`, so existing workspaces keep the legacy rules.

## Implementation

1. Extend `tests/test_edges.py` with exact new-install permissions, pre-existing legacy settings and an upgrade field case preserving unrelated settings, dry-run and idempotence. Run them red.
2. Replace the two broad patterns with the enumerated narrow patterns at the shared deny constant.
3. Have `upgrade()` read local settings with `settings()`, replace only legacy Vercel deny entries, write atomically when changed, and report the change. Keep dry-run read-only.
4. Run the #947 guard tests and every test file importing either changed module. Review correctness, security and complexity.

## Validation

Use the task-specified interpreter with `-m pytest -q -p no:cacheprovider` and explicit paths. Test fixtures must not touch the network or real GitHub.
