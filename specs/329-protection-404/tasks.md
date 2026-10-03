# Tasks: branch protection read falls back to rulesets on a classic 404 and reports each source

**Input**: `specs/329-protection-404/spec.md`, `specs/329-protection-404/plan.md`
**Test command**: `python -m pytest -q` from the repository root.

Every behaviour is a test task followed by its implementation task. Run each test, see it
fail for the expected reason, then implement the minimum that makes it pass. Fixture names
stay neutral (`acme/widget`, `main`, `Security`, `unit`, `Review Gate`).

## Phase 1: The adapter reads rulesets after a classic 404 (US1)

- [X] T001 Test: in `tests/test_code_host.py`, add `test_classic_404_reads_rulesets`,
  parametrized over the classic stderr `gh: Not Found (HTTP 404)` and
  `gh: Branch not protected (HTTP 404)`: replay `[{'exit': 1, 'stderr': <form>},
  {'stdout': '[[]]'}]`, call `adapter().protection('acme/widget', 'main')`, assert exit 0,
  two `gh` calls, and `data == {'required_checks': [], 'strict': False, 'approvals': 0,
  'dismiss_stale_reviews': False, 'require_code_owner_reviews': False,
  'require_last_push_approval': False, 'enforce_admins': False,
  'conversation_resolution': False, 'allow_force_pushes': True, 'allow_deletions': True,
  'merge_queue': False, 'classic': False}`. Add `test_classic_404_takes_rules_fields`: the
  same 404 then a rulesets page with `required_status_checks` (`Security`, no
  `integration_id`), `pull_request` (1 approval, other parameters False),
  `non_fast_forward` and `deletion`; assert `required_checks == [{'name': 'Security',
  'app_id': None}]`, `approvals == 1`, `allow_force_pushes is False`,
  `allow_deletions is False`, `classic is False`. Update
  `test_unreadable_protection_is_not_absent`: add a second step
  `{'exit': 1, 'stderr': 'gh: Not Found (HTTP 404)'}` for the rulesets read and assert
  exit 2, `'gh exited 1' in result.reason`, two calls. Add
  `test_classic_403_is_unmeasured_without_reading_rulesets`: a classic
  `Must have admin rights to Repository. (HTTP 403)` then `[[]]`; assert exit 2 and one
  call (review F2). Add `"classic": true` to the
  protection recording's `data` in `tests/fixtures/code_host/recordings.json`.
  Expect: the new tests fail with exit 2 after one call; `test_read_recording[protection]`
  fails on the missing `classic` key; the updated invisible-repository test fails on the
  unused second step (one call).
- [X] T002 Test: in `tests/test_shepherd.py`, rewrite
  `test_missing_branch_protection_keeps_reason_for_fallback` as
  `test_missing_branch_protection_reads_rulesets_for_fallback`: replay the
  `Branch not protected (HTTP 404)` step and `{'stdout': '[[]]'}`, assert
  `github.protection('acme/widget', 'feature-base')` is exit 0 with
  `data['required_checks'] == []` and `data['classic'] is False` (the empty list is what
  triggers shepherd's default-branch retry and `review_required_checks` fallback). Expect:
  fails with exit 2.
- [X] T003 Implement in `adapters/code_host/github.py`: in `_run()` widen the
  protection-endpoint stderr match to `r'\(HTTP 404\)'`; in `protection()` wrap the
  classic `_api` call in the try/except from plan section 1 (re-raise anything but
  `branch protection absent`, else the synthetic unprotected body) and add
  `'classic': classic` to `result`. T001 and T002 pass; `tests/test_merge_ports.py` and
  `test_read_fails_closed` stay green.

## Phase 2: config check reports each source (US1, US2, US3)

- [X] T004 Test: in `tests/test_env_credentials.py`, add end-to-end tests through the real
  GitHub adapter (fixture `case`, config `'[adapters]\ncode_host="github"\n' + REPO`,
  `install_replay(monkeypatch, 'gh', steps)` with `{'exit': 0}` for `gh auth status` first):
  (a) classic `Not Found (HTTP 404)` then `[[]]`: exit 1; output has
  `acme/widget main: classic protection: none visible (404: unprotected or no admin)`,
  `required checks: missing (require status checks on main)`, `required reviews: missing`,
  `force pushes: missing (block force pushes on main)`,
  `deletions: missing (block deletions of main)`; `unmeasured` and `protected ref` are not
  in the output. (b) ruleset-only protection, with `review_required_checks = ["unit"]`
  appended to the repo table: rules `required_status_checks` (`unit`), `pull_request`
  (1 approval), `non_fast_forward`, `deletion`: exit 0, the classic line, and
  `required checks: ok (unit)`, `required reviews: ok`, `force pushes: ok`,
  `deletions: ok`. (c) classic 404 then a rulesets `{'exit': 1, 'stderr': 'gh: Not Found
  (HTTP 404)'}`: exit 2 and `protection: unmeasured`. Replace
  `test_unprotected_branch_is_a_finding` (its `Fake` result `branch protection absent` no
  longer exists) with (a). In `test_unmeasured_outranks_missing_across_repositories`,
  change the first result to `protected(approvals=0)` so it is still a findings result.
  Expect: (a) and (b) fail with exit 2 and `protection: unmeasured`.
- [X] T005 Test: in `tests/test_env_credentials.py`, with the `host` fixture (`Fake`):
  `protected(required_checks=[Security, unit])` plus `review_required_checks = ["unit"]`
  prints `required checks: ok (Security, unit)` and exits 0;
  `protected(required_checks=[Security])` plus the same config prints
  `required checks: missing (require status checks on main: unit; required now: Security)`
  and exits 1; `protected(approvals=0, required_checks=[..., {'name': 'Review Gate',
  'app_id': None}])` prints `required reviews: missing (require at least 1 approving review
  on main, or set shepherd.min_reviewers = 0 for a solo owner; the required check Review
  Gate (shepherd.review_gate_check) may be satisfying it)` and exits 1, while
  `protected(approvals=0)` without that check ends the line at `for a solo owner)` with no
  `review_gate_check` in the output (review F1); a result whose
  data lacks `classic` prints `protection: unmeasured` and exits 2. Update the
  `test_each_protection_gap_is_a_finding` row for `review_required_checks = ["unit"]` to
  expect `required checks: missing (require status checks on main: unit; required now:
  lint, tests)`. Expect: the listing, gate and updated-row assertions fail on the old
  text; the missing-`classic` case fails with exit 0.
- [X] T006 Implement in `cli/wuwei/commands/config.py` (plan section 3): pass
  `config['shepherd']['review_gate_check']` from `run()`; in `_protection()` delete the
  `branch protection absent` branch, build sorted `names` and `listed`, choose the first
  row from `data['classic']`, list names on `required checks`, add the gate note on
  `required reviews`. T004 and T005 pass; `test_fully_protected_branch_is_clean`,
  `test_solo_owner_exemption` and `test_malformed_protection_is_unmeasured` stay green.

## Phase 3: Docs (FR-009)

- [X] T007 Test: in `tests/test_docs.py`, extend
  `test_config_check_host_and_credential_layout_are_documented` to require
  `classic protection`, `none visible (404: unprotected or no admin)`, `required now`
  and `review_gate_check` in the section, and to assert `currently reads as missing` is
  not in the page. Expect: fails on `classic protection`.
- [X] T008 Implement in `docs/site/configuration.md` the table and sentence changes of
  plan section 4. T007 passes.

## Phase 4: Finish

- [X] T009 Run `python -m pytest -q` from the repository root; everything passes. Check
  every changed file for em-dashes, emojis and absolute local paths, and remove any.
