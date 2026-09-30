# Tasks: Solo owner without reviewers or chat

Test first: each test task is run and seen failing for the stated reason before its implementation task.

## Config accepts a zero minimum (FR-001)

- [X] T001 [US1] In tests/test_workspace.py add a test that `[shepherd]\nmin_reviewers = 0` loads with value 0, and add `('[shepherd]\nmin_reviewers = -1', 'shepherd.min_reviewers')` to `test_invalid_config_values`. Fails: 0 is rejected with `expected integer >= 1`.
- [X] T002 [US1] In cli/wuwei/workspace.py change the `min_reviewers` schema minimum from 1 to 0.

## Unmapped author falls back to the code host (FR-003)

- [X] T003 [US1] In tests/test_shepherd.py make the fixture `author_login` return `Result(2, reason='author login unavailable')` for unknown emails (keep `test_unmapped_author_names_email_and_key` asserting the same message), and add a test where an unmapped `carol@example.test` resolves to `carol` and is selected and verified, plus one where the owner's unmapped email resolves to the author login and is excluded. Fails: the unmapped email raises before any lookup.
- [X] T004 [US1] In cli/wuwei/shepherd.py `_rank` load the code host once at the top, resolve unmapped emails through `code_host.author_login` with a per-call cache, keep the `shepherd.authors ... <email>` ValueError on failure, and feed resolved logins into the verification `emails` map.

## Solo raise creates the PR without a reviewer request (FR-002)

- [X] T005 [US1] In tests/test_shepherd.py add the acceptance test: config with `min_reviewers = 0`, `lead_login = ""`, authorship rows only for the owner's unmapped email; `raise_pr` returns 0, `pr_reviewers[REF] == []`, and no `request_reviewers` call is recorded. Confirm `test_zero_reviewers_names_minimum` (min 1, no eligible reviewer, exit 1 refusal) still passes unchanged. Fails: `request_reviewers` is called with an empty list (or the fixture port returns an error), exit 2.
- [X] T006 [US1] In cli/wuwei/shepherd.py `raise_pr` run the reviewer request and its verification only when `reviewers` is non-empty.

## PR create guard honours the minimum (FR-004)

- [X] T007 [US2] In tests/test_pr_guards.py add a table test with `[shepherd]\nmin_reviewers = 0` in the fixture config: `gh pr create` returns 0 with a gate check call; `gh pr create --reviewer ""` and `gh pr create --reviewer ,` return 1; `gh pr create` with a missing gate verdict returns 1 on the gates. The existing default-config row `('gh pr create', 1, 'reviewer')` stays. Fails: the reviewer rule ignores the minimum.
- [X] T008 [US2] In cli/wuwei/guards/pr.py `create_check` require a named `--reviewer` only when `config['shepherd']['min_reviewers'] > 0` or a `--reviewer` value is present.

## Visibility rule for reviewer and channel post (FR-005, FR-006)

- [X] T009 [US3] In tests/test_obligations.py, tests/test_merge.py and tests/test_watch.py add `[adapters]\nchat = "slack"` to the fixtures listed in plan.md so their channel-post assertions keep testing the rule with chat configured (expected values unchanged; they pass before and after).
- [X] T010 [US3] In tests/test_obligations.py add the acceptance tests: (a) solo config (`min_reviewers = 0`, chat default `none`), no requested reviewer, no channel post, PASS gate file at head: `sweep()` exits 0, event `visibility_owed == 0`, output has `NOT APPLICABLE reviewer` and `NOT APPLICABLE channel-post` with `shepherd.min_reviewers = 0`; (b) `min_reviewers = 1`, chat `none`, no requested reviewer: exit 1, `OWED reviewer`, `NOT APPLICABLE channel-post` naming `adapters.chat`; (c) solo config without a gate file: `verdict` still owed. Fails: reviewer and channel-post are always owed.
- [X] T011 [US3] In cli/wuwei/obligations.py add `_not_applicable(config)`, give `_visibility` a `config` parameter that skips not-applicable findings, pass `config` from `evaluate` and print the `NOT APPLICABLE` lines; in cli/wuwei/merge.py pass `config` at the `_visibility` call.

## Template and docs (FR-007)

- [X] T012 In tests/test_docs.py extend `test_shepherd_settings_are_visible_in_template_and_site` to assert the configuration page's `shepherd.min_reviewers` row mentions `0`, while the template default stays 1. Fails: the row does not mention 0.
- [X] T013 Update templates/workspace/config.toml comments for `min_reviewers` and `[shepherd.authors]`, and docs/site/configuration.md rows for `shepherd.min_reviewers`, `shepherd.authors` and `adapters.chat`.

## Review fixes

- [X] T015 In tests/test_shepherd.py add a min 1 raise where the code host returns `Builder` for owner handle `builder`: raise exits 1 before any PR is created; in cli/wuwei/shepherd.py `_rank` compare the author login case-insensitively. Add a raise where the code host returns an empty login: exit 2 naming `shepherd.authors` and the email.

## Verification

- [X] T014 Run `python -m pytest -q` from the repository root; everything passes. Check every changed file for em-dashes, emojis and absolute local paths.
