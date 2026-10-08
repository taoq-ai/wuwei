# Tasks: Measured reversibility

Test first: each test task runs and fails for the expected reason before its implementation
task. Fixtures are neutral (`fixture-org/...` repositories, decision ids `D-1`..). New tests
go in `tests/test_undo.py` unless a task names another file; reuse `record()`, `ws` and
`route()` from `tests/test_decision_classes.py`, the fake code host and merge entries of
`tests/test_merge.py`, and the payload helpers of `tests/test_protect_state.py` (import or
copy the few lines needed; no new fixture framework).

## Phase 0: base check

Outcome (builder): the worktree was fast-forwarded to origin/main at #554; #283 landed as
#566 (`cli/wuwei/cruise.py`, `commands.decision.undo`). `tests/test_invariants.py` is not on
the base, so the invariant rows go into `tests/test_undo.py`.

- [X] T001 `git fetch -q origin main`; when `git log origin/main` shows #283 (cruise mode) and
  the worktree base does not, `git merge --ff-only origin/main` (only untracked spec files
  are in the tree; no commit is written). Confirm #283's `undo(args, *, root=None,
  where=None)` in `cli/wuwei/commands/decision.py` and `cli/wuwei/cruise.py`; check whether
  `tests/test_invariants.py` exists. Note the outcome at the top of this file. If #283 is
  still absent, stop and report the dependency (spec Assumptions); build nothing.

## Phase 1: the registry and the ledger (FR-001, FR-002, FR-009)

- [X] T002 Test in `tests/test_undo.py`: `undo.KIND` maps every class of `decision.CLASSES`
  as FR-002 says (a new class without a mapping fails the test); `REGISTRY` holds exactly
  `commit`, `decision`, `merge`; `message` is not in it.
- [X] T003 Test in `tests/test_undo.py`: `ledger(root)` is `{}` without the file; returns the
  kinds after `record(root, 'commit', 'rehearsal')`; `record` keeps the first `at`; a
  symlink, bad JSON, wrong shape, unknown kind or bad `by` raises `ValueError` naming
  `memory/rehearsals.json` and `wuwei undo rehearse`; `missing(root)` lists the unrecorded
  registry kinds and all of them for a damaged file.
- [X] T004 Implement `NAME`, `REGISTRY`, `SCRATCH`, `KIND`, `ledger`, `record` and `missing`
  in `cli/wuwei/undo.py` (module-level imports: `json`, `re`, `pathlib`, `state`,
  `workspace` only).
- [X] T005 Test in `tests/test_protect_state.py`: a seat `Write`, `Edit` and Bash redirect to
  `.wuwei/memory/rehearsals.json` are refused under observe, guarded and strict, and the
  hint names `wuwei undo rehearse`. Test in `tests/test_undo.py`: `wuwei event undo.done`
  and `wuwei event undo.rehearsed` are refused as reserved.
- [X] T006 Implement the `_protected_name` tuple entry and `_hint` line in
  `cli/wuwei/guards/protect_state.py`, and the two `EVENT_PRODUCERS` entries in
  `cli/wuwei/commands/event.py`.
- [X] T007 Add the autouse `rehearsed_undo` fixture to `tests/conftest.py` (patches
  `wuwei.undo.ledger` to return `commit` and `decision`, returns the real reader); in
  `tests/test_undo.py` restore the real reader for every test. Run the full suite once to
  see what still breaks (expected: nothing yet).

## Phase 2: the measured door (US1, FR-003, FR-004)

- [X] T008 Test in `tests/test_undo.py`: `measured(fields, root, config)` returns no reason
  for a rehearsed `commit` or `decision` class; the unrehearsed reason with `run wuwei undo
  rehearse <kind>`; the message reason for `Class: message` with a full ledger; the
  no-undo reason for `other` and for a record without `Class:`; for `merge`: no repository
  named, a configured repository without `merge_deploys = false`, an unconfigured one, two
  repositories one of which deploys, and two that do not deploy with `merge` recorded
  (no reason); the damaged-ledger reason. Each reason passes the `tests/test_reasons.py`
  next-step pattern.
- [X] T009 Implement `measured` and `line` in `cli/wuwei/undo.py`, reusing
  `novelty.record_keys` for repository keys.
- [X] T010 Test in `tests/test_undo.py` (US1 scenarios 1, 3, 5, 6, 7): `decision lint` on a
  two-way `merge` record for a deploying `repo:fixture-org/app` exits 0 with the OK line and
  the correction line; on an unrehearsed `retry` record exits 0 with `run wuwei undo
  rehearse commit`; on a `message` record exits 0 with the message reason; on a `one-way`
  record prints only the OK line; the record file is byte-identical after each lint; under
  posture observe, guarded and strict the exit code is the same.
- [X] T011 Implement the `root` parameter of `lint` and its pass-through in `lint_file` in
  `cli/wuwei/decision.py`.

## Phase 3: the routing point writes it (US1, FR-005)

- [X] T012 Test in `tests/test_undo.py` (issue Acceptance 1 and 3, US1 scenarios 1 to 4 and
  6): `decision route` on the deploying `merge` record prints `owner` then the reason, the
  file reads `Reversibility: one-way` and one `Notes: Reversibility corrected at` line,
  `decision_routes[D-1].reversibility == 'one-way'`, no outcome; on the unrehearsed `retry`
  record the same with `run wuwei undo rehearse commit`; after `record(root, 'commit',
  'rehearsal')` a second `retry` record D-2 prints `mandate` and D-1 stays routed to the
  owner (a repeat route writes nothing); an `unsure` `park` record with `decision`
  unrehearsed is corrected and goes to the owner; a second route of a corrected record
  prints `owner` with no second line and appends no second Notes line; a two-way `retry`
  record taken under the mandate while `commit` was patched as rehearsed, routed again with
  the ledger empty, prints `mandate` and its file is byte-identical (first route only).
- [X] T013 Test in `tests/test_undo.py` (issue Acceptance 2, US1 scenario 2): with `commit`
  rehearsed, a two-way `retry` record with blast radius `own branch` is linted with only the
  OK line, routed `mandate` under autonomous and `seat` under supervised, file unchanged
  except what routing already writes.
- [X] T014 Test in `tests/test_undo.py`: `decision route D-1 --external <item>` on an
  unrehearsed two-way record corrects the record before the external route.
- [X] T015 Implement `correct(ident, path, text, fields, root)` in `cli/wuwei/undo.py` and
  call it in `decide(args)` in `cli/wuwei/commands/decision.py` right after `evaluate`,
  appending `said` to the printed `owner` route.

## Phase 4: undo and rehearse (US2, US3, FR-006, FR-007, FR-008)

- [X] T016 Test in `tests/test_undo.py` (issue Acceptance 4, US2 scenarios 1 to 3): a cruise
  answer D-1 with an open window (built through `decision route` under the defaults, as
  `tests/test_cruise.py` does); `wuwei undo D-1 --answer Undo` with the planner's card
  answer recorded reverts it exactly as `wuwei decision undo D-1` does (`decision.reversed`
  with `undo: true`, record `Decided-by: owner`, `Outcome: pending`, class one level lower)
  and the ledger has `decision` with `by: undo`; the DM `undo D-1` path also writes the
  ledger row; a closed window, no window and a seat call (no card, no terminal: patch the
  host confirmation to raise `OSError`) exit 1 and write nothing (no event, no ledger row).
- [X] T017 Implement `run` (the D-n branch) in `cli/wuwei/undo.py`, the new
  `cli/wuwei/commands/undo.py` (`register`, `run`) with `'undo'` in `WRITES` of
  `cli/wuwei/commands/__init__.py`, and the one ledger line in `undo` of
  `cli/wuwei/commands/decision.py`.
- [X] T018 Test in `tests/test_merge.py`: `merge.revert(root, directory, ref, entry, host)`
  opens the revert PR once, saves `merge.revert`, returns the URL, and a second call returns
  the stored URL without calling the host; the existing red-base monitor tests still pass.
- [X] T019 Implement `revert` in `cli/wuwei/merge.py` and call it from `monitor`.
- [X] T020 Test in `tests/test_undo.py` (US2 scenarios 4 and 5): with a fake code host and a
  day holding a `merge.completed` event and its `merges` entry, `wuwei undo <day>:<n>` with
  the host confirmation answering y opens the revert PR, writes `undo.done` with the event
  id, kind and revert PR, and records `merge`; answering no exits 1 and writes nothing; no
  terminal exits 1 naming `in a host terminal and answer y`; an event id naming a
  `decision.routed` event exits 1 with `has no registered undo`; an id past the end of the
  file exits 1.
- [X] T021 Implement the event branch of `run` in `cli/wuwei/undo.py`.
- [X] T022 Test in `tests/test_vcs.py`: one real smoke test: `rehearse_revert(<tmp dir>)`
  returns `reverted: true`; the allowlist refuses the new argv shapes for a path outside
  the temporary directory. Test in `tests/test_undo.py`:
  `wuwei undo rehearse commit` exits 0, prints `rehearsed commit`, appends one
  `undo.rehearsed` event, writes the ledger row, and leaves no directory behind; with the
  adapter patched to fail it exits 2 with the reason and writes nothing; no configured
  repository's refs change.
- [X] T023 Implement `rehearse_revert` and its allowlist cases in `adapters/vcs/git.py`,
  `'rehearse_revert': ('path',)` in the `vcs` contract of `cli/wuwei/registry.py`, and the
  `commit` branch of `rehearse` in `cli/wuwei/undo.py`.
- [X] T024 Test in `tests/test_undo.py` (US3 scenarios 2 and 3): `wuwei undo rehearse
  decision` exits 0 and writes the event and row in the real workspace while the real day
  directory gains no decision record, state or route, also when `WUWEI_WORKSPACE` names the
  real root (the pin), and `WUWEI_WORKSPACE` holds its previous value after the call; with the scratch undo patched to
  return 1 it exits 2 and writes nothing; `rehearse merge` exits 1 naming the revert PR and
  `wuwei undo`; `rehearse message` and `rehearse nonsense` exit 1 naming `wuwei undo rehearse
  commit or wuwei undo rehearse decision`; every exit 1 and 2 reason of `cli/wuwei/undo.py`
  passes `tests/test_reasons.py`.
- [X] T025 Implement the `decision` (with the `WUWEI_WORKSPACE` pin and restore), `merge` and
  fallback branches of `rehearse` in `cli/wuwei/undo.py`.

## Phase 5: the path, upgrade and doctor (US4, FR-010, FR-011)

- [X] T026 Test in `tests/test_next.py`: after the gate, with the real ledger reader and
  nothing rehearsed, `step` returns `rehearse` with `wuwei undo rehearse commit`, then (with
  `('rehearse', 'commit')` returned) `decision`, then the rows of today; with both recorded
  in the ledger no `rehearse` row appears; with both pairs returned the ledger file is not
  read (patch `undo.ledger` to raise).
- [X] T027 Implement the `rehearse` rows in `step` of `cli/wuwei/commands/next.py`.
- [X] T028 Test in `tests/test_undo.py`: `init --upgrade` and `init --upgrade --dry-run` print
  `Undo not rehearsed: commit, decision, merge; run wuwei undo rehearse <kind> (a merge
  counts after its first wuwei undo)` on a fresh
  workspace and still print `No workspace changes needed` when nothing else changed. Test in
  `tests/test_doctor.py`: the Workspace row `undo rehearsals` is ok and names rehearsed and
  unrehearsed kinds; a damaged ledger makes it fail with the fix; doctor's exit code on a
  fresh workspace is unchanged.
- [X] T029 Implement the line in `upgrade` of `cli/wuwei/commands/init.py` and the row in
  `_workspace` of `cli/wuwei/commands/doctor.py`.

## Phase 6: the report (US5, FR-012)

- [X] T030 Test in `tests/test_report_retro.py`: a day with a `decision.reversed` event with
  `undo: true`, an `undo.done` event, a one-way decision outcome and a `draft.sent` event
  lists them under `## Undone today` and `## Cannot be undone`; an empty day prints `none`
  under each.
- [X] T031 Implement `report_lines` in `cli/wuwei/undo.py` and the two sections in `build` of
  `cli/wuwei/report.py`.

## Phase 7: invariants, docs, suite (FR-013, FR-014, FR-015)

- [X] T032 Invariant tests: if `tests/test_invariants.py` exists on the base, add the rows
  there and in the design 9.2 table; otherwise add to `tests/test_undo.py`, named
  `test_invariant_*`: (a) over every class, written door (`one-way`, `two-way`, `unsure`),
  ledger (empty, `commit` only, `commit` and `decision`, all three), merge base deploying or
  not and autonomy mode, a routed record ends `two-way` or `unsure` only when its kind is
  registered and in the ledger (and the base does not deploy for `merge`); (b) no `message`
  record ever routes as anything but one-way; (c) `wuwei undo D-n` and `wuwei undo <event
  id>` without a card answer, DM reply or host terminal write no event, state or ledger
  change; (d) under observe, guarded and strict the lint exit code of a valid record is the
  same with and without a correction.
- [X] T033 Design spec: the paragraph `Measured reversibility (owner, 2026-10-08, #557).` in
  `docs/specs/2026-09-24-wuwei-design.md` 5.8 after the Decision classes paragraph.
- [X] T034 Docs: `docs/site/concepts.md` (reversibility measured, undo, rehearsal),
  `docs/site/reference.md` (`wuwei undo`, `undo rehearse`, the correction line, the ledger,
  the report sections), `docs/site/daily.md` (the rehearse step, undo by card, DM or
  terminal); run `tests/test_docs.py`.
- [ ] T035 Run `python -m pytest -q` from the repository root; fix fixture days that route
  two-way records in a subprocess by rehearsing in their setup; check every written file
  for em-dashes, emojis and absolute local paths.
