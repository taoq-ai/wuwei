# Tasks: No fast checks is a state, not a wall

Test first: each test task is written, run and seen failing for the expected reason before
its implementation task. Fixtures are neutral: repository `acme/paper` (no code) and
`acme/widget`, items `P1` and `P2`, records `D-1` and up. Set `WUWEI_NOW`; build workspaces
with the existing fixtures of each test file (`tests/test_build_next.py`, the `day_set`
pattern of `tests/test_dispatch.py`, `ws` and `config_card` of
`tests/test_card_confirms.py`, `save` of `tests/test_decision.py`). Simulate a card answer
the way `tests/test_card_confirms.py` does (`answer(root, 'D-1', question, label)`). Run
only the touched test files, in the foreground.

## Phase 1: the wall (US1, FR-001, FR-002, FR-012)

- [X] T001 Test in `tests/test_build_next.py`: a repository with `fast_checks = []`, a
  planned item with a logged builder brief and worktree, posture observe and guarded:
  `build.next_action` returns the launch action (no ValueError), the build record has
  `commands == []`, and the `build.started` event payload has `checks: "none configured"`.
  (The strict case is T023.)
- [X] T002 Test in `tests/test_dispatch.py`: with the real `build.next_action` (not the
  `day_set` stub) and `fast_checks = []` under observe, `dispatch.launch_set` gives the
  briefed planned item a `launch` entry and no entry is `refused`.
- [X] T003 Test in `tests/test_build_next.py`: with `commands == []`, `build.check(item)`
  records `{}` evidence, completes with exit 0 and moves the item to `gate` (pins the
  existing path); `build.stopped` with a clean worktree does the same.
- [X] T004 Test in `tests/test_commit_push.py`: `fast_evidence` on a repository with
  `fast_checks = []` returns `(0, '')` at every pace (pins the existing rule).
- [X] T005 Implement in `cli/wuwei/commands/build.py`: `_repo` keeps the refusal only under
  strict (T024 narrows it to an unanswered card); `next_action` passes
  `{'checks': 'none configured'}` to the `build.started` save when the list is empty.

## Phase 2: naming the state (US1.3, US2, FR-003, FR-004)

- [X] T006 Test in `tests/test_brief.py`: a builder brief for an item of a repository
  with `fast_checks = []` and no `repos.tests` carries the header line
  `Fast checks: none configured; CI and the gates are the evidence. Write "checks: none
  configured" in the PR body.` at steady, careful and fast pace and no `Checks:` pace
  line; with `repos.tests` set at careful pace the line is absent and the careful line is
  present; a repository with fast checks has neither the none line nor a change.
- [X] T007 Implement in `cli/wuwei/fast_checks.py` (`NONE`) and `cli/wuwei/brief.py`
  (builder header reads `fast_checks.commands`).
- [X] T008 Test in `tests/test_doctor.py`: change the `fast_checks` case of
  `test_workspace_repository_rows` to status `ok`, no `apply`, value
  `fast_checks.NONE`, and drop its `fix` assertions; a repository with checks keeps its
  `ok` row listing them.
- [X] T009 Implement in `cli/wuwei/commands/doctor.py`.
- [X] T010 Test in `tests/test_signal_status.py`: `status.snapshot` (non-line) lists
  `acme/paper` under `checks_none`; `status.full` shows
  `acme/paper fast checks: none configured; CI and the gates are the evidence`; with
  `line=True` the key is absent; a repository with checks is not listed.
- [X] T011 Implement in `cli/wuwei/commands/status.py`.

## Phase 3: Value rows and config cards (US4, FR-007, FR-008)

- [X] T012 Test in `tests/test_decision.py`: a new record titled `Detected`, `None`,
  `Defer` with a `Value:` table (`A` -> `repos.0.fast_checks = ["make test",
  "markdownlint ."]`, `B` -> `repos.0.fast_checks = []`) and
  `Previous: repos.0.fast_checks = []` passes `decision.lint` with the lens table;
  `decision.values` returns the two cells; `decision.config_keys` returns
  `{'repos.0.fast_checks': ...}` for that record and `{'cap': 5, ...}` for the #529
  `CONFIG_RECORD` of `tests/test_card_confirms.py`; a Value row naming option `Z`, key
  `nope.key`, value `[make test` or a `Previous:` spanning two lines is rejected with the
  reason. A history read (`evaluate(text)` without lenses) of a record without the fields
  is unchanged.
- [X] T013 Implement in `cli/wuwei/decision.py` (`OPTIONAL`, one-line `Previous`,
  `values`, `config_keys`, `_explained` checks).
- [X] T014 Test in `tests/test_card_confirms.py`: a Value-row card routed and answered
  `Detected` in the planner session: `config set --from-card D-1` (no KEY, no VALUE)
  writes `fast_checks = ["make test", "markdownlint ."]` to `repos.0`, no host prompt runs
  (`integrity._host_confirm` raises if called), the owner outcome is `A` and one
  `config.set` event names `D-1`; given KEY and VALUE equal to the Value row it writes the
  same; a different value exits 1 and writes nothing; answered `Defer`, it records the
  owner outcome `C`, writes nothing, prints `No config.toml changes` and exits 0; the #529
  card answered `Keep the current cap` does the same; `config set --from-card D-1` on the
  #529 card answered `cap = 5` writes `cap = 5`. `config set` with no KEY and no
  `--from-card` exits 2 naming both forms. Update
  `test_widget_of_a_config_record_prints_the_config_command` to expect
  `wuwei config set --from-card D-1`, and add the same for a Value-row card. The session
  hint without a card names `Value:` rows and prints a `Previous:` line with the key's
  current value. Through `protect_state` from the planner session after the card answer,
  `bin/wuwei config set --from-card D-1` passes and from a seat it is refused (no hook
  change; pins I8 for the short form).
- [X] T015 Implement in `cli/wuwei/commands/config.py` (optional KEY and VALUE),
  `cli/wuwei/commands/setup.py` (`set_value`, `_from_card`, the hint) and
  `cli/wuwei/commands/decision.py` (`CONFIG_RECORD`, `show --widget` on `config_keys`).

## Phase 4: two-way config records (US5, FR-009, FR-010)

- [X] T016 Test in `tests/test_undo.py`: `undo.config_write` is True for the T012 record
  and for a #529 title record with `Previous: cap = 1`, False without `Previous` or when
  `Previous` names another key; `undo.measured` returns `('config', None)` for it with an
  empty ledger; `undo.correct` on its first route rewrites `Reversibility: one-way` (and
  `unsure`) to `two-way` and `Class: other` (and a missing Class) to `approach`, adds the
  Notes line and returns the report line; `Class: design` stays `design` with the door
  corrected; a record without `Previous` is untouched; a second route changes nothing.
- [X] T017 Test in `tests/test_decision.py` and `tests/test_card_confirms.py`: under
  autonomous and observe, `decision route D-1` on the T012 record written `one-way` and
  `other` stores `two-way` and `approach`, routes to the owner (not `mandate`), and
  `decision.cisr` on the stored fields is `Routine`; `decision lint` on the file reports
  the correction line and exits 0; the #529 `CONFIG_RECORD` under autonomous routes to the
  owner, and `decision show D-1 --widget` prints its card (not `[]`).
- [X] T018 Implement in `cli/wuwei/undo.py` (`config_write`, `measured`, `correct`),
  `cli/wuwei/decision.py` (`lint` line) and `cli/wuwei/commands/decision.py` (`mandate`
  skip).

## Phase 5: detection and the proposal (US3, FR-005, FR-006)

- [X] T019 Test in `tests/test_calibrate.py`: `toolchain` on a checkout with
  `.markdownlint.json` yields fast check `markdownlint .` and `classify` calls it fast;
  with `.latexmkrc`, `latexmk` (unmeasured); a symlinked `.markdownlint.json` yields
  nothing; with only `.github/workflows/ci.yml` on `pull_request` whose `test` job runs
  `pip install -r requirements.txt` then `python3 -m pytest -q`, it yields
  `python3 -m pytest -q` only; with a Makefile `test:` target the workflow step is not
  read; a `run: |` block and a job named `deploy` yield nothing.
- [X] T020 Implement in `cli/wuwei/calibrate.py` (`LINT`, `toolchain`, `_workflow` runs,
  `TEST_STEP` with its `ponytail:` comment).
- [X] T021 Test in `tests/test_calibrate.py`: `checks_text` for detected `["make test"]`
  and for nothing passes `decision.evaluate` with the lens table, recommends `A`, has
  Class `approach`, two-way, high, the Value rows and the Previous line, and its Context
  names `Makefile:1` or the `NOTHING` reason; `grants._record` with no keywords returns
  text byte-identical to today's for a fixed input; `checks_record` finds the newest
  record on a live day and ignores another repository's; `checks_answered` is True only
  with an owner outcome in that day's state.
- [X] T022 Implement in `cli/wuwei/grants.py` (`_record` keywords) and
  `cli/wuwei/calibrate.py` (`CHECKS`, `NOTHING`, `checks_text`, `checks_record`,
  `checks_answered`).
- [X] T023 Test in `tests/test_build_next.py`: under strict with no answered fast-checks
  record, `build.next_action` on the `acme/paper` item raises naming
  `wuwei calibrate --questions --repo acme/paper`; after a fast-checks record for
  `acme/paper` is routed and its owner outcome recorded (any option), it launches; a
  seat-written record with `Decided-by: owner` and no state outcome does not clear it.
- [X] T024 Implement in `cli/wuwei/commands/build.py`: `_repo` under strict refuses only
  while `calibrate.checks_answered(root, name)` is False, with the reason above.
- [X] T025 Test in `tests/test_card_confirms.py` (it has `ws`, `main` and the card
  helpers): `calibrate --questions` under autonomous and observe on `acme/paper` with
  `fast_checks = []` and a Makefile `test:` target writes one record decided by
  `mandate` (record Outcome `A`, `decision_outcomes[D-n]['decided_by'] == 'mandate'`),
  writes `fast_checks = ["make test"]`, appends one `config.set` event naming `D-n`, prints
  `calibrate: D-n taken under mandate (Routine): repos.0.fast_checks = ["make test"]` on
  stderr, prints no widget for it and exits 0; with no runner it records `None`, leaves
  config unchanged and names the reason in the record; a second run writes no second
  record; under supervised the record is in `decision_routes`, the widget list carries its
  card with record `wuwei config set --from-card D-n`, and config is unchanged; with
  `--questions cap` no record is written; a missing checkout prints one stderr line and
  still prints the other widgets; the digest of that day lists the record (`digest.build`).
- [X] T026 Implement in `cli/wuwei/calibrate.py` (`propose_checks`) and
  `cli/wuwei/commands/calibrate.py` (`_interview`).

## Phase 6: invariants and docs (FR-011)

- [X] T027 Test in `tests/test_invariants.py`: add `i25`, `i26`, `i27` as in plan section
  7, register them in `INVARIANTS` and `READS` (`(0,)`, `(0,)`, `()`), and add one
  `BROKEN` entry per row (a `_repo` that always raises; a `_from_card` that calls the host
  prompt; a `correct` that keeps `one-way`) so `test_broken_rule_is_caught` shows each
  check bites. Run it: `test_table_matches_the_checks` fails until T028.
- [X] T028 Docs: design 9.2 rows I25 to I27 and the I22 note; design 5.2 Records (#529
  paragraph); `skills/wuwei-plan/SKILL.md` record command and Value rows;
  `docs/site/configuration.md` (the none state and the daily card) and
  `docs/site/recovery.md` (the `fast_checks = []` entry keeps `bin/wuwei config promote`).
  Run `tests/test_docs.py` and `tests/test_invariants.py`.
- [X] T029 Run every touched test file listed in `plan.md`; check the diff for em-dashes,
  emojis and absolute local paths.

## Phase 7: review fixes

- [X] T030 Review F1: a CI `run:` line with a shell control or expansion character is never
  proposed (`calibrate.toolchain`); test `test_detector_refuses_a_chained_ci_run_line`.
- [X] T031 Review F2: `shepherd.raise_pr` appends `checks: none configured` to the PR body
  when the repository has no fast checks; tests in `tests/test_shepherd.py`.
- [X] T032 Review F3: `build next` records `fast_checks.commands` when `fast_checks = []`, so
  careful pace with `repos.tests` still checks the tests; test in `tests/test_build_next.py`.
