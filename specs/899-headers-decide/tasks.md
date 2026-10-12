# Tasks: a refusal's own rate-limit headers decide the bucket

**Input**: [spec.md](spec.md), [plan.md](plan.md)

## Phase 1: tests first (red)

- [x] T001 [US1] `tests/test_code_host.py`: `test_the_refused_replys_headers_decide` (the field
  case: headers core 0 until 12:55:46, rate_limit 5000, one call; FR-001, FR-002, SC-001).
- [x] T002 [US1] `tests/test_code_host.py`: `test_included_headers_decide` over a plain and a
  conditional read: secondary wording, Retry-After, remaining 0 beating secondary, primary
  wording with calls left (FR-002, FR-004).
- [x] T003 [US1] `tests/test_code_host.py`: `test_no_headers_and_a_full_bucket_name_the_disagreement`
  and the write case asserting no `--include` and a rate_limit read (FR-003, FR-004).
- [x] T004 [US1] `tests/test_code_host.py`: `test_read_recording_with_its_head` for every
  single-page read; paged and 304 reads keep their existing tests (FR-001).
- [x] T005 [US1] `tests/test_pr_actions.py`: `test_pr_act_names_the_refused_replys_bucket`
  (SC-001 through `pr act`).
- [x] T006 Read argv in recordings, merge ports and env credential tests carry `--include`.

## Phase 2: implementation (green)

- [x] T007 `_run` adds `--include` to reads, strips the head, passes integer headers (FR-001).
- [x] T008 `gh_limit` decides from the headers, rate_limit only without them (FR-002 to FR-004).

## Phase 3: verification

- [x] T009 Every test file importing a changed module on 3.12; code host, adapters, pr actions,
  doctor, tracker adapters, merge ports, env credentials and reference adapters on 3.11 (FR-005).
