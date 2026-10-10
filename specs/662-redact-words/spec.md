# Feature Specification: the credential scan matches secrets, not the words for them: bearer token in prose is not a credential

**Feature Branch**: `662-redact-words`
**Created**: 2026-10-10
**Status**: Draft
**Input**: GitHub issue #662: fix(redact): the credential scan matches secrets, not the words
for them: 'bearer token' in prose is not a credential.

Owner, 2026-10-10 (item 19): the redactor refused a docs page because the item's scope text
says "bearer token". Item 48: a second docs page refused on prose mentioning the token; the
docs page scan and the message scan share the fix.

## Root cause

Reproduced in-process with this worktree's `cli/wuwei/redact.py` and
`adapters/redactor/builtin.py` (no dry-run workspace needed: every scan routes through one
pattern string).

- `cli/wuwei/redact.py:60`, the `Bearer`/`Basic` branch of `SECRET`:
  `\b(?:Bearer|Basic)\s{1,40}\S{1,2048}`. Any word after `bearer` or `basic` counts as the
  credential, and `SECRET` is always searched with `re.I`. So
  `redact.redact('the collector masks the bearer token in its logs')` returns `[REDACTED]`
  (the match is `bearer token`), `use a bearer token, not a password` and
  `Basic authentication is off` do the same, and `builtin.redact(...)` reports a `secret`
  finding for each.
- `cli/wuwei/docs.py:177` (`check`) refuses a page when `redact.redact(line) != line` for any
  line, so the scope line `... the bearer token ...` refuses the whole page with
  `docs: the page holds a credential`.
- The same `SECRET` string is the message scan: `adapters/redactor/builtin.py:12` compiles
  `(?:SECRET)\S*` for inbound messages (inbox) and the profile export check, and
  `cli/wuwei/voice.py:26` (`private`), `cli/wuwei/mcp.py:429`, `cli/wuwei/commands/why.py:61`
  and the trace recorder call `redact.redact`. One fix at line 60 fixes every scan.
- `cli/wuwei/redact.py:48` and `:56`, the word list: the `SENSITIVE_FIELD` branch already
  needs `=` or `:` after the word (`(?:SENSITIVE_FIELD)[\w-]{0,40}...\s*[:=]\s*\S`). A bare
  mention does not match today: `the token is rotated weekly`, `the password field is
  masked` and `the secret stays in the env file` all come back unchanged. The issue's word
  list requirement is already met; this feature pins it with tests and does not change line
  48 or 56.

## User Scenarios and Testing

### User Story 1: prose about credentials passes every scan (Priority: P1)

**Independent Test**: `redact.redact`, `builtin.redact` and `docs.check` on sentences that
name a credential kind with prose on both sides.

**Acceptance Scenarios**:

1. **Given** `the collector masks the bearer token in its logs`, **When** it is redacted
   (`redact.redact`), scanned as a message (`builtin.redact`) or checked as a docs page line
   (`docs.check`), **Then** there is no finding: the text comes back unchanged, exit 0 with
   no findings, and no `StateError`.
2. **Given** `use a bearer token, not a password`, `Basic authentication is off`,
   `the token is rotated weekly`, `the password field is masked` and
   `the secret stays in the env file`, **Then** there is no finding in any of the three
   scans.

### User Story 2: real credentials are still redacted (Priority: P1)

**Independent Test**: the same three scans on credential values inside prose.

**Acceptance Scenarios**:

1. **Given** `Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abc`, **Then** it is
   redacted as today: `redact.redact` returns `[REDACTED]`, `builtin.redact` returns exit 1
   with `secret` findings and no part of the value in its text, `docs.check` refuses.
2. **Given** `send Bearer abc123XYZ789def456 with the request` and
   `the header is Basic dXNlcjpwYXNz here`, **Then** each is redacted (Bearer and Basic
   values without an `Authorization:` prefix).
3. **Given** `token = 'abc123XYZ789'` and `set password=hunter2 then restart`, **Then** each
   is redacted.

### Edge Cases

- A `Bearer` or `Basic` value shorter than 8 characters, or made only of letters with no
  digit and no lower-to-upper case change (`Bearer swordfish`), is not a finding by this
  branch. With an `Authorization:` prefix it is still redacted by the word list
  (`authorization` is in `SENSITIVE_FIELD`), as `tests/test_traces.py` already expects.
- A value already replaced by the known-value pass (`Bearer [REDACTED]`) is no longer a
  second finding; the value is already gone.
- Token prefixes (`ghp_`, `sk-`, `glpat-`, JWT `eyJ...`), URL credentials, private key
  headers and phone numbers are unchanged; a `Bearer ghp_...` value is caught both ways.
- The trace recorder's `prefix=True` mode keeps the text before the first finding, as today.

## Requirements

### Functional Requirements

- **FR-001**: the `Bearer`/`Basic` branch of `redact.SECRET` matches only when the value
  after the scheme word looks like a credential: at least 8 characters of the token68 set
  (`[\w.~+/-]`), and at least one digit or one lowercase letter directly followed by an
  uppercase letter, compared case-sensitively although `SECRET` is searched with `re.I`. A
  dictionary word such as `token` or `authentication` fails both tests.
- **FR-002**: the word-list branches of `SECRET` (`redact.py:56-57`) are unchanged: a field
  word matches only when followed by `=` or `:` and a value, or as a `--flag value`; a bare
  mention in prose never matches. Tests pin this.
- **FR-003**: every scan that uses `redact.SECRET` (`redact.redact`, the builtin redactor
  adapter, `docs.check`) gets the behaviour from the one pattern; no caller changes.
- **FR-004**: every existing redaction test passes unchanged (`tests/test_traces.py`,
  `tests/test_inbox.py`, `tests/test_docs_system.py`, `tests/test_env_credentials.py`,
  `tests/test_why.py`, `tests/test_voice.py`).

## Success Criteria

- **SC-001**: the issue's three acceptance scenarios pass as tests for `redact.redact`, the
  builtin redactor and `docs.check` (US1 scenario 1, US2 scenarios 1 and 3).
- **SC-002**: the full suite passes with no existing test edited.

## Assumptions

- No orchestrator notes file exists for #662 (`notes/662-full.md` is absent) and no dry-run
  workspace is named; the reproduction ran in-process against this worktree. The issue text
  is the brief.
- Item 48 ("prose mentioning the token") is the same `bearer token` prose; a bare `token`
  mention already passes today (see Root cause).
- "Not followed by prose" in the issue is met by judging the whole whitespace-delimited value
  after the scheme word: a word of prose fails the credential shape. Text after a real value
  is not inspected, so `Bearer <jwt> and more words` stays redacted (fail safe).
- "No dictionary word" is approximated by the character test in FR-001 (a digit or an
  internal lower-to-upper change); the runtime is stdlib only, with no word list. The known
  ceiling: an all-lowercase, letters-only bearer value such as `Bearer swordfish` without an
  `Authorization:` prefix is no longer caught by this branch, and a camel-case word such as
  `Basic JavaScript` still is. A `ponytail:` comment names it.
- "A quoted string" in the issue's word-list rule is read as the quoted value after `=` or
  `:` (acceptance 3, `token = '...'`), which already matches. A new branch for a field word
  followed directly by a quoted string (`password "x"`) is not added: `SENSITIVE_FIELD` also
  holds `message`, `body` and `text`, so it would add new prose refusals
  (`the message "hello"`), the opposite of this issue.
- `Basic` shares the branch with `Bearer` and gets the same shape test (`Basic
  authentication` is the same false positive).
- The issue's reference `cli/wuwei/commands/docs.py` is `cli/wuwei/docs.py` (`check`);
  neither file changes.
- No guard or decision rule changes, so no design 9.2 row (constitution, Workflow).

## Deferred

- Field words inside longer words still match before `:` or `=`, because the
  `SENSITIVE_FIELD` branch at `cli/wuwei/redact.py:56` has no left boundary:
  `Context: ...` (`text`) and `the author: ...` (`auth`) are refused as credentials. A left
  boundary would drop camel-case keys (`dbPassword=`, `accessToken=`) that the recorder
  relies on, so it needs its own design. To be filed as a follow-up issue linked to #662.
