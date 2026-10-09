# Tasks: loop robustness

Test first: each test task runs and fails for the expected reason before its implementation
task. No test reaches the network or a real `gh`: HTTP is replayed through
`urllib.request.urlopen`, gh through a fake `subprocess.run`, adapters through a fake
`registry.load`. Run only the touched test files, then the full suite.

## Phase 1: balanced queries (FR-001, US1.1)

- [X] T001 Test in `tests/test_tracker_adapters.py`: a brace and parenthesis checker over every
  recorded query of the GitHub and Linear port contracts and of the gh port contract; it fails
  on `github.created`.
- [X] T002 Fix the `created` query in `adapters/tracker/github.py`.

## Phase 2: name the failing lookup (FR-002, US1.2)

- [X] T003 Test in `tests/test_tracker_adapters.py`: a token-path errors response for
  `acme/app#9` gives `GitHub error response for acme/app#9: <message>` on one line, capped;
  the gh case with stdout errors names the ticket and message and no stderr text.
- [X] T004 Implement `_error` in `adapters/tracker/github.py`, its use in `_query` and `_gh`, and
  the `Failure` docstring in `adapters/_http.py`.

## Phase 3: one failing lookup does not block the loop (FR-003, FR-004, US1.3, US1.4)

- [X] T005 Test in `tests/test_outcome_metrics.py`: two tickets, `created` fails for one: the
  other measures and `unmeasured` names the failing ticket with its reason; both fail:
  `unmeasured`; a malformed `created` timestamp still fails collect.
- [X] T006 Implement `_Unavailable` and the per-ticket catch in `cli/wuwei/metrics.py`.
- [X] T007 Test in `tests/test_steward.py`: `steward.review` with `metrics.collect` and
  `registry.load` raising still records `<item>-fix-3`.
- [X] T008 Implement `metrics.fix_rounds` and its use in `collect` and `steward.review`.

## Phase 4: one fresh steward (FR-005, US2)

- [X] T009 Test in `tests/test_next.py`: two unlaunched runs offer the newest brief; a running
  steward seat gives no steward row for due or for an unlaunched brief; after it stops the due
  row returns.
- [X] T010 Implement the steward rows in `cli/wuwei/commands/next.py`.

## Phase 5: docs (FR-006)

- [X] T011 Test in `tests/test_docs.py`: configuration.md names the newest steward brief rule.
- [X] T012 Update `docs/site/configuration.md`, `docs/site/reference.md` and
  `docs/site/adapters.md`.

## Phase 6: verify

- [X] T013 Full suite; adversarial review (correctness, security, ponytail).
