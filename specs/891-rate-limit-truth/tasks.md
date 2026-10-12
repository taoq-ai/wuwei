# Tasks: a rate limit refusal names the bucket only when gh api rate_limit confirms it

**Input**: [spec.md](spec.md), [plan.md](plan.md)

## Phase 1: tests first (red)

- [x] T001 [US1] `tests/test_code_host.py`: `test_a_full_bucket_names_both_readings`
  (FR-001, FR-002, FR-003, SC-001); run it, see the extra `--include` call.
- [x] T002 [US1] `tests/test_code_host.py`: `test_included_headers_are_named_never_trusted`
  (primary wording and Retry-After; FR-001, FR-002); run it, see `(0 of 5000 core calls left)`
  until the header reset.
- [x] T003 [US1] `tests/test_code_host.py`: `test_a_search_limit_never_names_its_query`,
  `test_an_empty_bucket_names_rate_limits_reset`, the secondary wording in the existing cases.
- [x] T004 [US1] `tests/test_pr_actions.py`: `test_pr_act_on_a_full_bucket_names_both_readings`
  (SC-001); run it, see the re-ask.

## Phase 2: implementation (green)

- [x] T005 `gh_limit` takes `where`, `after` and `seen`; `RateLimited` takes a `note` (FR-002, FR-002a).
- [x] T006 `_run` raises `gh_limit` only; `_headers_limit` and `included_limit` deleted
  (FR-001, FR-003).

## Phase 3: verification

- [x] T007 Full suite on 3.12; code host, adapters, pr actions, tracker, doctor and reference
  adapter tests on 3.11 (FR-004, FR-005).
