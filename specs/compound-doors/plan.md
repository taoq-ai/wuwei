# Implementation Plan: the doors read a command inside a loop or if body, after shell flags, and after a wrapper's options

**Branch**: `claude/compound-doors` | **Spec**: `specs/compound-doors/spec.md`

## Summary

Three readings in `guards._unwrap`: reserved words that open a body are dropped, a shell with
combined flags before `-c` is unwrapped, and after a wrapper the command starts at the first
program a door reads. An unreadable `sh -c` body now reaches the raw-text rule of #1077.

## Technical Context

Python 3.11 stdlib (`shlex`, `re`). Tests in tests/test_guards.py. Runtime budget 3,000 lines:
main has 3,000 since #1081, so this change is net zero lines in `cli/wuwei/`.

## Constitution Check

- I. Stdlib only: yes.
- III. An auditor: no new door; existing doors read more shapes.
- V. Test first: the new tests ran red (23 failed, 143 passed) before the change.
- VI. Budgets: no config key; `cli/wuwei/` net 0 lines (3,000 before and after).

## Design

- `WRAPPERS` adds `timeout` and `stdbuf`. A new `READ` set names the programs a door reads.
- `_unwrap`: the leading-word loop matches `VAR=value` or a reserved word in one regex. If the first
  word is then a wrapper, the command starts at the first word in `READ` or starting with `python`.
- The shell check finds the first plain word after the program; when a dash option before it is a
  single-dash cluster holding `c`, that word is the body.
- A nested `segments` returning `None` gives the marker segment `UNREAD` in its place; `bash`
  applies the raw-text rule when `UNREAD` is in the segments and reads the rest as before.
  `segments` runs its split loop inside the `try` (one line freed).

## Lines

Added: `READ` (1), `UNREAD` (1), the body-index line (1), the nested body as two lines instead of
one (1). Freed: `tokens = list(lexer)` (1), the redirect loop as three lines instead of six (3).
The flag-skip loop and the first-program rule are four lines each. Net 0.

## Rollback

Revert the PR. No state, config, cache or ledger format changes.
