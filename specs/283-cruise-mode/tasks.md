# Tasks: Cruise mode

Test first: each test task runs and fails for the expected reason before its implementation
task. Fixtures are neutral (`VALID`, `record()`, `LEAD` from `tests/test_decision.py` and
`tests/test_decision_classes.py`; items `DIV-1`..). New tests go in `tests/test_cruise.py`
unless a task names another file. Run `python -m pytest -q` from the repository root.

## Phase 1: config and running level (FR-001 to FR-003, US3)

- [X] T001 Test in `tests/test_cruise.py`: defaults `margin 0.2`, `max_per_day 20`,
  `undo_minutes 60`, `promote_agreements 10`, `promote_days 14`; the US3.3 values load;
  `margin = 0` and `1.5` raise `ConfigError` naming `decisions.cruise.margin`; `wuwei config
  check` exits 1 for `[decisions.cruise.levels] message = 2` naming `above its ceiling L1`
  (US3.1); `decision lint` of `record(cls='autopilot')` exits 1 with `Class: expected one of`
  (US3.2). Replace the margin row in `tests/test_workspace.py:1132` with an out-of-range
  margin.
- [X] T002 Implement the five keys and the margin range check in `cli/wuwei/workspace.py`.
- [X] T003 Test: `decision.running` returns empty levels without the file and raises with
  `DAMAGED` for invalid JSON, an unknown class, a string level and a symlink;
  `decision.level` table: default, running raised (capped by ceiling and configured level),
  configured lower, `enabled = false` gives 0, supervised gives 0.
- [X] T004 Implement `running` and the new `level` in `cli/wuwei/decision.py`; pass
  `decision.running(root)` in `cli/wuwei/brief.py:mandate`. Existing `tests/test_brief.py`
  mandate tests pass.
- [X] T005 Test: `promotion.cruise_level` writes `cruise.json` (`levels`, `changed`) and one
  ledger line (target, action `raise`/`lower`, status `landed`, reason, evidence); refuses
  an unknown class and a level above the ceiling; a proposal file in
  `days/<date>/proposals/` targeting `.wuwei/memory/cruise.json` is `rejected` by `wuwei
  promote` (in `tests/test_promotion.py` style, PATH git stub).
- [X] T006 Implement `promotion.cruise_level` and the `_target` rejection in
  `cli/wuwei/promotion.py`.
- [X] T007 Test in `tests/test_protect_state.py`: a Write or Edit to
  `.wuwei/memory/cruise.json` and a Bash redirect into it are refused (hook-level payloads);
  `tests/test_guard_mutation.py` gains the case if it enumerates protected names.
- [X] T008 Implement the protected name in `cli/wuwei/guards/protect_state.py`.

## Phase 2: the cruise answer (FR-004, FR-005, US1.1, US2, US5.1)

- [X] T009 Test (US1.1): `defer` at L2 via `promotion.cruise_level`; `record(cls='defer',
  radius='workspace')` routes to `mandate`; record text `Decided-by: cruise defer@L2`,
  `Outcome: A`; outcome row fields and the event payload as US1.1; no route; a second route
  writes nothing.
- [X] T010 Test (conditions): each single failing condition gives a plain `mandate` answer
  (no `rule`): class at L0 (default `defer`), `Class: merge`, no `Class:`, blast radius
  `item DIV-1`, margin 0.18 (`BELOW` with the record otherwise clear), `max_per_day = 0`, a
  record naming an item with goal `unplanned`; `enabled = false` (US5.1); a `retry` record on
  `own branch` with the `VALID` margin is `cruise retry@L2` (default level).
- [X] T011 Test (lint): `Decided-by: cruise defer@L2` and `cruise merge@L3` lint clean;
  `cruise defer@L1`, `cruise unknown@L2` and `cruise` are refused.
- [X] T012 Implement `cli/wuwei/cruise.py:rule`, the lint value in `decision.evaluate`, the
  `class` field in `seat_outcome`, and the cruise branch in
  `cli/wuwei/commands/decision.py:mandate`.
- [X] T013 Test (US2.1, US2.3): `LEAD` on the `defer@L2` workspace record prints `owner`;
  the route row and `decision.routed` payload carry `class: defer`, `thin: true`, `at`; the
  `approach` own-branch `LEAD` record prints `mandate` with `Decided-by: mandate`.
- [X] T014 Test (US2.2): three thin `defer` routes today lower `defer` to L1 with reason
  `three thin-margin escalations`; the fourth does not lower again; a cruise answer between
  thin routes resets the streak.
- [X] T015 Implement `route_owner(..., thin=False)` fields in `cli/wuwei/decision.py`,
  `cruise.thin`, `cruise.lower`, `cruise.streak` and their calls in `decide()`.
- [X] T016 Test: `closing` collects a cruise `park` answer's disposition (record
  `Decided-by: cruise park@L2`, `Outcome: parked DIV-1`) as it does for mandate.
- [X] T017 Implement the `closing.py:194` comparison.

## Phase 3: notify and undo (FR-006 to FR-010, US1.2 to US1.6, US6)

- [X] T018 Test (US1.2): `wuwei nudges` first line for an open window; the row is absent
  after `undo_until`; `decision show D-3 --widget` prints the Keep/Undo widget inside the
  window and `[]` after it and for an L3 answer.
- [X] T019 Implement the `decision.cruise` row and sort in `cli/wuwei/commands/status.py`,
  the `ACTIONS` row in `cli/wuwei/commands/nudges.py`, and the widget branch in
  `commands/decision.py:show`.
- [X] T020 Test (US1.4 to US1.6): undo with the host confirmation monkeypatched (as
  `test_owner_reverses_a_mandate_decision`): state, record text, event and the L1 level with
  ledger reason `undo D-3`; `--answer Keep` writes nothing; closed window and no window exit 1
  with the FR-006 messages; a declined confirmation exits 1; the undone record then takes an
  owner answer through `wuwei decide`.
- [X] T021 Implement `undo` and its parser in `cli/wuwei/commands/decision.py`.
- [X] T022 Test (US1.3, DM): `listen.notify` with a fake transport sends the cruise line once
  and writes `decision.notified`; `remote.handle` with the pinned owner DM text `undo D-3`
  runs the undo (`where` in the owner DM) and replies; the sent text passes the outward lint.
- [X] T023 Implement `listen.notify`, `remote.parse`/`handle` and the vocabulary line;
  `decision.notified` in `signal.SILENT` and `EVENT_PRODUCERS`.
- [X] T024 Test (US6) in `tests/test_decision_digest.py`: a mandate D-1 and a cruise D-2;
  the digest lists `- D-2: A (cruise defer@L2)` first.
- [X] T025 Implement the digest sort and line in `cli/wuwei/watch.py`.
- [X] T026 Test (US4.4): `wuwei decide D-3 B` on a cruise answer writes `decision.reversed`
  with `class` and lowers the class with reason `reversal D-3`; the same option keeps the
  level; the owner row carries `class` and `recommendation`.
- [X] T027 Implement `cruise.answered` (reversal branch) and the owner row fields in
  `owner_outcome`.

## Phase 4: promotion, sample and escaped defects (FR-011, FR-013, FR-014, US4)

- [X] T028 Test (US4.1 to US4.3): ten agreements in `defer` across neutral day directories
  (owner rows with `option == recommendation`, cruise rows with a past `undo_until`) make
  `cruise.propose` write one raise card, route it and store `cruise_cards`; `plan gate`
  prints it after the gate widget; nine agreements, a level change in the window, an
  existing raise card in the window, supervised or cruise off write nothing; a second
  `propose` the same day writes nothing new.
- [X] T029 Test (US4.2): `wuwei decide D-n raise` lands `defer` at L1 with ledger evidence
  `decisions/D-n.md`; `keep` changes nothing; a raise never exceeds the configured level.
- [X] T030 Implement `cruise.agreements`, `cruise.propose`, `cruise.gate_widgets`, the raise
  branch of `cruise.answered`, the `revisit` parameter of `grants._record`, the calls in
  `cli/wuwei/plan.py:propose` and `cli/wuwei/commands/plan.py` (gate), and
  `STATE_PRODUCERS['cruise_cards']` plus `EVENT_PRODUCERS['cruise.carded']` and
  `signal.SILENT`.
- [X] T031 Test (US4.6): a cruise answer in the last seven days and no sample card make
  `propose` write a sample card; its widget has record-order options without
  `(Recommended)`; an owner answer different from the cruise answer lowers the class with
  `weekly sample D-n`; the same answer keeps it; a second propose within seven days writes
  no sample.
- [X] T032 Implement the sample branch of `propose`, `record_widget(hidden=True)` and the
  sample branch of `cruise.answered`.
- [X] T033 Test (US4.5) in `tests/test_cruise.py`: a merged item named by a later builder
  brief and a `retry` cruise answer naming it make `cruise.escaped` lower `retry` once with
  `escaped defect DIV-1 D-n`; a second call does not lower again; `metrics` escaped-by-tier
  results are unchanged (existing tests).
- [X] T034 Implement `metrics._escaped`, `cruise.escaped` and the call in
  `steward.review`.

## Phase 5: status line, profiles, producers, docs (FR-009, FR-015 to FR-018, US5)

- [X] T035 Test (US5.2, US5.3): `status.line(status.snapshot(day))` ends `| cruise L2 |
  meeting unmeasured` by default, `cruise off | L2` when off, `cruise L3` with `defer` at L3,
  `cruise L0` under supervised; supervised routing of the US1 record matches #530; the seat
  mandate block under supervised lists every class as going to the owner; a damaged
  `cruise.json` makes status print `WUWEI ? unmeasured`.
- [X] T036 Implement `cruise.label` and the snapshot and line parts in
  `cli/wuwei/commands/status.py`.
- [X] T037 Test in `tests/test_profiles.py`: a profile lowering `decisions.cruise.margin` or
  raising `decisions.cruise.max_per_day` is refused.
- [X] T038 Implement the two `profiles.DENIED` rows.
- [X] T039 Test in `tests/test_state_allowlist.py`: add `('cruise_cards', 'wuwei plan
  propose')` to the state table and `('decision.notified', 'wuwei listen')`,
  `('cruise.carded', 'wuwei plan propose')` to the event table; the reader inventory test
  passes unchanged.
- [X] T040 Test in `tests/test_docs.py`: replace `test_cruise_mode_is_designed_not_built`
  with a test that README "What ships today", `concepts.md`, `configuration.md`, `daily.md`
  and `reference.md` describe cruise as shipped (no "not built" next to cruise),
  `configuration.md` names the five new keys, `daily.md` names `decision undo` and `cruise
  off`, `reference.md` has a `decision undo` row.
- [X] T041 Update `docs/site/daily.md`, `docs/site/reference.md`,
  `docs/site/configuration.md`, `docs/site/concepts.md`, `README.md` and
  `templates/workspace/config.toml`.
- [X] T042 (skipped: tests/test_invariants.py is absent on this base) If `tests/test_invariants.py` exists on the base at build time: add rows for the
  cruise answer rule, the undo window, the level writer and the producer-only keys to the
  design section 9 invariant table and to that test. Otherwise skip and note it.
- [X] T043 Run the full suite; check every written file for em-dashes and emojis.
