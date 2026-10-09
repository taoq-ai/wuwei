# Tasks: next passes --repo to worktree add on a multi-repository workspace, and approves the day's proposed goals

Test first: each test task runs and fails for the expected reason before its implementation
task. Run only the touched test files (never the full suite):
`python -m pytest -q tests/test_dispatch.py tests/test_worktree_command.py tests/test_plan.py
tests/test_path_day.py tests/test_invariants.py tests/test_charters.py tests/test_docs.py
tests/test_next.py tests/test_owner_edits.py`.

## Phase 1: defect 2, approve reads the day's proposed goals (US2; FR-009, FR-010)

- [X] T001 Test in `tests/test_plan.py`: replace `test_approve_needs_recorded_goals` with
  `test_approve_reads_the_proposed_goals` (the `empty` fixture, `plan.propose(lead(), empty)`,
  `plan.approve(['A'], empty, goals_confirmed=True)` passes, state `goals == ['G-1', 'G-2']`,
  `memory/goals.md` byte-identical to before) and `test_approve_without_goals_or_draft_fails`
  (delete the day `goals.md` after propose: still `no goals`). Run: the first fails with
  `no goals`.
- [X] T002 Test in `tests/test_path_day.py`: `test_fresh_day_goals_reach_an_approved_plan`
  with `prepare(Day(...))`, `memory/goals.md` set to the goals template
  (`test_plan.TEMPLATE`) and `day.proposal` returning goal blocks (`test_plan.LEAD_GOALS`
  shape); drive `wuwei next --json` with the existing `bash` and `card` helpers until
  `gate_approved`, asserting no command exits 2 and no `no goals` in any output; then the
  next row is `goals` with `wuwei goals edit --file .wuwei/days/<date>/goals.md`, and
  running it records the goals in memory (FR-010, the row order). Run: fails at approve.
- [X] T003 Implement FR-009 in `cli/wuwei/plan.py` `approve` (lines 307-309): memory text,
  else the day's `goals.md` when memory has no goal heading. Run `tests/test_plan.py`,
  `tests/test_path_day.py` and `tests/test_owner_edits.py`: green.

## Phase 2: defect 1, `_start` passes `--repo` (US1 scenarios 1, 2, 4, 5; FR-001, FR-002, FR-006)

- [X] T004 Test in `tests/test_dispatch.py`: a two-repository variant of `day_set` (config
  with two `[[repos]]`, `proposal.json` rows: `P3` with `repo = "acme/code"`, `P1` with no
  repo): the `P3` start commands are `wuwei worktree add P3 --repo acme/code` then the brief;
  `P1` is exactly one command, `wuwei plan park P1 --reason '<reason naming both
  repositories>'`, and that command run through `main` exits 0 and leaves `P1` out of
  `next.approved`; with `worktrees/P1` present, `P1` is the brief only. The one-repository
  tests stay unchanged. Run: fails (no `--repo`, no park).
- [X] T005 Test in `tests/test_path_day.py`: `test_multi_repository_dispatch_runs` with a
  second `[[repos]]` (`acme/other`, path `other`, the directory created) appended to the Day
  config, `prepare`'s interview answers extended to `acme/other`, and `repo =
  "acme/widget"` on the lead's candidate; walk `wuwei next --json` until the first `set`
  action and run each start command: `wuwei worktree add A --repo acme/widget` is among them
  and every command exits 0 (a setup card for the second repository is answered by the
  `card` helper). Run: fails, `worktree add A` exits 2.
- [X] T006 Implement in `cli/wuwei/dispatch.py`: lift `candidate(root, name)` out of `_start`;
  `_start(root, name, repos)` per plan section 2; `launch_set` passes `config['repos']`. Run
  `tests/test_dispatch.py` and `tests/test_path_day.py`: green, one-repository tests
  untouched.

## Phase 3: `worktree add` falls back to the proposal (US1 scenario 6; FR-007)

- [X] T007 Test in `tests/test_worktree_command.py` `test_repo_selection`: add a row with
  names `['app', 'web']`, no `--repo`, and today's `proposal.json` naming `repo = "web"` for
  `X`: exit 0 on `web`; extend the existing two-repository row (no proposal) to assert the
  error names `app` and `web`. Run: the new row fails with exit 2.
- [X] T008 Implement in `cli/wuwei/commands/worktree.py` `add` (line 44): the
  `dispatch.candidate` fallback and the configured names in the error. Run
  `tests/test_worktree_command.py`: green.

## Phase 4: `plan.propose` keeps, derives and lints `repo` (US1 scenarios 3, 4; FR-003, FR-004, FR-005)

- [X] T009 Test in `tests/test_plan.py`: with two configured repositories whose checkouts are
  directories under the fixture root, one holding `src/a.py`: a candidate with `repo` naming
  the second keeps it; a candidate with `paths: ['src/a.py']` and no `repo` gets the first
  in `proposal.json`; a candidate with a path in neither (and one with an unknown `repo`
  name) gets no `repo`, and `plan.md` carries the `Repository: not named` line naming both
  repositories; propose returns the plan path (no exception). With one repository,
  `plan.md` has no `Repository:` line and `proposal.json` no `repo`. Run: fails.
- [X] T010 Implement in `cli/wuwei/plan.py` `propose` per plan section 4. Run
  `tests/test_plan.py`: green.

## Phase 5: the lead is asked (FR-008)

- [X] T011 Test in `tests/test_docs.py` (next to the `LEAD_BODY` assert at line 1418) and
  `tests/test_charters.py` (the lead assertions near line 136): `repo` and `more than one
  configured repository` appear in `LEAD_BODY` and in `charters/lead.md`. Run: fails.
- [X] T012 Implement: the `LEAD_BODY` sentence in `cli/wuwei/commands/next.py` (no single
  quote), the step 4 sentence in `charters/lead.md`, version unchanged. Run
  `tests/test_docs.py tests/test_charters.py tests/test_next.py`: green.

## Phase 6: invariants (FR-011)

- [X] T013 Test in `tests/test_invariants.py`: add `i26` and `i27` per plan section 7 to
  `INVARIANTS` and `READS` (READS `()`), without the 9.2 rows. Run
  `test_table_matches_the_checks`: fails (table lacks I26, I27). Confirm once, by hand, that
  each check fails on the pre-fix behaviour (monkeypatch `_start` to the bare `worktree add`,
  `approve` to memory only), then drop the patch.
- [X] T014 Add the I26 and I27 rows to `docs/specs/2026-09-24-wuwei-design.md` 9.2 after I24.
  Run `tests/test_invariants.py`: green, the walk under its 1.0 s CPU budget.

## Phase 7: finish

- [X] T015 Grep the files written for em-dashes, emojis and absolute local paths; remove any.
  Run the touched test files listed at the top once more.

## Phase 8: review findings

- [X] T016 (F1) Test in `tests/test_plan.py` `test_one_pr_number_in_two_repositories_gives_two_ids`:
  the same PR number open in two repositories gives `PR-widget-12` and `PR-paper-12`, and approve
  claims both. Implement in `cli/wuwei/plan.py` `_owner_prs`: with more than one repository the id
  is `PR-<short repository name>-<number>`; one repository keeps `PR-<number>`. The two-repository
  walk in `tests/test_path_day.py` no longer hides the second repository's PR.
- [X] T017 (F2) Test in `tests/test_dispatch.py` `test_a_park_runs_without_free_seats`: with no free
  seats the unresolved item is a `park` entry carrying the park command. Implement in
  `cli/wuwei/dispatch.py` `launch_set`: parks are returned before the seat and CAP checks and
  take no seat. The park record wording ("at day close") is fixed text in `plan.dispose`, left as is.
- [X] T018 (delta) Test in `tests/test_dispatch.py`
  `test_a_corrupt_proposal_refuses_the_planned_items_only`: a corrupt `proposal.json` gives each
  planned item a `refused` entry and the set still returns the gate and build entries. Implement in
  `cli/wuwei/dispatch.py` `launch_set`: `_start` runs per item inside its own try, so a ValueError
  refuses that item only instead of making `dispatch next --all` exit 2.
