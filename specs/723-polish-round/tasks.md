# Tasks: an optional polish round after a pass

Test first: each test task runs and fails for the expected reason before its implementation
task. Use the existing fixtures in `tests/test_dispatch.py` (`root`, `record`, `built`,
`caps`, `opinion_fix_round`, `LIGHT`) and neutral item names and paths; no test reaches git
or the network. A note is a finding block like
`- P3 | cli/example.py:3 | fails when the file is empty | blocks: no` inside a PASS verdict.
Config settings go into the fixture's `.wuwei/config.toml` through `caps(root, ...)`. Run the
touched test files, then the full suite.

## Phase 1: the config key (FR-001; US2.3)

- [X] T001 Test in `tests/test_workspace.py`: the gates defaults include
  `'polish': 'offer'` (update the defaults assertion near line 234); `[gates]\npolish =
  "sometimes"\n` fails to load naming `never`, `offer` and `always`.
- [X] T002 Implement the schema entry in `cli/wuwei/workspace.py` (plan, Design). T001
  passes.

## Phase 2: the offer rule and the re-check rule (FR-002, FR-005)

- [X] T003 Tests in `tests/test_dispatch.py` for `dispatch.polish_offer`: None under
  `never`, with no notes, with a `polish` record (opened or skipped) and at the round cap
  (`used == max_rounds`); otherwise `{'gate', 'notes'}` with the notes in gate order and the
  gate the single author (`arch`; `goal` for `['goal']`; `quality@codex` for a second
  opinion) or `quality` for two authors.
- [X] T004 Tests in `tests/test_dispatch.py` for `dispatch.rechecks`: true for a FIX initial
  record; for an all-PASS row with `polish = {'status': 'opened', 'gate': 'quality', ...}`
  true for quality only; false for every gate when the polish is `skipped`, when the row
  records a `pr`, and when the role has no initial record.
- [X] T005 Implement `polish_offer` and `rechecks` in `cli/wuwei/dispatch.py`. T003 and
  T004 pass.

## Phase 3: `dispatch next` at a round-one pass (FR-003; US1.1, US2.1, US2.2)

- [X] T006 Tests in `tests/test_dispatch.py` (`built(root)`, arch PASS with one note,
  quality PASS with one note, security PASS without): at the defaults `next_step` returns
  `{'action': 'polish', 'gate': 'quality', 'notes': [<arch note>, <quality note>], 'command':
  'wuwei dispatch polish A', 'skip': 'wuwei dispatch skip-polish A'}` and the events file is
  unchanged by a second call; under `polish = "never"` it returns `raise` with both notes;
  under `polish = "always"` it returns `{'action': 'fix', 'roles': ['quality'], 'command':
  'wuwei build next A'}`, the item is in `fix` and `items.A.polish` is recorded as opened. A
  pass without notes still returns `{'action': 'raise', 'notes': []}` in all three modes.
- [X] T007 Update `test_ordinary_finding_below_threshold_remains_a_note` in
  `tests/test_dispatch.py` to assert the polish offer carrying the scanner note (plan,
  Existing tests).
- [X] T008 Implement the gate-phase tail of `next_step` and `_open_polish` in
  `cli/wuwei/dispatch.py`, and `open_fix(..., polish=None)` in
  `cli/wuwei/commands/build.py` (record in the same state write, refuse a second record,
  `polish: True` in the `build.fix_opened` payload). T006 and T007 pass.

## Phase 4: take or skip the offer (FR-004, FR-011; US1.2, US3)

- [X] T009 Tests in `tests/test_dispatch.py`: after the offer, `dispatch.polish('A', root)`
  returns the `fix` action for `['quality']`; phase `fix`; `items.A.polish ==
  {'status': 'opened', 'gate': 'quality', 'notes': [...]}`; the build record's action
  feedback starts `Polish round:` and contains both notes, and its prompt ends with it; the
  last event is `build.fix_opened` with `round: 1` and `polish: True`. Without a resumable
  builder (pop `agent_id`, as `test_gate_fix_without_agent_id_launches_gate_fix_brief`
  does) the fresh brief body carries the notes.
- [X] T010 Tests in `tests/test_dispatch.py`: `dispatch.skip_polish('A', root)` returns
  `raise` with both notes, records `items.A.polish.status == 'skipped'`, appends a
  `polish.skipped` event, and the next `next_step` returns the same `raise`. After a skip or
  an open, both `polish` and `skip_polish` raise `Refused` naming `dispatch next`. Under
  `always` and `never`, both raise `Refused` naming the mode, and the item stays at `gate`
  with no `polish` record.
- [X] T011 Test in `tests/test_dispatch.py` through `wuwei.__main__.main` with
  `WUWEI_WORKSPACE`: `dispatch polish A` exits 0 printing the JSON action; a second
  `dispatch polish A` exits 1 with the reason on stderr; `dispatch skip-polish` on another
  fixture exits 0.
- [X] T012 Test in `tests/test_state_allowlist.py`: `event.EVENT_PRODUCERS['polish.skipped']
  == 'wuwei dispatch skip-polish'` (the pattern of `tests/test_config_transition.py:226`),
  and `state.write_state` setting `items.A.polish` raises `StateError` matching
  `reserved; written by wuwei dispatch polish or wuwei dispatch skip-polish` (the pattern of
  `tests/test_plan.py:509`).
- [X] T013 Implement `_offered`, `polish`, `skip_polish` and `_polish_feedback` in
  `cli/wuwei/dispatch.py`; the two subcommands in `cli/wuwei/commands/dispatch.py`; the
  producer text in `cli/wuwei/state.py`; the reserved kind in `cli/wuwei/commands/event.py`.
  T009 to T012 pass.

## Phase 5: one gate re-checks the polish delta (FR-005, FR-006; US1.3, US1.4)

- [X] T014 Test in `tests/test_dispatch.py`, the issue acceptance end to end: offer, then
  `dispatch.polish`, `state.transition('A', 'delta')`; `next_step` asks for `['quality']`
  only; with the quality seat stopped with an agent id at the round-one head, the one seat
  action is a `continue` whose feedback starts `Polish re-check:`, names both notes and
  `gate-quality-1.md`, and whose `receive` ends `--round delta`; `dispatch.delta_due('A'...)`
  for that seat is true and for the arch seat false; receiving an arch delta is refused
  (`did not need a delta`); receiving the quality delta PASS (one remaining note) makes
  `next_step` return `raise` with that one note, and a further `next_step` never returns
  `polish`.
- [X] T015 Test in `tests/test_dispatch.py`: a blocking polish delta (quality FIX) opens the
  next fix round under the default cap (`fix`, `fix_rounds == 2`, the quality delta rotated
  to `initial`, `round1` kept), and the following delta asks for `['quality']`; with
  `max_rounds = 1` it returns `escalate` starting `round cap 1 reached: quality still
  blocks:`.
- [X] T016 Test in `tests/test_dispatch.py`: notes only from the second opinion
  (`opinion_fix_round` style setup, quality PASS without notes, `quality@codex` PASS with a
  note): the offer names `quality@codex`; after the polish round the delta step is the
  `run` of `wuwei dispatch opinion A`, and `dispatch.opinion` continues the codex job with
  the polish re-check feedback.
- [X] T017 Implement the `rechecks` call sites in `cli/wuwei/dispatch.py` (`next_step` fix
  and delta roles, `delta_due`, `receive`, `opinion`) and `_recheck_feedback` with its two
  call sites (`_seats`, `opinion`). T014 to T016 pass, and the existing delta tests pass
  unchanged.

## Phase 6: the PR is raised and merged after the re-check (FR-007; US1.5)

- [X] T018 Test in `tests/test_pr_guards.py` (model on
  `test_pr_gate_accepts_quality_only_delta_after_fix`): three PASS initial records at the old
  head, a quality delta PASS at the new head: `gate_check` passes at the new head; without
  the quality delta it refuses naming every gate; with the delta and a current head other
  than the delta's it refuses naming quality.
- [X] T019 Test in `tests/test_merge.py` (next to the `quality-delta.md` assertion near line
  127): for a PASS-initial gate with a delta record, the eligibility `verdicts` list carries
  the delta file.
- [X] T020 Implement the `rechecked` set in `cli/wuwei/guards/pr.py` `_recorded_gates` and
  the selection in `cli/wuwei/merge.py`. T018 and T019 pass, and every existing PR-guard and
  merge test passes unchanged.

## Phase 7: the planner's loop (FR-008; US4)

- [X] T021 Test in `tests/test_next.py` (next to the `raise` resolve cases near line 586):
  `resolve` on a `verdicts` row whose `dispatch.next_step` returns the polish action gives a
  `polish` row with command `wuwei dispatch polish A` and a then line naming
  `wuwei dispatch skip-polish A`.
- [X] T022 Implement the `polish` branch in `cli/wuwei/commands/next.py` `resolve`. T021
  passes.

## Phase 8: invariant, charter and docs (FR-001, FR-009, FR-010)

- [X] T023 Add `i58` to `tests/test_invariants.py` (plan, I58), `INVARIANTS['I58']`,
  `READS['I58'] = ()`, and the 9.2 row in `docs/specs/2026-09-24-wuwei-design.md` after
  I46. Run it red by temporarily inverting the `never` check in `polish_offer`, then green.
- [X] T024 Add the anchor `("polish round", "_common.md", "fixes only the listed notes")` to
  `tests/test_charters.py`; it fails.
- [X] T025 Append the polish sentence to rule 5 of `charters/_common.md`, bump its version to
  1.10.0 and run `bin/wuwei agents build`. T024 passes and the agents check is clean.
- [X] T026 Add the `gates.polish` row to `docs/site/configuration.md`, the commented line to
  `templates/workspace/config.toml` and the two commands to the dispatch row of
  `docs/site/reference.md`. `tests/test_docs.py` passes (template keys documented).

## Phase 9: verification

- [X] T027 Run the full suite with the pipeline interpreter (`-m pytest -q`); all green. Grep
  the changed files for em-dashes and emojis; none.
