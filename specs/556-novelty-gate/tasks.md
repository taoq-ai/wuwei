# Tasks: Novelty gate

Test first: each test task runs and fails for the expected reason before its implementation
task. Fixtures are neutral (`fixture-org/...` repositories, channel ids `C1`, `C9`, items
`DIV-1`..). New tests go in `tests/test_novelty.py` unless a task names another file; reuse
the record and routing helpers of `tests/test_decision_classes.py`, the workspace and payload
helpers of `tests/test_outward.py`, the `standing` and deploy helpers of
`tests/test_grants.py`, and the payload helpers of `tests/test_protect_state.py` (import or
copy the few lines needed; no new fixture framework).

## Phase 1: the module (FR-001, FR-002)

- [X] T001 Test in `tests/test_novelty.py`: `novelty.keys` finds each of the seven key forms
  in free text, strips trailing `.`, `)` and `:`, drops duplicates and anything containing
  `<` or `>`; `record_keys` reads only Question, Context and Blast radius;
  `configured(config)` holds a configured repo, each config channel source, a person, an
  environment, a workflow and an exact standing target, and not a `repo:fixture-org/*`
  standing pattern.
- [X] T002 Implement `KEY`, `keys`, `record_keys` and `configured` in `cli/wuwei/novelty.py`.
- [X] T003 Test: on a workspace with `memory/targets.json` present, `novel()` returns `[]`
  for an empty list without creating or reading the file, returns a new key and records
  `first_seen` today with `cleared: null`, never returns a configured key, keeps the first
  `first_seen` on a second call; `clear()` marks `by: owner` with the evidence and never
  un-clears; a damaged file (bad JSON, wrong shape, invalid key, symlink) raises
  `ValueError` naming `memory/targets.json` and `bin/wuwei init --upgrade`.
- [X] T004 Implement `_path`, `_read`, the lock, `_update`, `novel`, `clear` and `line` in
  `cli/wuwei/novelty.py`.

## Phase 2: the seed (US4, FR-008)

- [X] T005 Test: day directories dated today, 10 and 31 days back with events
  (`grant.used` target `repo:fixture-org/old`, a `fast_checks.record` repo
  `fixture-org/kept`, a `note` naming `repo:fixture-org/forged`, a `guard.would_refuse`
  whose target is `repo:fixture-org/shaped`) and a day state with a sent chat draft to `C7` and a dropped
  one to `C8`; `seed(root)` returns the count and the set holds `repo:fixture-org/old`,
  `repo:fixture-org/kept`, `channel:C7` with `cleared.by == 'seed'` and `first_seen` the
  event day; not the `note` target, not the 31-day-old one, not `C8`, not the `guard.would_refuse`
  target.
  A second `seed` adds nothing and leaves an uncleared row uncleared. An unreadable day
  prints a warning and is skipped.
- [X] T006 Implement `_history` and `seed` in `cli/wuwei/novelty.py` (reusing
  `consolidation.day_records`, `watch._rows`, `commands.event.FREE_KINDS`).
- [X] T007 Test (US4.4): with no `memory/targets.json`, the first `novel()` seeds from history
  first, so a target in the last 30 days of events is not returned.
- [X] T008 Implement the lazy seed in `_update`.
- [X] T009 Test (US4.1, US4.2, issue acceptance 3) in `tests/test_novelty.py`: `wuwei init
  --upgrade` on that workspace prints `Upgraded memory/targets.json: <n> targets seen in the
  last 30 days` and writes the set; `--dry-run` prints `Would upgrade ...` and writes
  nothing; afterwards `decision route` of a Routine record naming a seeded target prints
  `mandate`.
- [X] T010 Implement the seed call and line in `upgrade()` in `cli/wuwei/commands/init.py`.

## Phase 3: decision route (US1, FR-003 to FR-005, FR-011)

- [X] T011 Test (US1.1, issue acceptance 1): autonomous default, a `Class: retry` record
  whose Context names `repo:fixture-org/new`; `decision route D-1` exits 0 and prints
  `owner` then `first time for repo:fixture-org/new; one owner answer on a card clears it`;
  `decision_routes[D-1]['novel']` and the `decision.routed` payload are
  `['repo:fixture-org/new']`; no outcome; the set has the target uncleared. A second route
  of D-1 prints `owner` and writes nothing new.
- [X] T012 Implement the novelty check in `mandate()` (`cli/wuwei/commands/decision.py`) and
  the `novel` field in `route_owner()` (`cli/wuwei/decision.py`).
- [X] T013 Test (US1.2): `decision show D-1 --widget` question ends with `First time for
  repo:fixture-org/new: your answer clears it.`; a route without `novel` is unchanged.
- [X] T014 Implement the widget sentence in `show()`.
- [X] T015 Test (US1.3, US1.4, issue acceptance 1): the owner answers D-1 through
  `owner_outcome` (gate topic recorded for the planner session, as the existing decide tests
  do); the set shows `cleared: {by: owner, evidence: D-1}`; a second retry record D-2
  naming the same repository routes `mandate`. A damaged set at answer time returns exit 2
  with `D-1 recorded; the seen set was not updated` and the outcome stays recorded.
- [X] T016 Implement the clearing in `owner_outcome()` (with the Keep owner-only exception
  for grant cards, tested in T025).
- [X] T017 Test (US1.5): under `[autonomy] mode = "supervised"` a two-way own-branch seat
  record naming a novel repository routes `seat` (as today); a one-way record routes
  `owner` with `novel` recorded; answering it clears.
- [X] T018 Make T017 pass (expected to pass after T012 and T016; fix only if it does not).
- [X] T019 Test (FR-011): `decision template` lints clean, its Context names the key forms,
  and `novelty.keys` of the template is empty.
- [X] T020 Implement the template Context text in `template()`.

## Phase 4: outward (US2, FR-006)

- [X] T021 Test in `tests/test_novelty.py` (US2.1, issue acceptance 2): autonomous,
  `default_tier = "send"`, a chat MCP write to `C9`; the outward PreToolUse guard exits 1
  with a held draft whose reason contains `first time for channel:C9; approving this draft
  clears it, then the tier table decides`; `drafts show <id> --widget` shows it. The same
  call to a configured channel `C1` passes; a message only the owner reads passes; under
  supervised the `C9` call passes.
- [X] T022 Implement `channel_ids` and the novelty hold in `check_tier`
  (`cli/wuwei/outward.py`).
- [X] T023 Test (US2.2, US2.5): approving the draft clears `channel:C9` with the draft id;
  the repeated identical call passes once (spend); a different message to `C9` then passes
  by the tier table. Dropping a draft for `C10` leaves `channel:C10` uncleared.
- [X] T024 Implement the clearing in `drafts.approve()` (`cli/wuwei/drafts.py`).

## Phase 5: grants (US3, FR-007)

- [X] T025 Test in `tests/test_novelty.py` (US3): autonomous, standing `deploy` on
  `repo:fixture-org/*`, a deploy naming `-R fixture-org/new`; the deploy guard exits 1, a
  grant card exists for that target, the reason contains `first time for
  repo:fixture-org/new`, no `grant.used` event. After the owner answers the card, the same
  deploy passes on the standing line. Answering Keep owner-only instead leaves the target
  novel and the next deploy is refused with the kept reason. A deploy on the configured
  repository passes on the standing line throughout; under supervised the novel one passes
  too.
- [X] T026 Implement `standing=` in `active()` and the novelty check in `gate()`
  (`cli/wuwei/grants.py`).

## Phase 6: the records floor (US5, FR-009)

- [X] T027 Test in `tests/test_protect_state.py` (issue acceptance 4): a seat `Write` and
  `Edit` to `.wuwei/memory/targets.json` and a Bash redirect into it are refused under
  observe, guarded and strict, and the reason names the seen set and its CLI writers.
- [X] T028 Implement the entry in `_protected_name` and `_hint`
  (`cli/wuwei/guards/protect_state.py`).

## Phase 7: report and why (US6, FR-010)

- [X] T029 Test in `tests/test_novelty.py`: the day report has `## First time today` after
  `## Decisions by class`, listing a cleared-by-owner, a seeded and an uncleared target first
  seen today, or `none`; `wuwei why repo:fixture-org/new` prints its first-seen date and
  clearing, `why` of a configured key prints `seen: configured in config.toml`; `wuwei why
  D-1` on a novel route has the `novel:` line.
- [X] T030 Implement `today_lines` and `explain` in `cli/wuwei/novelty.py`, the section in
  `cli/wuwei/report.py`, and the key branch and `novel:` line in
  `cli/wuwei/commands/why.py`.

## Phase 8: invariants, docs, suite

- [X] T031 Invariant tests: if `tests/test_invariants.py` exists on the base, add the three
  rows there and in the design 9.2 table; otherwise add them to `tests/test_novelty.py`
  named `test_invariant_*`: (a) under autonomous a record, an outward send and a standing
  grant on a novel target never run above L1 (always a card, never `mandate`, `seat`, send
  or `grant.used`); (b) only `owner_outcome`, `drafts.approve` and the seed clear (a mandate
  route, a seat route, a dropped draft and a `note` event leave the target novel); (c) a seat
  cannot write `memory/targets.json` (protect_state refuses).
- [X] T032 Docs: design 5.8.1 `Novelty (owner, 2026-10-08, #556)` paragraph; `### Novel` in
  `docs/site/concepts.md`; one paragraph in `docs/site/daily.md`; `docs/site/reference.md`
  (route output, `why <target key>`, `init --upgrade` seed, draft reason). Run any docs test
  (`tests/test_docs.py`, `tests/test_hygiene.py`).
- [X] T033 Run the full suite with `python -m pytest -q`. Fix existing tests only as plan
  "Existing tests at risk" allows. Check every written file for em-dashes and emojis.

## Phase 9: review fixes

- [X] T034 Review F1: key text in backticks, quotes or a markdown link parses to the plain key
  (`test_keys_find_each_form`).
- [X] T035 Review F2: a damaged `memory/targets.json` on an outward send names that file, not
  config check (`test_a_damaged_set_names_the_file_on_send`).
