# Tasks: a fix to a broken base skips the soak, and merge check says either wait or who merges

Test first: each test task runs and fails for the expected reason before its implementation
task. Use the `case` fixture in `tests/test_merge.py` (PR `REF`, head `SHA`, base commit
`BASE`, `updated_at` two hours before `WUWEI_NOW`); no test reaches git or the network. For
base checks, add one local helper in `tests/test_merge.py`, `base_checks(host, conclusion)`,
that wraps `host.checks` so a call for `BASE` returns `[{'name': 'tests', 'sha': BASE,
'app_id': 1, 'state': 'completed', 'conclusion': conclusion}]` and any other SHA goes to the
recorded fake (keep recording the call). Do not change the shared fixture. Run the touched
test files, then the full suite.

## Phase 1: config key (FR-001)

- [X] T001 Test in `tests/test_merge.py`: `workspace.load_config` on the fixture gives
  `repos[0]['merge']['soak_skip'] == 'base_fix'`; `soak_skip = "never"` loads; `soak_skip =
  "sometimes"` fails to load.
- [X] T002 Add `"soak_skip": (str, "base_fix", ("base_fix", "never"))` to `MERGE_SCHEMA` in
  `cli/wuwei/workspace.py`. T001 passes.

## Phase 2: the red-to-green rule (FR-002)

- [X] T003 Test in `tests/test_merge.py`: `merge.fixes_base(base, head)` returns `['lint']`
  for base `lint: failure` and head `lint: success`; the same with base `error`; `[]` for
  base `success`, `cancelled`, `timed_out`, `skipped` or `None`; `[]` when head lacks the
  check or has it `neutral` or `skipped`; two fixed checks come back sorted.
- [X] T004 Implement `fixes_base` in `cli/wuwei/merge.py` (plan, Design). T003 passes.

## Phase 3: the soak skip and the wait sentence in `check` (FR-003, FR-004, FR-005; US1, US2.1)

- [X] T005 Tests in `tests/test_merge.py`, all with `soak_minutes = 180`:
  - base `failure` (helper): `check` exits 0 and `result.data['soak']` contains `tests`,
    `BASE` and `fixes the broken base` (US1.1);
  - same with `soak_skip = "never"`: exit 1 (US1.2);
  - base `success`: exit 1, reason exactly
    `merge policy: waits: soak ends at 2026-09-29T13:00:00+00:00`, data
    `{'next': 'run bin/wuwei merge example/project#7 after 2026-09-29T13:00:00+00:00'}`, and
    neither contains `owner merges` nor `ask the owner` (US1.3, US2.1);
  - base checks `Result(2, None, 'offline')` for `BASE`: exit 2;
  - soak passed (default `soak_minutes`): no `checks` call for `BASE` and `data['soak'] is
    None`; granted with `soak_minutes = 180`: no `checks` call for `BASE`.
  Update the soak cases of `test_config_eligibility` and `auto_only` to call
  `base_checks(host, 'success')` so they still exit 1 with `soak` in the reason.
- [X] T006 Implement the soak block and the `soak` evidence key in `merge.check`
  (`cli/wuwei/merge.py`, replacing line 313). T005 passes.

## Phase 4: the owner sentence and the `Next:` line (FR-005, FR-006; US2.2)

- [X] T007 Tests in `tests/test_merge.py`: with `auto = false`, `check` exits 1, reason
  `merge policy: owner merges: merge.auto is off`, `data['next']` is
  `run bin/wuwei merge example/project#7: it merges under the owner's grant, or asks the owner on a card`,
  and the reason has no `waits`. Through `main(['merge', 'check', '7'])` (cwd the repo, as
  `test_cli_check_and_numeric_merge`), stdout is the reason line then
  `Next: run bin/wuwei merge example/project#7: ...`; for the soak case (base green) it is the
  `waits` line then `Next: run bin/wuwei merge example/project#7 after ...`. `main(['merge',
  '7'])` refused prints no `Next:` line.
- [X] T008 Change the non-granted `except Refused` return in `cli/wuwei/merge.py` and print
  the `Next:` line in `cli/wuwei/commands/merge.py`. T007 passes; `tests/test_pr_guards.py`
  and `tests/test_headless_shepherd.py` still pass unchanged.

## Phase 5: invariant I40 (FR-007)

- [X] T009 Add the I40 row to the design 9.2 table in `docs/specs/2026-09-24-wuwei-design.md`
  and run `tests/test_invariants.py::test_table_matches_the_checks`: it fails until the check
  exists.
- [X] T010 Add `i40` to `tests/test_invariants.py` (computed once through `rules.memo`, READS
  `()`): over every base conclusion x head conclusion x head present, `merge.fixes_base`
  names the check only for base `failure` or `error` with head `success`. Register it in
  `INVARIANTS` and `READS`. `tests/test_invariants.py` passes within its time budget.

## Phase 6: docs (FR-008)

- [X] T011 Add the 4.6 amendment line in `docs/specs/2026-09-24-wuwei-design.md`, the
  `repos.merge.soak_skip` row in `docs/site/configuration.md`, and the base-fix sentence in
  the Soak glossary entry of `docs/site/concepts.md` (at most two lines). Run
  `tests/test_docs.py`.

## Phase 7: verify

- [ ] T012 Run `python -m pytest -q` from the repository root; everything passes. Check the
  changed files for em-dashes and emojis.
