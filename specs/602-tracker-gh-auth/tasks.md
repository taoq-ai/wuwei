# Tasks: tracker.github through the owner's gh login

Test first: each test task runs and fails for the expected reason before its implementation
task. No test reaches the network or a real `gh`: HTTP is replayed through
`urllib.request.urlopen`, gh through a fake `subprocess.run` on the adapter module. Run only
the touched test files, then the full suite.

## Phase 1: HTTP status (FR-004, US2)

- [X] T001 Test in `tests/test_reference_adapters.py`: an `HTTPError` with 401, 403, 404, 429,
  500 and 418 gives `HTTP <code>: <hint>` (`HTTP 418` alone) in the reason, never the
  credential or the error body.
- [X] T002 Implement `HINTS`, `status` and the `HTTPError` branch in `adapters/_http.py`.

## Phase 2: credential shape (FR-005, US3)

- [X] T003 Test in `tests/test_env_credentials.py`: `env.malformed` table (whitespace,
  newline, `/path`, `~/x`, `./x`, `$(cmd)`, a quote, a clean token, an unset name, a URL
  credential); `config check` with a malformed `GITHUB_TRACKER_TOKEN` prints
  `GITHUB_TRACKER_TOKEN: malformed (contains whitespace)`, exits 1, and the value is in
  neither stream. Test in `tests/test_tracker_adapters.py`: a malformed token gives exit 2,
  `is malformed`, and no request.
- [X] T004 Implement `TOKENS` and `malformed` in `cli/wuwei/env.py`, the check in
  `_http.credential`, and the malformed state in `config check`.

## Phase 3: gh transport (FR-001 to FR-003, US1)

- [X] T005 Test in `tests/test_tracker_adapters.py`: the port contract under `auth = "gh"`
  without a token (gh fake answers the recorded fixture; every argv is
  `gh api graphql --hostname github.com --input -`; no HTTP call); token set with
  `auth = "gh"` uses HTTP; the default without a token names the opt-in and calls nothing;
  gh failures (exit 1 with `(HTTP 401)`, a scope message, `FileNotFoundError`) give the
  reasons of US1.4 without stderr text. Test in `tests/test_workspace.py` or the adapter
  test: `tracker.auth = "other"` is a config error.
- [X] T006 Implement `tracker.auth` in `cli/wuwei/workspace.py`, the template line, and
  `_query`/`_gh` in `adapters/tracker/github.py`.

## Phase 4: config check, doctor, interview (FR-006, US1.5)

- [X] T007 Test in `tests/test_env_credentials.py`: `config check` under `tracker.auth = "gh"`
  prints `tracker.github: gh login (tracker.auth = "gh")` and reports no missing credential.
  Test in `tests/test_doctor.py`: tracker row fix text under both modes.
- [X] T008 Implement `requirements`, the config check line, the doctor fix text and the
  interview text.

## Phase 5: docs (FR-006)

- [X] T009 Test in `tests/test_docs.py`: adapters.md names `tracker.auth`, `gh api graphql`,
  and the seat sentence; configuration.md names `malformed`.
- [X] T010 Update `docs/site/adapters.md` and `docs/site/configuration.md`.

## Phase 6: verify

- [X] T011 Full suite `python -m pytest -q`; adversarial review (correctness, security,
  ponytail).
