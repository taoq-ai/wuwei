# Implementation Plan: PR Auto Claim

**Issue**: #954 | **Date**: 2026-10-13 | **Spec**: [spec.md](spec.md)

## Summary

Keep the existing PR pretool guard. Read the successful Bash result in the PostToolUse trace recorder, require unambiguous command and URL evidence, and use the shared PR writer only after local gate verification. Record unsafe or unmatched configured PRs as unclaimed. Refresh the existing PR listing in `next` before offering a claim.

## Constitution Check

- Runtime stays stdlib-only; no new module or GitHub call in the hook.
- Tests reproduce the planner field case and unsafe item path before each fix.
- PostToolUse errors fail open; a timeout uses the trace slow event.
- The owner-only design file stays unchanged.

## Source Changes

- `cli/wuwei/guards/edges.py`: restore the item PR refusal; prefer approved items in local branch matching.
- `cli/wuwei/guards/traces.py`: parse one create and URL, validate configured repository and gates, record a local branch or an unclaimed event, and name gates before claiming an existing PR.
- `cli/wuwei/commands/next.py`: refresh pending PR listings at event and poll boundaries, rank recovery first, preserve the matched item in the claim offer, and dismiss an attempted claim.
- Existing edge, trace, next and signal tests cover the field case, safety boundaries and fail-open paths.
