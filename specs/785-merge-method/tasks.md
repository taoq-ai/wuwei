# Tasks: the merge method follows the repository

Test first: each test task runs and fails for the expected reason before its implementation
task. Tests are in-process: `tests/test_merge.py` through its `case` fixture (the recording
`Fake` code host, `WUWEI_NOW` 2026-09-29T12:00:00Z), `tests/test_code_host.py` through
`install_replay` (no real `gh`). Neutral fixtures only (`example/project`, `acme/widget`).
Run the touched test files after each pair, then the full suite (`python -m pytest -q`).

## Phase 1: the setting (FR-001, US2)

- [X] T001 Test in `tests/test_merge.py`: `workspace.load_config` of the `case` config gives
  `repos[0]['merge_method'] == 'auto'`; with `merge_method = "merge"` under `[[repos]]` it is
  `merge`; `merge_method = "fast"` is refused by `load_config` (`workspace.ConfigError`).
- [X] T002 Add `merge_method` to `SCHEMA['repos']` in `cli/wuwei/workspace.py`.

## Phase 2: the adapter reports the allowed methods (FR-002)

- [X] T003 Test in `tests/test_code_host.py`: replace `test_protection_measures_squash` with
  `test_protection_measures_methods`, parametrized over the repository read and a ruleset's
  `allowed_merge_methods`:
  - all three `allow_*` true, no ruleset list: `['squash', 'rebase', 'merge']`;
  - only `allow_merge_commit` true: `['merge']`;
  - all true, ruleset `['merge']`: `['merge']`; ruleset `['merge', 'squash']`:
    `['squash', 'merge']`;
  - `allow_squash_merge` false, ruleset `['squash']`: `[]`;
  - `allow_rebase_merge` missing, and `allow_merge_commit: 'yes'`: exit 2.
  Update `REPO` to carry all three fields and `test_classic_404_reads_rulesets`'s expected
  dict to `'methods': [...]` in place of `'squash': True`. In
  `tests/fixtures/code_host/recordings.json` add `"allow_rebase_merge": false` to the
  repository stdout and expect `"methods": ["squash"]` in place of `"squash": true`.
- [X] T004 Implement `methods` in `protection` in `adapters/code_host/github.py`.
- [X] T005 Update the repository replays in `tests/test_shepherd.py` (line 796) and
  `tests/test_env_credentials.py` (`SQUASH`, line 497) to carry all three `allow_*` fields;
  run both files green.

## Phase 3: the adapter merges with the method (FR-004)

- [X] T006 Test in `tests/test_code_host.py`: for each of `squash`, `rebase`, `merge`,
  `adapter().merge('acme/widget#7', HEAD, method)` runs exactly
  `['pr', 'merge', 'https://github.com/acme/widget/pull/7', '--' + method, '--match-head-commit', HEAD]`
  (replayed, exit 0, `{'accepted': True, 'sha': HEAD}`); `method` `'admin'`, `'--admin'`
  and `'auto'` are exit 2 with no subprocess; add
  `['pr', 'merge', <url>, '--auto', '--match-head-commit', 'a' * 40]` to
  `test_run_rejects_unapproved_commands_before_spawn`. In `recordings.json` the `merge`
  operation's `args` gain `"squash"` (argv unchanged).
- [X] T007 Implement the `_run` merge case and `merge(ref, sha, method)` in
  `adapters/code_host/github.py`; the same signature in `adapters/code_host/none.py`,
  `PARAMETERS['code_host']['merge']` in `cli/wuwei/registry.py` and the fake in
  `tests/fakes/code_host.py`.

## Phase 4: the policy chooses the method (FR-003, FR-005, US1, US2, US3)

- [X] T008 Test in `tests/test_merge.py` (fixture `protection` now `'methods': ['squash']`):
  `test_merge_method_follows_the_repository`, parametrized `(setting, methods, expected)`:
  - `auto`, `['merge']`: exit 0, `data['method'] == 'merge'`;
  - `auto`, `['squash', 'rebase', 'merge']`: `squash`; `auto`, `['rebase', 'merge']`: `rebase`;
  - `merge`, `['squash', 'merge']`: `merge`;
  - `merge`, `['squash']`: exit 1, reason contains
    `example/project does not allow the merge method into main` and `repos.merge_method`;
  - `auto`, `[]`: exit 1, reason contains `example/project allows no merge method into main`;
  - methods `'yes'` and `['fast-forward']`: exit 2.
  Replace `test_squash_must_be_allowed` with these rows, and the `squash` row of
  `test_grant_never_lifts_a_precondition` with `methods = []`, hint `allows no merge method`.
- [X] T009 Test in `tests/test_merge.py`: with `methods = ['merge']`, `main(['merge', 'check',
  '7'])` exits 0 and its JSON has `"method": "merge"`; `policy().execute(REF, root)` records
  `('merge', (REF, SHA, 'merge'), root)` in `host.calls` and the journal entry's
  `evidence['method'] == 'merge'`. Update `test_merge_pins_head_and_writes_evidence_and_undo`
  to `(REF, SHA, 'squash')` and the `race` stub in `test_push_between_check_and_merge_fails`
  to take `method`.
- [X] T010 Test in `tests/test_merge.py`: `test_strict_without_grant_names_the_owner_command`
  with `methods = ['merge']` names `... --merge --match-head-commit <SHA>` (the existing
  `COMMAND` stays the squash case); an `owner_paths` route on a merge-only repository names
  `--merge`.
- [X] T011 Implement `METHODS`, `method_for`, the method rule and `method` evidence in
  `check`, and `owner_command(ref, head, method)`, `by_grant` and `execute` in
  `cli/wuwei/merge.py`.
- [X] T012 Update `tests/test_path_day.py`: `HEAD['protection']` carries `'methods': ['squash']`
  and the merge call assertion (line 267) expects `(day.ref, day.head, 'squash')`.

## Phase 5: the watch follows a merge commit (FR-006, US3)

- [X] T013 Test in `tests/test_merge.py`:
  - a merged entry (the `merged` helper) on a merge-only repository (`methods = ['merge']`)
    with a baseline note: at `WUWEI_NOW` 2026-10-13T12:00:00Z `poll` returns 0, calls
    `history` with `patches` False only, records no `outcome` and no `monitor_error`;
  - the existing squash case still measures (`test_outcome_measured_once_at_fourteen_days...`
    unchanged);
  - `test_revert_in_base_history_trips_immediately` parametrized over the message
    `This reverts commit {MERGED}.` and
    `This reverts commit {MERGED}, reversing\nchanges made to {BASE}.`: both trip the breaker.
- [X] T014 Implement the `measure` condition (with its `ponytail:` comment) and the revert
  pattern in `monitor` in `cli/wuwei/merge.py`.

## Phase 6: invariant and docs (FR-007)

- [X] T015 Add the I72 row as the last row of the design 9.2 table in
  `docs/specs/2026-09-24-wuwei-design.md` and run
  `tests/test_invariants.py::test_table_matches_the_checks`: it fails until the check exists.
- [X] T016 Add `i72` to `tests/test_invariants.py` (computed once through `rules.memo`, as
  `i40`): for every setting in `('auto', *merge.METHODS)` and every subset of `merge.METHODS`,
  `merge.method_for` returns the setting only when allowed, under `auto` the first allowed in
  squash, rebase, merge order, else `None`; append `'I72': i72` to `INVARIANTS` and
  `'I72': ()` to `READS`. `tests/test_invariants.py` passes.
- [X] T017 Docs: the 4.6 amendment line and the adapter table `merge(ref, sha, method)` in
  `docs/specs/2026-09-24-wuwei-design.md`; the `repos.merge_method` row after
  `repos.merge_deploys` and `--<method>` in the `merge.default_tier` row of
  `docs/site/configuration.md`; the merge-method sentence in `docs/site/concepts.md` (line
  195). Run `tests/test_docs.py`.

## Phase 7: finish

- [X] T018 Full suite green; grep the changed files for em-dashes, emojis and absolute local
  paths and remove any.
