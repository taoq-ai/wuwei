# Tasks: One setup question for autonomy, the interview on upgrade, and the harness allowlist card

Test first: each test task is written and run, and fails for the expected reason, before its
implementation task. Fixtures are neutral (`example/project`, `other/elsewhere`). Run only the
touched test files (plan.md, "Test files to run"), never the full suite.

## Phase 1: the merge default (US2; FR-005, FR-006)

- [X] T001 Test in `tests/test_grants.py`: `workspace.load_config` accepts
  `[merge]\ndefault_tier = "today"`; with it and one configured repository, `grants.active`
  returns `('today', 'merge.default_tier')` for `merge` on `repo:example/project` and
  `pr:example/project#7` under observe and guarded, and `None` for `repo:other/elsewhere`,
  for `deploy`, `release`, `publish` and `evidence` on the configured repository, under
  strict, with `close_requested` set, and when a grant row for that target is answered `keep`.
  A recorded `once` or `today` row still wins with its own D-n.
- [X] T002 Implement `"today"` in `cli/wuwei/workspace.py` (`SCHEMA['merge']`) and `DEFAULT`
  plus the default branch in `grants.active` (`cli/wuwei/grants.py`).
- [X] T003 Test in `tests/test_merge.py`: under `merge.default_tier = "today"`, a merge the
  policy does not clear on the configured repository passes `merge.by_grant` with no card
  (no `grant.asked` event, no decision file) and one `grant.used` event whose payload has
  `decision: merge.default_tier` and `scope: today`; `merge_deploys = true` is still refused
  by `check`.
- [X] T004 Make T003 pass (no code beyond T002 expected; fix only what the test shows).
- [X] T005 Test in `tests/test_grants.py` (or `tests/test_plan.py` where planned cards are
  tested): `grants.plan` with a lead entry `{'action': 'merge', 'target':
  'repo:example/project'}` and the default writes no decision and no grant row and returns
  `{item: [('merge', 'repo:example/project', 'merge.default_tier')]}`; a `deploy` entry still
  writes its card.
- [X] T006 Implement the skip in `grants.plan` (`cli/wuwei/grants.py`).

## Phase 2: the autonomy question (US1; FR-001 to FR-004)

- [X] T007 Test in `tests/test_interview.py`: the table ids start with `autonomy`, end with
  `allowlist` and no longer hold `posture`, `tier`, `learn` (update
  `test_question_table_fits_widgets_and_every_choice_validates`, allowing the `allowlist`
  effect key); `settings({'autonomy': 'Autonomous'}, config)` returns exactly the five FR-001
  rows and no `shadow_since` row, `Supervised` the other five; no other row's effects name
  one of the five keys; `card_for('security.posture')`, `card_for('outbound.default_tier')`
  and `card_for('merge.default_tier')` are `None`, `card_for('host.seats') == 'seats'`. Port
  `test_workspace_rows_for_the_day_keys` and `test_observe_answer_sets_the_start_day` to the
  autonomy row.
- [X] T008 Implement the `autonomy` row, remove `posture`, `tier`, `learn`, drop the
  `shadow_since` lines in `settings` and skip `autonomy` in `card_for`
  (`cli/wuwei/interview.py`). Check `tests/test_docs.py::test_interview_options_lead_with_plain_words`.
- [X] T009 Test in `tests/test_card_confirms.py`: acceptance 1 of the item. Fresh workspace,
  the autonomy card answered Autonomous from `planner-1`, `calibrate --answer
  autonomy=Autonomous` exits 0, the config holds observe, send, today, auto, autonomous,
  `guards.shadow_since` is empty, and one `config.set` event names the five keys and card
  `autonomy`; Supervised gives guarded, ask, ask, card, supervised. Port the `tier` and `learn`
  cases of `test_calibrate_answer_writes_the_card_answer` and the `posture=Observe` lines of
  `test_unrelated_gate_question_with_the_header_confirms_nothing` to `autonomy`.
- [X] T010 Make T009 pass (the #529 path is reused; fix only what the test shows).
- [X] T011 Test in `tests/test_setup.py`: port `test_shadow_skips_the_posture_question` and
  `test_shadow_records_posture_answer` to `autonomy` / `Autonomous` (with `--shadow` the row
  is not asked and the answer is recorded; posture observe and `shadow_since` set by the flag).
- [X] T012 Implement the `autonomy` replacements in `cli/wuwei/commands/setup.py` (`_setup`).

## Phase 3: the interview on upgrade (US3; FR-007 to FR-009)

- [X] T013 Test in `tests/test_interview.py`: `interview.unanswered(root, ['example/project'])`
  on a workspace with no answers returns every row once (the repository rows once for
  `example/project`) with `autonomy` first; an earlier day's `interview.json` holding
  `{'cap': '2', 'posture': 'Observe'}` removes `cap` and nothing else; `repos=[]` drops the
  repository rows; `widgets(root, repos)` returns the same ids in the same order.
- [X] T014 Implement `HOW`, `unanswered` and the `widgets` change (`cli/wuwei/interview.py`).
- [X] T015 Test in `tests/test_workspace.py`: acceptance 2 of the item for init. A workspace
  with day directories for five days, one repository and no answers: `init --upgrade` prints
  `setup: N questions unanswered: bin/wuwei setup, or the planner asks them on cards` with N
  equal to `len(interview.unanswered(...))`; after every row is answered in an
  `interview.json` the line is absent. Add `setup:` to the line filter of the two
  exact-output asserts.
- [X] T016 Implement the line in `init.upgrade` (`cli/wuwei/commands/init.py`).
- [X] T017 Test in `tests/test_doctor.py`: the same workspace gives the `interview` row
  `warn`, value `N questions unanswered`, fix `bin/wuwei setup, or the planner asks them on
  cards`; all answered gives `ok` `all setup questions answered`; a damaged `interview.json`
  gives `unmeasured`.
- [X] T018 Implement the row in `doctor._calibration` (`cli/wuwei/commands/doctor.py`).
- [X] T019 Test in `tests/test_next.py`: on day 5 (earlier day directories present), after the
  gate and goals, `wuwei next --json` returns `calibrate` / `card` with a widget list whose
  first id is `autonomy`; after `ran` of its command the next row follows; with every row
  answered the widget list is `[]` and the row passes in the same call (as telemetry does); its `then` says to show the
  printed `Next:` line. Update the day-one comment and the `config promote` assert of
  `test_cards_after_the_gate_come_once`. `tests/test_hooks.py::test_calibrate_is_off_every_hook_path`
  passes unchanged.
- [X] T020 Implement the `next.step` row and `THEN['calibrate']` (`cli/wuwei/commands/next.py`).

## Phase 4: the harness allowlist card (US4; FR-010 to FR-012)

- [X] T021 Test in `tests/test_workspace.py` (init helpers): `init.allow_rules(config,
  'bin/wuwei')` with the default adapters starts with `Bash(bin/wuwei
  *)` and holds the git and gh rules of plan.md; with `vcs` and `code_host` set to `none` it
  holds only the executable rule; no rule matches (fnmatchcase on the text inside `Bash(...)`)
  any `PERMISSIONS_DENY` command stem, `git push origin main`, `git push --force`,
  `git push --tags`, `gh release create v1`, `gh pr merge 1 --admin` or
  `gh api repos/o/r/releases`. `init.allow(root)` on a project with a
  `.claude/settings.local.json` holding another key and one rule adds exactly the missing
  rules, keeps the rest, returns the added ones, and a second call adds none; a symlinked
  file is refused with exit-2 reason text; a non-list `permissions.allow` is refused.
- [X] T022 Implement `settings(root, name)`, `ALLOW`, `allow_rules` and `allow`
  (`cli/wuwei/commands/init.py`).
- [X] T023 Test in `tests/test_card_confirms.py`: acceptance 3 of the item. The allowlist card
  answered Allow, `calibrate --answer allowlist=Allow` writes `.claude/settings.local.json`
  with exactly `allow_rules(...)`, prints each rule, writes no config key and prints no
  `config promote` line; `Not now` writes nothing; Allow without the card answer, or under
  strict, writes nothing and prints `Next: run bin/wuwei calibrate --interview allowlist in a
  host terminal`. In `tests/test_interview.py`: the Allow description holds the one line on
  production reads, and `describe({'allowlist': 'Allow'}, config)` names
  `.claude/settings.local.json`.
- [X] T024 Implement the `allowlist` row, `_setting` and `describe` (`cli/wuwei/interview.py`)
  and the write in `calibrate._interview` (`cli/wuwei/commands/calibrate.py`).
- [X] T025 Test in `tests/test_setup.py`: setup with the terminal answering Allow writes the
  rules to `.claude/settings.local.json`; `Not now` leaves it absent.
- [X] T026 Implement the allowlist write in `setup._setup` (`cli/wuwei/commands/setup.py`).

## Phase 5: the invariant and the text (FR-013 to FR-015)

- [X] T027 Test in `tests/test_invariants.py`: `i18` (READS `(0,)`, posture) asserts, for the
  case's posture, that `grants.active` with `merge.default_tier = "today"` returns the default
  only for `merge` on a configured repository below strict, and that no `init.allow_rules`
  rule matches the publish samples of T021; `default_has_no_grant` also asserts the shipped
  `merge.default_tier == ''`. Add `I18` to `INVARIANTS` and `READS`. Run it and see
  `test_table_matches_the_checks` fail on the missing design row.
- [X] T028 Add row I18 and the I5 note to design 9.2 (`docs/specs/2026-09-24-wuwei-design.md`,
  nothing else there); update `docs/site/configuration.md` (line 3, the `merge.default_tier`
  row, the calibration paragraph). Run `tests/test_docs.py` and `tests/test_invariants.py`.
- [X] T029 Run the touched test files (plan.md list); check every written file for
  em-dashes, emojis and absolute local paths.
