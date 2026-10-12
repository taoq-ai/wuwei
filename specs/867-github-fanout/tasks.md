# Tasks: why reads local state only and doctor caps its network probes

**Input**: [spec.md](spec.md), [plan.md](plan.md)

## Phase 1: tests first (red)

- [x] T001 [US1] `tests/test_code_host.py`: the rate-limit table names the failed call's
  resource (REST: core; GraphQL: graphql) and says "secondary limit" when that resource has
  calls left (FR-001, FR-002); run it, see the REST secondary and GraphQL rows fail.
- [x] T002 [US2] `tests/test_code_host.py`: `WUWEI_RATE_LIMIT_WAIT=0` makes a call whose
  reset is 30 s away return at once (FR-003); run it, see it sleep.
- [x] T003 [US2] `tests/test_doctor.py`: doctor under a rate limit sleeps zero seconds and
  restores the variable (FR-003); the config check row is `waiting` when its protection read
  is rate limited (FR-004); run, see both fail.
- [x] T004 [US3] `tests/test_doctor.py`: a clean protection read is made once a day; a read
  with findings is made again (FR-005); run, see the second call.
- [x] T005 [US4] `tests/fixtures/code_host/recordings.json` and `tests/test_code_host.py`:
  the `open_prs` recording is the search call; an incomplete search fails closed (FR-006);
  `tests/test_plan.py`: plan propose calls `open_prs(repo, login)`; run, see them fail.
- [x] T006 [US5] `tests/test_why.py`: `why` with every adapter load and subprocess refused
  (FR-007). Green on arrival: it pins today's behaviour (spec root cause 6).

## Phase 2: implementation (green)

- [x] T007 [US1] `adapters/_http.py` `RateLimited`, `gh_limit(resource=)`; `adapters/code_host/github.py`
  `_run` passes the resource; `adapters/tracker/github.py` `_gh` passes `graphql`.
- [x] T008 [US2] `adapters/_http.py` `cap` reads `WUWEI_RATE_LIMIT_WAIT`;
  `cli/wuwei/commands/doctor.py` `diagnose` sets it to 0 for the run; `_gates` maps a limited
  config check to `waiting`.
- [x] T009 [US3] `cli/wuwei/commands/config.py` `_protection` reads and writes
  `<day>/protection.json`.
- [x] T010 [US4] `adapters/code_host/github.py` `open_prs(repo, author)` and its `_run`
  allowlist entry; `none.py`, `registry.py`, `tests/fakes/code_host.py`,
  `tests/test_adapters.py`; `cli/wuwei/plan.py` `_owner_prs`.
- [x] T011 Docs: `docs/site/configuration.md`, `docs/site/reference.md`.

## Phase 3: verification

- [x] T012 Run every test file that imports a changed module under 3.12, and the code_host,
  doctor, why, plan and next files under 3.11.

## Phase 4: review fix round

- [x] T013 F1: `tests/test_plan.py` `test_owner_pr_search_skips_handles_that_are_not_github_logins`
  (red: a chat ID and dotted handle were searched); `plan._owner_prs` searches login-shaped
  handles and `outbound.owner.code_host` only.
- [x] T014 Residual: `tests/test_code_host.py` header tests over recorded failing
  `--include` replies (REST, GraphQL, paged read; a write is never repeated) (red: rate_limit
  was read); `_http.included_limit` and `github._headers_limit` (FR-008).
- [x] T015 F2: `tests/test_doctor.py` `test_a_protection_finding_outranks_a_rate_limit` (red:
  the row read waiting); `doctor._gates` waits only with no finding.
- [x] T016 F3: search index lag recorded under Assumptions.
- [x] T017 D1: `tests/test_code_host.py` `test_a_secondary_limit_is_never_asked_again` (red:
  an `--include` re-ask was sent); `github._headers_limit` returns None on a secondary limit.
