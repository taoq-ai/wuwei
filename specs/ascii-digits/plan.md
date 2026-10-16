# Implementation Plan: PR numbers are ASCII digits only

**Branch**: `claude/ascii-digits` | **Spec**: `specs/ascii-digits/spec.md`

## Summary

Replace every `\d` under `cli/wuwei` with `[0-9]`, guard `__main__._ref`'s `isdigit()` with
`isascii()`, and read the owner review and breaking rulings in `hook._answers` from one `REF`
search. A setup test scans the runtime for both patterns.

## Technical Context

Python 3.11 stdlib, pytest. Runtime 2,986 lines at 0104d00; the item commit brings it to 2,982
(minus 4: the two ruling readers, eight lines, become four). After merging #1106 (2,992 on main
23625f3) the head is 2,988; anchoring the REF after the security gate costs no line.

## Constitution Check

- I. Stdlib only: yes.
- II. Evidence over steps: no rule changes; readers only narrow what counts as a number.
- V. Test first: seven new cases ran red at 0104d00 before any runtime edit.
- VI. Budgets: no config key; the runtime shrinks.

## Design

- `cli/wuwei/evidence.py`, `guards.py`, `upgrade.py`, `verdict.py`, `hook.py`: `\d` to `[0-9]`.
  No `re.ASCII`, so `\w` in repository names reads as before.
- `cli/wuwei/__main__.py` `_ref`: `number.isascii() and number.isdigit()`.
- `cli/wuwei/hook.py` `_answers`: one `re.match` of `\s*(?i:owner review|(breaking)):\s*` and
  `REF.pattern`; with a repository it records the ruling, with `kind: breaking` only for breaking.
- `cli/wuwei/guards.py` `pre_tool`: the shape rule matches the REF right after `owner review:` or
  `breaking:` (and anywhere after `exception:`, as before), with the same `\b` after the sha as
  `hook.REF`. Same line count.
- `tests/test_setup.py`: a scan of every runtime line for `\d` and for `\b\w+\.isdigit\(` not
  preceded by `.isascii() and `.
- Re-vendor `.claude/` with `setup.vendor('.')`.
