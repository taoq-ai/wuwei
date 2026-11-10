# Implementation Plan: verdict files and the verdict.missing row are masked before they sync

**Branch**: `fix/verdict-mask` | **Spec**: `specs/verdict-mask/spec.md`

## Summary

Mask `guards.SECRETS` and the canary, canary first, in every verdict `_verdict_problem` copies in or
attests, and in the `verdict.missing` row `_seat_stop` records, through the existing `hook.mask`.

## Technical Context

Python 3.11 stdlib. Tests in tests/test_hook.py. Runtime budget 4,000 lines; main (3a1dc3c) is at
3,970 and the item's estimate is +4, budget 6.

## Constitution Check

- I. Stdlib only: yes.
- III. An auditor: no new door; the mask is the one the hook already uses.
- V. Test first: four of the five new tests ran red before the change; the fifth (stray byte) is a
  guard against a lossy decode and passes on main.
- VI. Budgets: no config key; runtime at 3,972.

## Design

- `_verdict_problem` reads the canary once and builds `scrub`, a bytes lambda over `hook.mask` that
  decodes and encodes with `surrogateescape`, so a body with no match keeps its exact bytes.
- The worktree copy-in scrubs the body before the "already holds another verdict" compare and the
  write, so a repeat stop matches its own masked copy.
- After the path check, a body scrub changes is rewritten in place with `ws.atomic_write` rooted at
  the resolved verdicts folder; the sha256 and the parse read the masked body.
- `_seat_stop` masks `problem` with the canary it already read, before the 300-character cut.
- `docs/design.md` and `docs/site/concepts/hooks.md`: the SubagentStop rows name the masking.

## Lines

hook.py 763 to 765: runtime 3,970 to 3,972.
