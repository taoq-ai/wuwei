# Implementation Plan: an exception: question names its gap after its refs, or it is refused

**Branch**: `fix/exception-shape` | **Spec**: `specs/exception-shape/spec.md`

## Summary

Split the owner-class regex in `guards.pre_tool` so the `exception:` branch requires `: <gap>` after
its last ref, the way `hook.exception_refs` reads it.

## Technical Context

Python 3.11 stdlib. Tests in tests/test_guards.py and tests/test_hook.py. Runtime 2,976 lines at
efcd9e7; this item may add 2.

## Constitution Check

- I. Stdlib only: yes, `re`.
- III. An auditor: no new door; the AskUserQuestion branch refuses more, never less.
- V. Test first: the new tests ran red (7 failed) before the change.
- VI. Budgets: no config key; runtime at 2,977.

## Design

The `exception:` branch becomes, in order:

- `(?i:exception:)` at the start, with no leading whitespace, as the hook's `startswith` reads it;
- `[\s\S]*?` prose before the refs, as before;
- one `owner/repo#n at <sha7>` ref, then any ` and [owner/repo]#m at <sha7>` refs;
- `\s*:\s*`, then a lookahead that no `#n at <sha>` follows, then one character that is not
  whitespace, `.`, `?` or `:`.

`owner review:` and `breaking:` keep `\s*<class>\s*owner/repo#n at <sha7>`. The deny text is
unchanged; it already names the shape.

## Lines

guards.py grows by 1 line: runtime 2,976 to 2,977.
