# Implementation Plan: a multi-line command that names a door program is refused

**Branch**: `claude/1068-blunt-multiline` | **Spec**: `specs/1068-blunt-multiline/spec.md`

## Summary

A raw-text rule in `guards.bash` before any segment is read, and newline splitting in
`guards.segments` so the other doors read every line.

## Technical Context

Python 3.11 stdlib (`shlex`, `re`). Tests in tests/test_guards.py and tests/test_hook.py. Runtime
budget 3,000 lines, already full: seven lines freed by equivalent refactors.

## Constitution Check

- I. Stdlib only: yes.
- III. An auditor: no new door; an existing door's reading gets stricter on multi-line text.
- V. Test first: the new tests ran red (20 failed) before the change.
- VI. Budgets: no config key; runtime held at 3,000.

## Design

- `DOOR_WORDS`: tuples of regexes, `(\bgit\b, \bpush\b)`, `(\bgh\b, \b(pr|api|repo)\b)`,
  `(\bwuwei["']?(\s|\\\n)+["']?hook\b,)` and `(\.wuwei/ledger,)`; a tuple matches when every regex is found
  anywhere in the raw text.
- `bash`: `parts = segments(command)`; when `parts is None` or the text holds `\r` or `\n`, and the
  text names a door program, return the deny with the hint. Otherwise loop over `parts or ()`.
- `segments`: before lexing, one `re.sub` skips single-quoted strings, double-quoted strings and
  backslash pairs, drops an unquoted backslash-newline and turns every other newline into ` ; `.
  The lexer and the separator set are as on main; `ValueError` returns `None`.
- `_unwrap` and `hook.post_tool` read `segments(...) or []`.

## Lines freed

hook.py: a stray blank line, the `path` local in `last_text`, the `attest` record dict on four
lines instead of six. guards.py: `deleting` as one expression in `git_push`, the `verb` local
inlined, the `name` local in `once` inlined. Each is behaviour-preserving and covered by existing
tests.

## Rollback

Revert the PR. No state, config, cache or ledger format changes.
