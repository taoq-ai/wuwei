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
- A nested `segments` returning `None` raises `ValueError`; `segments` now runs its split loop
  inside the `try`, so the outer call returns `None`.

## Lines

Added: `READ` (1), the body-index line (1), the nested `None` check (2). Freed: the flag-skip loop
(2, replaced by the first-program line), `tokens = list(lexer)` (1), the redirect loop as three
lines instead of six (3). Net 0.

## Rollback

Revert the PR. No state, config, cache or ledger format changes.
