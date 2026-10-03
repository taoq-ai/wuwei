# Tasks: reviewers from history, owner override, solo fall-through

**Input**: [spec.md](spec.md), [plan.md](plan.md)

Test first: each test task is written, run and seen failing for the expected reason before
its implementation task. Run with `python -m pytest -q` from the repository root. Fixtures
reuse the `case` fixture and `solo_raise` helper in `tests/test_shepherd.py`; neutral names
only (`acme/widget`, `example.test`).

## Phase 1: Setup

- [X] T001 Add `shepherd.reviewers`, `shepherd.reviewers_exclude` (lists of str, default
  `[]`) and the per-repository `repos[].shepherd.reviewers` to `SCHEMA` in
  `cli/wuwei/workspace.py`. (Schema only; behaviour is tested below.)

## Phase 2: User Story 1, history with no configuration (P1)

- [X] T002 [US1] Test in `tests/test_shepherd.py`: config with no `[shepherd.authors]`,
  history `alice 5, bob 4, carol 1` (example.test emails), fake `author_login` resolving all
  three: `select_reviewers` returns `['alice', 'bob', 'lead']`; with `carol 3` (within
  `tie_commits`) it returns `['alice', 'bob', 'carol', 'lead']`. (Issue acceptance 1; the
  `lead` row stays mapped so its host verification still runs.)
- [X] T003 [US1] Test in `tests/test_shepherd.py`: rewrite
  `test_unmapped_author_names_email_and_key` to `test_unresolved_author_is_skipped_once`:
  history `alice 4, missing 3`; `select_reviewers` returns `['alice', 'lead']`, exactly one
  `reviewer.unresolved` event with payload `{'repo': 'acme/widget', 'author': 'missing'}`
  (no `@`), state `author_logins['missing@example.test'] is None`; a second call makes no
  second `author_login` call for that email and writes no second event. Also an empty login
  (`Result(0, {'login': ''})`) and `Result(2, reason='github.author_login: could not run: invalid author email')`
  are skipped the same way. (Issue acceptance 4, first half.)
- [X] T004 [US1] Test in `tests/test_shepherd.py`: `author_login` returning
  `Result(2, reason='offline')` or `Result(0, {'message': 'Not Found'})` makes
  `select_reviewers` raise `ValueError` (fail closed) and writes no `reviewer.unresolved`
  event.
- [X] T005 [US1] Test in `tests/test_state_allowlist.py` (or the existing reserved-key
  test): generic `wuwei state set author_logins...` is refused naming its producer, and
  `wuwei event reviewer.unresolved` is refused as a reserved kind.
- [X] T006 [US1] Implement in `cli/wuwei/shepherd.py::_rank`: `login_of` with the day cache
  and the not-found rules, `tally(rows)`, one cache write and the per-email events after
  the window loop; narrow the verification loop to `shepherd.authors` logins (plan steps
  3-6, 9).
- [X] T007 [US1] Implement reservations: `STATE_PRODUCERS['author_logins']` in
  `cli/wuwei/state.py`, `EVENT_PRODUCERS['reviewer.unresolved']` in
  `cli/wuwei/commands/event.py`, `'reviewer.unresolved'` in `SILENT` in
  `cli/wuwei/signal.py`.

## Phase 3: User Story 2, solo owner (P1)

- [X] T008 [US2] Test in `tests/test_shepherd.py`: rewrite
  `test_owner_handle_case_differs_from_code_host_login` and add
  `test_single_author_raises_solo_on_defaults`: `solo_raise(case, monkeypatch, minimum=1)`
  with `lead_login` set to `builder` (the owner, as setup writes it): `raise_pr` exits 0,
  stdout has `acme/widget#7` and `reviewers: none (solo)`, `pr_reviewers[REF] == []`, no
  `request_reviewers` call. (Issue acceptance 2.)
- [X] T009 [US2] Test in `tests/test_shepherd.py`: rewrite
  `test_zero_reviewers_names_minimum` to expect `[]`; extend
  `test_configured_minimum_two_requires_two` to assert the refusal text contains
  `shepherd.min_reviewers 0` and `shepherd.reviewers` and not `no setting lowers it`;
  update `test_empty_code_host_login_names_email_and_key` to exit 0 solo with one event for
  `builder`.
- [X] T010 [US2] Test in `tests/test_shepherd.py`: with `pr_reviewers[REF] = []` written
  through `state._write_state(..., reserved=False)` and a clear gate,
  `post_review_request` returns 0, prints `reviewers: none (solo)`, makes no
  `request_reviewers` call and no chat `post`, writes no `channel_posts`.
- [X] T011 [US2] Implement in `cli/wuwei/shepherd.py`: the `if selected and len(selected) <
  min_reviewers` refusal with `REVIEWER_WAYS_OUT` (plan step 8); `raise_pr` prints `SOLO`;
  `post_review_request` drops the length check, requests only when non-empty, returns 0
  with `SOLO` after the record. Add `SOLO` to `cli/wuwei/obligations.py`.
- [X] T012 [US2] Test in `tests/test_obligations.py`: with `min_reviewers = 1`, chat
  configured, no requested reviewers and `pr_reviewers[REF] = []`, the sweep owes neither
  `reviewer` nor `channel-post` and prints `NOT APPLICABLE reviewer: reviewers: none (solo)`.
- [X] T013 [US2] Implement `_not_applicable(config, recorded=None)` and pass
  `data.get('pr_reviewers', {}).get(ref)` at both call sites in `cli/wuwei/obligations.py`.
- [X] T014 [US2] Test in `tests/test_signal_status.py`: a day with `pr_reviewers` holding one
  `[]` entry gives `status --line` containing `reviewers: none (solo)`; with only non-empty
  lists it does not.
- [X] T015 [US2] Implement `solo` in `snapshot` and the line part in
  `cli/wuwei/commands/status.py`.

## Phase 4: User Story 3, owner override (P2)

- [X] T016 [US3] Test in `tests/test_shepherd.py`: `shepherd.reviewers = ["pat-dev"]`:
  `select_reviewers` returns `['pat-dev']`, no `authorship` call on the vcs port, no
  `author_login` call; `post_review_request` requests exactly `['pat-dev']` (the fake's
  `requested` set to `['pat-dev']`). (Issue acceptance 3.)
- [X] T017 [US3] Test in `tests/test_shepherd.py`: `[repos.shepherd] reviewers = ["sam-dev"]`
  plus workspace `shepherd.reviewers = ["pat-dev"]` gives `['sam-dev']`; an override
  containing the PR author (`builder`, different case) drops it; an override with a PR whose
  only changed path is `specs/x.md` still returns the override.
- [X] T018 [US3] Test in `tests/test_shepherd.py`: `shepherd.reviewers_exclude = ["Alice"]`
  with the default history gives `['bob', 'lead']`; excluding `lead` drops the lead.
- [X] T019 [US3] Implement in `cli/wuwei/shepherd.py::_rank`: override first, the moved
  empty-paths refusal, the exclusion set (plan steps 1-3, 7); remove the empty-paths checks
  from `select_reviewers` and `raise_pr`.

## Phase 5: User Story 4, the refusal names the ways out (P2)

- [X] T020 [US4] Test in `tests/test_pr_guards.py`: `gh pr create` with `min_reviewers = 1`
  returns exit 1 with a reason containing `--reviewer`, `shepherd.min_reviewers 0` and
  `shepherd.reviewers and raise with bin/wuwei pr raise` (the guard never reads
  `shepherd.reviewers`, so that way out goes through `pr raise`).
- [X] T021 [US4] Test in `tests/test_hooks.py` (in-process): with a workspace config,
  `hook.posture({}, [(pr.check, NO_REVIEWER), (pr.check, 'other')], root)` returns
  `[('pr', NO_REVIEWER, ''), ('pr', 'other', 'posture: publish = block (owner-only action; no setting lowers it)')]`.
- [X] T022 [US4] Implement `REVIEWER_WAYS_OUT` and `NO_REVIEWER` in
  `cli/wuwei/guards/__init__.py`, use it in `cli/wuwei/guards/pr.py::create_check`, and the
  one-line `line = ''` in `cli/wuwei/commands/hook.py::posture`.

## Phase 6: User Story 5, explain (P3)

- [X] T023 [US5] Test in `tests/test_shepherd.py`: `main(['pr', 'reviewers', REF,
  '--explain'])` with changed files `src/app.py`, `src/util.py` and a vcs `authorship`
  lambda answering per path: exit 0; stdout lines include `window: 90 days`,
  `alice 7: src/app.py 4, src/util.py 3 (selected)`, `lead: shepherd.lead_login (selected)`
  and ends with `reviewers: alice bob lead`; without `--explain` stdout is only the
  `reviewers:` line; a solo PR prints `reviewers: none (solo)`; a refusal exits 1; an
  unreadable PR exits 2.
- [X] T024 [US5] Implement the `explain` lines in `cli/wuwei/shepherd.py::_rank` (plan
  step 10), `explain` passthrough in `select_reviewers`, and the `reviewers` subcommand in
  `cli/wuwei/commands/pr.py`.

## Phase 7: Config surface and docs

- [X] T025 Test in `tests/test_docs.py`: extend
  `test_shepherd_settings_are_visible_in_template_and_site` with `reviewers` and
  `reviewers_exclude` (template defaults `[]`, rows in `configuration.md`); assert
  `` `repos.shepherd.reviewers` `` and `` `[repos.shepherd]` `` are documented. Test in
  `tests/test_calibrate.py` (where profile export is tested; `tests/test_profiles.py` covers
  guard profiles): `shepherd.reviewers`, `shepherd.reviewers_exclude` and
  `repos.shepherd` are not exported.
- [X] T026 Implement `templates/workspace/config.toml` lines, `profiles.PRIVATE` in
  `cli/wuwei/profiles.py`, and the rows in `docs/site/configuration.md`.
- [X] T027 Update `docs/site/reference.md` ("Raising a PR", the `bin/wuwei pr` row, the
  posture paragraph, "Watch state") per plan. Covered by the existing
  `test_reference_lists_every_cli_command` and `test_docs` suite.

## Phase 8: Polish

- [X] T028 Run `python -m pytest -q`; everything passes. Grep the changed files for
  em-dashes and emojis and remove any. No absolute local paths in any file.

## Dependencies

T001 first. US1 (T002-T007) before US2 (T008-T015), since solo builds on the rewritten
`_rank`. US3, US4 and US5 are independent of each other after US1. Docs last.
