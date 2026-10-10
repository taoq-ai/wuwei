# Tasks: the credential scan matches secrets, not the words for them: bearer token in prose is not a credential

Test first: each test task runs and fails (or, for a pinning test, passes) for the stated
reason before its implementation task. Run only the touched test files while building; the
full suite at the end.

## Phase 1: prose passes, credentials stay redacted (US1, US2, FR-001, FR-002)

- [X] T001 Test in `tests/test_traces.py`: new `test_prose_names_credentials_without_holding_one`
  (#662) next to `test_redaction_corpus`, with the clean and dirty lists from `plan.md`,
  Tests. Clean: `redact(text) == text` and `redact(text, prefix=True) == text`. Dirty:
  `redact(text) == '[REDACTED]'`. Run: fails on `the collector masks the bearer token in its
  logs`, `use a bearer token, not a password` and `Basic authentication is off` (line 60
  matches the word after the scheme); the bare-word and dirty cases already pass.
- [X] T002 Test in `tests/test_inbox.py` (the message scan): add the rows from `plan.md`,
  Tests, to the `test_builtin_redactor` parametrize. Run: the two prose rows fail (a
  `secret` finding); the credential rows pass.
- [X] T003 Test in `tests/test_docs_system.py` (the docs page scan): new
  `test_check_accepts_prose_about_credentials` (#662) and the two added rows of
  `test_check_refuses_raw_records_paths_and_credentials`, as in `plan.md`, Tests. Run: the
  new test fails with `docs: the page holds a credential`; the refusal rows pass.
- [X] T004 Implement in `cli/wuwei/redact.py`: replace the `Bearer`/`Basic` branch of
  `SECRET` (line 60) with the credential-shaped value from `plan.md`, Changes 1, with its
  `#662` and `ponytail:` comment; split the `://` branch onto its own line. No other file
  changes. Run T001, T002, T003: green.

## Phase 2: close

- [X] T005 Run `tests/test_traces.py`, `tests/test_inbox.py`, `tests/test_docs_system.py`,
  `tests/test_env_credentials.py`, `tests/test_why.py`, `tests/test_voice.py`,
  `tests/test_profiles.py`, `tests/test_mcp.py`: green with no existing test edited (FR-004).
- [X] T006 Full suite left to CI (owner rule, 2026-10-10). Check
  the changed files for em-dashes, emojis and absolute local paths; remove any.
