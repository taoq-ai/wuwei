# Tasks: Error budget per decision class

Test first: each test task runs and fails for the expected reason before its implementation
task. Fixtures are neutral (classes from design 5.8.1, items `DIV-1`.., records `D-n`).
New tests go in `tests/test_budget_classes.py` unless a task names another file; import the
helpers of `tests/test_cruise.py` (`config`, `ledger`, `later`, `raise_to`, `agree`,
`propose`, `answer`, `status_line`, `undo`) and `tests/test_decision_classes.py` (`ws`,
`record`, `route`). A small local helper `answers(root, cls, count, start)` writes `count`
cruise `decision.decided` events (payload `id`, `option`, `class`, `rule: cruise <cls>@L2`,
`items`, `decided_by`) and `reverse(root, ident, undo=False)` writes the matching
`decision.reversed`, both through `state.append_event` under the current `WUWEI_NOW`.

## Phase 1: config (FR-008)

- [X] T001 Test: defaults `budget_share == 0.1`, `budget_window_days == 14`,
  `burn_warn == 2.0`; a config with `budget_share = 0.3` loads; `0.6`, `0.0` and `-0.1`
  raise `ConfigError` naming `decisions.cruise.budget_share`; `budget_window_days = 0`
  raises; `wuwei config check` exits 1 on `budget_share = 0.6`. In `tests/test_docs.py`
  `test_cruise_mode_ships`, add `budget_share`, `budget_window_days` and `burn_warn` to the
  key loop; both tests fail.
- [X] T002 Implement the three keys in `SCHEMA` and the share check in
  `cli/wuwei/workspace.py`; add the commented lines to `templates/workspace/config.toml` and
  the three rows to `docs/site/configuration.md` (`test_every_template_config_key_is_documented`
  and `test_cruise_mode_ships` go green).

## Phase 2: the reader and the rule (FR-001, FR-002)

- [X] T003 Test `measure`: (20, 3, 0) is `spent` with allowance 2.0; (20, 2, 2) is `warn`
  with burn 7.0; (20, 0, 0) is `ok` with burn 0.0; (5, 1, 0) is `ok` (fewer than two
  events); (5, 2, 0) is `spent`; (0, 1, 1) has burn `inf` and is `warn`; (0, 0, 0) is `ok`.
- [X] T004 Implement `measure` in `cli/wuwei/budget_classes.py`.
- [X] T005 Test `select`: under `WUWEI_NOW` on two days, a cruise answer and a plain
  `mandate` answer; an undo of one cruise answer, an owner reversal of another, an owner
  reversal of the plain mandate answer (not counted); a `cruise.carded` sample card naming
  a cruise answer's source and its owner answer with another option (counted as `sample`
  of the sampled class), and a second sample answered the same (not counted); an answer
  naming `DIV-1` with `metrics._escaped` monkeypatched to escape `DIV-1` (counted as
  `escaped`); an answer older than the window (dropped). Assert the answers, each event's
  kind, class, day, id and label. A day with an incomplete event line raises `ValueError`.
- [X] T006 Implement `select` in `cli/wuwei/budget_classes.py`.
- [X] T007 Test `table`: one row per class but `merge`; `defer` raised to L2 with 20
  answers and 3 reversals reads level 2, answered 20, spent 3, allowance 2.0, state
  `spent`, three labels, `held` false; other classes `ok` with zeros.
- [X] T008 Implement `table`.

## Phase 3: the promote writer hold (FR-003)

- [X] T009 Test in `tests/test_cruise.py`: `promotion.cruise_level(..., hold=2)` writes
  `budget: {defer: 2}` beside the level; a later write without `hold` removes the key and
  the file is back to `{levels, changed}`; `cruise.running` refuses a `budget` entry with an
  unknown class or a level outside 0..3 with `DAMAGED`.
- [X] T010 Implement `hold` in `cli/wuwei/promotion.py` `cruise_level` and the `budget`
  shape check in `cli/wuwei/cruise.py` `running`.

## Phase 4: the steward evaluation (US1, US2, US3; #558 acceptance 1 to 3)

- [X] T011 Test acceptance 1: `defer` at L2, 20 answers and 3 reversals in the window;
  `budget_classes.evaluate(ws)` leaves `defer` at L1, `running['budget'] == {'defer': 2}`,
  and the last ledger line is a `lower` whose reason starts `budget spent: defer` and names
  the three labels. A second `evaluate` writes no new ledger line. With 2 reversals the
  level stays 2 (US1 scenario 2); with 5 answers and 1 reversal it stays 2 (scenario 3).
- [X] T012 Test acceptance 2: after T011's state, move `WUWEI_NOW` 15 days on with no new
  event; `evaluate` restores `defer` to L2, removes the hold, and the last ledger line is a
  `raise` whose reason starts `budget refilled: defer back to L2`.
- [X] T013 Test acceptance 3: 20 answers and 2 reversals inside 48 hours; `evaluate` writes
  one `cruise.burn` event naming both labels with a `reason`; the level is unchanged; a
  second `evaluate` the same day writes no second event; `wuwei nudges` prints a line
  ending `Run: wuwei cruise budget`.
- [X] T014 Test: a spent class at L0 (cruise default for `defer`) is not lowered, not held
  and writes no ledger line.
- [X] T015 Test in `tests/test_signal_status.py`: add `'cruise.burn': 'nudge'` to the
  expected map; it fails (`cruise.burn` is not emitted by any writer yet).
- [X] T016 Implement `evaluate` in `cli/wuwei/budget_classes.py`; add `cruise.burn` to
  `EVENT_PRODUCERS` in `cli/wuwei/commands/event.py` and to `ACTIONS` in
  `cli/wuwei/commands/nudges.py`. T011 to T015 go green.
- [X] T017 Test: `steward.review(ws)` calls `budget_classes.evaluate` with the root
  (replaces `test_the_steward_review_checks_escaped_defects` in `tests/test_cruise.py`).
- [X] T018 Implement: `cli/wuwei/steward.py` `review` calls `budget_classes.evaluate(root)`
  in place of `cruise.escaped(root)`.

## Phase 5: single triggers removed (US6, FR-004)

- [X] T019 Test in `tests/test_cruise.py`: rewrite `test_undo_reverts_the_answer_and_lowers_the_class`
  (undo keeps the record flow, level stays 2, no new ledger line),
  `test_the_owner_reversing_a_cruise_answer_lowers_the_class` (level stays 2),
  `test_weekly_sample_card` (a different sample answer leaves `retry` at its level and
  `select` counts one `sample` event), `test_three_thin_escalations_lower_the_class` (level
  stays 2 after the third thin route; the route rows still carry `thin: true`),
  `test_an_escaped_defect_lowers_the_class_once` (level unchanged; `select` counts one
  `escaped` event), each renamed to what it now asserts; add a check that `cruise` has no
  `lower`, `streak` or `escaped` attribute.
- [X] T020 Implement: delete `lower`, `streak`, `escaped` and the two `answered` branches in
  `cli/wuwei/cruise.py`; drop `previous` from `answered` and its call in
  `cli/wuwei/commands/decision.py` `owner_outcome`; delete the `cruise.streak` call in
  `decide` and the `cruise.lower` call in `undo`.

## Phase 6: promotion gate (US4, #558 acceptance 4, FR-005)

- [X] T021 Test: 10 agreements (`agree`) for `defer` and a spent budget (answers and
  reversals as in T011 with `defer` at its default) give `propose(ws) == []` with no raise
  card; 10 agreements and one reversal of `defer` after its last change (budget unspent:
  20 answers, 1 reversal) give no raise card; 10 agreements alone still give one (the
  existing `test_ten_agreements_propose_a_raise` stays green).
- [X] T022 Implement the skip in `cli/wuwei/cruise.py` `propose` and the raise card text.

## Phase 7: command and status line (US5, FR-006, FR-007)

- [X] T023 Test: `main(['cruise', 'budget'])` prints a header and a row per class but
  `merge`; with T011's events it exits 1 and the `defer` row ends `spent`; with no events it
  exits 0; a damaged `events.jsonl` today exits 2 with `wuwei cruise budget:` on stderr;
  `commands.read_only(['cruise', 'budget'])` is true.
- [X] T024 Implement `cli/wuwei/commands/cruise.py`, `'cruise budget'` in `READ_ONLY`
  (`cli/wuwei/commands/__init__.py`) and `cruise` in the Owner group of `GROUPS`
  (`cli/wuwei/__main__.py`); add the `bin/wuwei cruise` row to `docs/site/reference.md`
  (`test_reference_lists_every_cli_command`).
- [X] T025 Test: with `budget: {defer: 2}` in `cruise.json`, `status_line(ws)` contains
  `cruise L2 · budget defer spent`; with two held classes they are joined by `, ` in sorted
  order; without a hold the cruise part is unchanged (`test_the_status_line_names_the_cruise_level`
  stays green).
- [X] T026 Implement the budget part in `cli/wuwei/cruise.py` `label`.

## Phase 8: invariant, design and docs (FR-010)

- [X] T027 Test in `tests/test_invariants.py`: add `i11` and `'I11'` to `INVARIANTS`;
  `test_table_matches_the_checks` fails until the design row exists.
- [X] T028 Implement the 9.2 row `I11` and the 5.8.1 "Error budget" amendment in
  `docs/specs/2026-09-24-wuwei-design.md`.
- [X] T029 Docs: `docs/site/concepts.md`, `docs/site/daily.md`, `docs/site/configuration.md`
  paragraph, `README.md` line 38, as named in the plan. Run `tests/test_docs.py`.

## Phase 9: verify

- [X] T030 Run the focused files (`tests/test_budget_classes.py`, `tests/test_cruise.py`,
  `tests/test_invariants.py`, `tests/test_signal_status.py`, `tests/test_docs.py`,
  `tests/test_guide.py`, `tests/test_cli_known_command.py`), then the full suite in the
  background to a file; check every written file for em-dashes and emojis.
