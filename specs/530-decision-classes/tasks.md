# Tasks: Decision classes (MIT CISR) and fewer cards

Test first: each test task runs and fails before its implementation task. Fixtures are
neutral (records built from `tests/test_decision.py`'s `VALID` shape, items `DIV-1`..).
New tests go in `tests/test_decision_classes.py` unless a task names another file.

## Phase 1: the key and the class (FR-001 to FR-003, FR-009)

- [X] T001 Test in `tests/test_decision_classes.py`: a fresh workspace config has
  `autonomy.mode == 'autonomous'`; `supervised` loads; any other value is a config error.
- [X] T002 Implement the `autonomy` table in `cli/wuwei/workspace.py` (`SCHEMA`) and the
  `[autonomy]` block in `templates/workspace/config.toml`.
- [X] T003 Test: `decision.margin` returns the 5.8.1 margin for `VALID` and for a tie (0);
  `bin/wuwei why D-n` still prints the same `margin:` line (existing why test passes).
- [X] T004 Implement `decision.margin` in `cli/wuwei/decision.py` and use it in
  `cli/wuwei/commands/why.py` (`decided`).
- [X] T005 Test: `decision.cisr` table over Class (`retry`, `approach`, `park`,
  `accept-residual` give Routine even one-way, low confidence or tied), Reversibility
  (`two-way`, `one-way`, `unsure`), Blast radius (`item ...`, `Own branch and PR.`, `own PR`,
  `day`, `repository`, `outside`, free text) and ambiguity (Confidence `low`, margin below
  and at 0.2); each case gives the class FR-002 names.
- [X] T006 Implement `MARGIN`, `ROUTINE` and `cisr` in `cli/wuwei/decision.py`.
- [X] T007 Test: lint of a record with no `Recommendation:` line, with a blank one, and a new
  record with no `Reasoning:` each exits 1 with `add the recommendation and the reasoning`;
  lint of `VALID` prints `OK: A (<score>), Routine`; `Decided-by: mandate` lints clean.
  Update the five OK-line asserts in `tests/test_decision.py`.
- [X] T008 Implement the messages, the OK suffix and the `mandate` value in `evaluate`,
  `_explained` and `lint` (`cli/wuwei/decision.py`).

## Phase 2: who decides (US1, US2, US3; FR-004 to FR-008)

- [X] T009 Test (US1.1, US1.2): default config; `retry`, `approach` and `park` records with
  blast radius `item`; `decision route D-n` prints `mandate`; state outcome has
  `decided_by: mandate` and `cisr: Routine`; one `decision.decided` event with both; the
  record text has `Decided-by: mandate` and `Outcome: <recommendation>`; no
  `decision_routes` entry, no `decision.routed` event.
- [X] T010 Test (US2): Consequential (one-way, clear) prints `mandate`; Exploratory with a
  lead prints `mandate`; Exploratory tie on `item` prints `owner` and writes a route with
  `cisr: Exploratory`; the same tie on `own branch` with `Decided-by: seat` prints `seat`;
  Strategic (one-way, Confidence low) prints `owner` with `cisr: Strategic`.
- [X] T011 Test (US3): `[autonomy] mode = "supervised"`; the T009 records print `owner` with a
  route entry carrying `cisr: Routine` and no mandate outcome; a two-way `own branch` record
  with `Decided-by: seat` prints `seat` and its outcome carries `cisr`.
- [X] T012 Test (edge cases): under autonomous a second `route` of a routed id prints `owner`
  and writes nothing; a second `route` of a mandate id prints `mandate` and writes nothing.
- [X] T013 Implement `seat_outcome(..., by=)`, `cisr` on `route_owner` and
  `decided_record` (with `owner_record` calling it) in `cli/wuwei/decision.py`, and the
  autonomous branch of `decide()` in `cli/wuwei/commands/decision.py`.
- [X] T014 Test (US1.3, US5.2): `decision show D-n --widget` prints `[]` for a mandate id;
  `owner_outcome` with another option on a mandate id (confirmation stubbed as in the
  existing decide tests) writes `decision.reversed` and `decided_by: owner`.
- [X] T015 Implement the `show --widget` check and the prior-outcome check in
  `cli/wuwei/commands/decision.py`.

## Phase 3: digest, report, close (US1.4, US5; FR-010 to FR-012)

- [X] T016 Test in `tests/test_decision_digest.py`: a `mandate` outcome on a two-way door is
  listed in the digest beside a seat one; a one-way mandate outcome is not.
- [X] T017 Implement the `decided_by` filter in `cli/wuwei/watch.py`.
- [X] T018 Test in `tests/test_report_retro.py`: a day with two Routine mandate outcomes, one
  Consequential mandate outcome and one Strategic route prints, before `## Merged` at brief
  and full, `## Taken under mandate` (Consequential first, record path, `bin/wuwei decide
  D-n <option>`) and `## Decisions by class` with the four count lines of US5.1 and the
  target line; a reversed id is not in the mandate list; a day with none prints `none`.
- [X] T019 Implement `mandate_lines`, `class_lines` and their insertion in
  `cli/wuwei/report.py`.
- [X] T020 Test: close on a day with a one-way mandate outcome reports no pending owner
  decision for it (`closing.unresolved`).
- [X] T021 Implement the mandate skip in `cli/wuwei/closing.py`.

## Phase 4: profile, text, docs (FR-013, FR-014)

- [X] T022 Test in `tests/test_calibrate.py` (the profile denial table near `:726`): importing a profile with `autonomy.mode =
  "autonomous"` over a supervised workspace is refused as outside what a profile may carry;
  `supervised` over autonomous is accepted.
- [X] T023 Implement the `DENIED` row in `cli/wuwei/profiles.py`.
- [X] T024 Update `charters/_common.md` rule 2 (bump its `version:`), `charters/lead.md`
  routing line and `skills/wuwei-plan/SKILL.md:10`; regenerate `agents/*.md`; run
  `tests/test_charters.py` and `tests/test_agents.py` (one home per sentence, no blocking
  instruction).
- [X] T025 Update `docs/site/configuration.md` (Sections table and key row),
  `docs/site/reference.md` (Decided-by values, `route` output, lint OK line) and design 5.4
  and 5.8 (with the 5.8.1 Ceilings sentence) in `docs/specs/2026-09-24-wuwei-design.md`;
  run `tests/test_docs.py`.
- [X] T026 (not applicable: `tests/test_invariants.py` is not on the base) Only if `tests/test_invariants.py` exists on the base at build time: add the
  invariant "under autonomous no Routine, Consequential or scoring Exploratory record is
  routed to the owner by `decision route`, and under supervised routing equals the legacy
  rule" to the design section 9 table and to that test, test first.

## Phase 5: suite

- [X] T027 Run `python -m pytest -q`. For each failure caused by the autonomous default in a
  test whose subject is the owner card flow, set `[autonomy] mode = "supervised"` in that
  test's workspace; change no other assertion. Check written files for em-dashes, emojis and
  absolute local paths.

## Phase 6: review fixes

- [X] T028 (review F1) Under autonomous a one-way record, an `unsure` record whose class is
  not Routine by definition and a record written `Decided-by: owner` (scanner, MCP registry
  and retro records) take the legacy route to the owner; a one-way record is never Routine by
  definition. Tests: `test_cisr`, `test_who_decides_follows_the_class`,
  `test_a_security_finding_still_asks_the_owner`. Charter rule 2, design 5.8 and the 5.8.1
  Ceilings sentence and `docs/site/configuration.md` updated.
- [X] T029 (review F2) A mandate decision keeps an Outcome line holding a carried or parked
  disposition; `close` and `next` count a mandate disposition like a seat one. Test:
  `test_a_mandate_park_keeps_its_disposition`.
