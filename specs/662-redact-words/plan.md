# Implementation Plan: the credential scan matches secrets, not the words for them: bearer token in prose is not a credential

**Branch**: `662-redact-words` | **Date**: 2026-10-10 | **Spec**: `spec.md`

## Summary

Change one branch of the one shared credential pattern, `redact.SECRET`: the `Bearer`/`Basic`
value must look like a credential. Every scan (`redact.redact`, the builtin redactor adapter,
`docs.check`) routes through that string, so no caller changes. The word list already needs
`=` or `:`; tests pin it. Root cause with file and line: `spec.md`, Root cause.

## Technical Context

Stdlib-only Python 3.11+ runtime (`re` scoped inline flags `(?-i:...)` are 3.6+); pytest
dev-only. All tests are in-process; no workspace fixture is needed for `redact.redact` or
`builtin.redact`; `docs.check` takes text and raises `state.StateError`.

## Constitution Check

- Test first per behaviour. Pass.
- Stdlib only. Pass.
- Exits unchanged: the builtin redactor still returns 0 clean, 1 findings, 2 on non-string.
  Pass.
- Security (VII): only the `Bearer`/`Basic` branch narrows; token prefixes, JWTs, URL
  credentials, private keys, phones and the word list are unchanged. The narrowing has a
  known ceiling, named in a `ponytail:` comment. Pass.
- No guard or decision rule changes: no design 9.2 row. Pass.
- Ponytail: one pattern line, no new function, module, constant or caller change. Pass.

## Changes

### 1. The Bearer/Basic branch (FR-001)

`cli/wuwei/redact.py`, `SECRET`, line 60. Replace

```python
    r'\b(?:Bearer|Basic)\s{1,40}\S{1,2048}|[a-z][a-z0-9+.-]{0,30}://[^/\s]{0,2048}@|'
```

with

```python
    # #662: a scheme word is a credential only with a credential-shaped value: 8 or more
    # token68 characters holding a digit or a lower-to-upper change (case-sensitive under
    # re.I). ponytail: no word list, so `Bearer swordfish` is missed and `Basic JavaScript`
    # is still caught; a dictionary check if either matters.
    r'\b(?:Bearer|Basic)\s{1,40}(?=[\w.~+/-]{8})'
    r'(?=[\w.~+/-]{0,2048}?(?-i:\d|[a-z][A-Z]))[\w.~+/-]{1,2048}|'
    r'[a-z][a-z0-9+.-]{0,30}://[^/\s]{0,2048}@|'
```

The comment goes above the line inside the parenthesised `SECRET` string (comments between
implicitly concatenated literals are valid). Keep it short; the wording above is a guide.

Verified before writing this plan: with this branch, in a scratch copy of the worktree,
`tests/test_traces.py`, `tests/test_inbox.py`, `tests/test_docs_system.py`,
`tests/test_env_credentials.py`, `tests/test_why.py`, `tests/test_voice.py`,
`tests/test_profiles.py` and `tests/test_mcp.py` pass unchanged (665 passed), and every
spec scenario gives the expected result in all three scans.

### 2. Nothing else

- `SENSITIVE_FIELD` (line 47-49) and the word-list branches (lines 56-57): unchanged (FR-002).
- `adapters/redactor/builtin.py`: unchanged; it compiles `(?:SECRET)\S*` and picks the change
  up. Its `ponytail:` comment about field words stays true.
- `cli/wuwei/docs.py` (`check`), `cli/wuwei/voice.py`, `cli/wuwei/mcp.py`,
  `cli/wuwei/commands/why.py`, `cli/wuwei/guards/traces.py`: unchanged (FR-003).
- No docs page change: no user-facing doc describes the Bearer pattern.

## Tests

One test per scan, each with prose on both sides, all in existing test files:

- `tests/test_traces.py`, next to `test_redaction_corpus`: new
  `test_prose_names_credentials_without_holding_one` (#662). Clean list: the five US1 texts
  plus `the collector masks the bearer token in its logs`; each satisfies
  `redact(text) == text` and `redact(text, prefix=True) == text`. Dirty list: the US2 texts
  (`Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abc`,
  `send Bearer abc123XYZ789def456 with the request`,
  `the header is Basic dXNlcjpwYXNz here`, `token = 'abc123XYZ789'`,
  `set password=hunter2 then restart`); each satisfies `redact(text) == '[REDACTED]'`.
- `tests/test_inbox.py`, rows added to the `test_builtin_redactor` parametrize (the message
  scan): `('the collector masks the bearer token in its logs', <same>, [])`,
  `('use a bearer token, not a password', <same>, [])`,
  `('send Bearer abc123XYZ789def456 with the request', 'send [REDACTED] with the request', ['secret'])`,
  `('the header is Basic dXNlcjpwYXNz here', 'the header is [REDACTED] here', ['secret'])`,
  `("token = 'abc123XYZ789'", '[REDACTED]', ['secret'])`. The `Authorization: Bearer <jwt>`
  case yields two `secret` findings (`[REDACTED] [REDACTED]`); add it as
  `('Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abc', '[REDACTED] [REDACTED]', ['secret', 'secret'])`.
- `tests/test_docs_system.py`: new `test_check_accepts_prose_about_credentials` (#662):
  `docs.check('### What changed\nthe collector masks the bearer token in its logs\n'
  'Basic authentication is off and the token is rotated weekly.')` raises nothing; and
  extend the `test_check_refuses_raw_records_paths_and_credentials` parametrize with
  `'Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abc'` and
  `"token = 'abc123XYZ789'"` (both already refused: they pin acceptance 2 and 3 for the
  docs scan).

The clean texts fail before the change (red): `bearer token`, `bearer token,` and
`Basic authentication` are matched by line 60. The bare `token`/`password`/`secret` texts and
the dirty texts pass before and after; they pin FR-002 and the acceptance "redacted as today".

## What must not change

- Every existing test in the files above passes unedited (FR-004, SC-002).
- `redact.redact` still returns the whole string as `[REDACTED]` outside `prefix=True`.
- The builtin redactor's result shape and exit codes.
