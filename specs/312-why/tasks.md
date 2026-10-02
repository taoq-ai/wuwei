# Tasks: wuwei why

Test first: run each test task, see it fail for the stated reason, then do the
implementation task that follows it. Run tests with `python -m pytest -q <file>` from the
repository root using the interpreter the task names. Signatures, texts and placement are
in plan.md. New behaviour tests go in a new `tests/test_why.py` unless a task names another
file.

`tests/test_why.py` fixture `root` (as in `tests/test_shadow.py`): `.wuwei/config.toml`
empty, `WUWEI_WORKSPACE`, `WUWEI_NOW = '2026-10-02T12:00:00+00:00'`, `chdir`. Records are
written the way their producers write them: `state.json` as JSON text (as
`tests/test_board_mcp.py` does), events with `state.append_event(kind, payload,
directory=day)` so line numbers are known, decision records with `VALID` from
`tests/test_decision.py`, verdict files as text under `decisions/gate-<name>.md`. A helper
`merged_item(root)` builds the acceptance day for item `fix-login` (PR `acme/app#7`):
`proposal.json` with its candidate and WSJF score; events `plan.approved`, `gate.tiered`
(`standard`, reasons `['lead flag trust_surface', 'floor standard']`), three
`gate.received` (arch PASS, quality FIX, security PASS) with matching `gate_verdicts` and
files (quality's with one `blocks: yes` finding), a seat `decision.decided` for `D-3`
(whose `Context:` names `fix-login`), an owner `decision.decided` for `D-4`, events with
`phase_changes` (`state.transition` to `gate`, `pr.raised` to `raised`, `pr.action` to
`merged`) and `merge.auto` with evidence (head, checks, approvals, verdict paths).

## Phase 1: Recorded inputs the chain needs (US2, US3; FR-006, FR-007)

- [X] T001 In `tests/test_hooks.py`, add failing tests with the `plugin` fixture, a stub
  module `fake` returning `(1, 'force-push is refused; push a branch instead')` and
  `tests/payloads/PreToolUse/bash.json`:
  (a) the refusal is enforced exactly as today (`assert_refusal`) and today's last event
  is `hook.refusal` with payload `{'reason': 'force-push is refused; push a branch
  instead', 'refusals': [{'guard': 'fake', 'reason': <same>}], 'target': 'npm test'}`;
  (b) then `main(['why', 'last refusal'])` exits 0 and prints the lines
  `command: npm test`, `guard: fake`, `rule: force-push is refused`,
  `fix: push a branch instead` (issue acceptance 2);
  (c) with `hook.redacted_target` monkeypatched to raise, the call is still denied with
  exit 2 and the event is recorded without `target`;
  (d) with two stubs refusing, `refusals` lists both in discovery order and `reason` is
  both messages joined by a newline, as today.
  Fails today: the payload is `{'reason': ...}` only and there is no `why` command.
- [X] T002 In `cli/wuwei/commands/hook.py`, add `redacted_target`, make `shadow` return
  the enforced pairs and `refuse` record `refusals` and `target` (plan.md 1). T001 (a),
  (c), (d) pass; run `tests/test_hooks.py`, `tests/test_shadow.py`,
  `tests/test_e2e_day.py`, `tests/test_promotion.py` unchanged.
- [X] T003 In `tests/test_why.py`, add a failing test: with `VALID` one-way saved as
  `D-3`, `main(['decision', 'route', 'D-3'])`, `_host_confirm` monkeypatched to `True`,
  then `main(['decision', 'outcome', 'D-3', 'B'])`: the last event is `decision.decided`
  with `payload['decided_by'] == 'owner'`; and a seat reversal (two-way `D-3` routed to
  the seat, then owner outcome `B`) writes `decision.reversed` with `decided_by: owner`.
  Fails today: the owner payload has no `decided_by`.
- [X] T004 In `cli/wuwei/commands/decision.py` line 132, add `'decided_by': 'owner'`
  (plan.md 2). T003 passes; run `tests/test_decision.py` and `tests/test_metrics.py`.

## Phase 2: The item chain (US1; FR-001 to FR-005, FR-009)

- [X] T005 In `tests/test_why.py`, add failing tests on `merged_item(root)`:
  (a) `main(['why', 'fix-login'])` exits 0 and prints, in this order, `queued: goal ...,
  score value ...`, `tier: standard (lead flag trust_surface; floor standard)`,
  `gate arch initial: PASS`, `gate quality initial: FIX, blocking: <finding first line>`,
  `gate security initial: PASS`, `decision D-3: <question>: A by seat`,
  `decision D-4: <question>: B by owner`, the `phase ... by <EVENT_PRODUCERS name>` lines
  in event order, `merge acme/app#7: cleared by the merge policy at head <12 chars>,
  checks <name conclusion>, approvals <login>`, and `now: merged (done)` (issue
  acceptance 1);
  (b) `--full`: every line except `now` ends with `(event 2026-10-02:<n>` where `<n>` is
  that event's line in `events.jsonl`, the queued line names
  `.wuwei/days/2026-10-02/proposal.json`, each gate line its verdict file, each decision
  line its record, the merge line the evidence verdict paths; `now` ends with
  `(event not recorded; .wuwei/days/2026-10-02/state.json)`;
  (c) `[owner.verbosity]` `report = "full"` in `config.toml` gives the `--full` output
  without the flag; `report = "standard"` gives the brief output;
  (d) `main(['why', 'acme/app#7'])` prints the same as (a);
  (e) the workspace tree (paths and bytes) is identical before and after (a) and (b).
  Fails today: no `why` command.
- [X] T006 Create `cli/wuwei/commands/why.py` with `Missing`, `register`, `level`, `run`,
  `render` and `item` (plan.md 3, 3a). T005 passes.
- [X] T007 In `tests/test_why.py`, add failing tests for missing records (issue
  acceptance 3): drop the `gate.tiered` event from `merged_item` and the output has
  `tier: not recorded` with no event under `--full` (`(event not recorded)`); with no
  `plan.approved`, `queued: not recorded`; with no `gate.received`,
  `gate verdicts: not recorded`; with no `merge.auto` on a merged item,
  `merge policy check: not recorded`, and no merge line at all for an item at `implement`;
  a `proposal.json` without the item gives `score not recorded`; an owner
  `decision.decided` without `decided_by` (an older record) gives `by not recorded`; a
  `D-n` naming the item with no decision event gives `decided not recorded`; a quality
  `gate_verdicts` entry whose file is missing gives `blocking findings not recorded`.
  Fails until each placeholder exists.
- [X] T008 In `cli/wuwei/commands/why.py`, complete the required-step placeholders and
  the `not recorded` fallbacks (plan.md 3a steps 3 to 5). T007 passes.
- [X] T009 In `tests/test_why.py`, add failing tests: an item in yesterday's state (with
  its `plan.approved` and `gate.tiered` there) carried into today by a `state.import`
  event lists yesterday's steps before today's (`queued: goal ...` then
  `queued: carried over from an earlier day, goal ...`); a parked item with `decision:
  D-5` ends `now: parked (blocked), waiting on decision D-5`; a parked item without one
  ends `waiting on: not recorded`; an item with `assumption.status = 'waiting'` names
  `waiting on external confirmation D-n`; `plan.added` takes the score from
  `discovery_candidates`.
- [X] T010 In `cli/wuwei/commands/why.py`, make T009 pass (plan.md 3a steps 2, 3, 5).
- [X] T011 In `tests/test_why.py`, add failing exit tests: an unknown item exits 1 with
  `wuwei why: no recorded item <name>` on stderr; an unlinked PR ref exits 1 with
  `no item links acme/app#9`; a malformed ref `acme#x` exits 2 (the
  `references.pull_request` `ValueError`); a corrupt line in a read day's `events.jsonl` exits 2 with
  `wuwei why:` on stderr; outside a workspace (no `WUWEI_WORKSPACE`, empty cwd) exits 2.
- [X] T012 In `cli/wuwei/commands/why.py`, fix anything T011 shows (the `Missing` path and
  the `__main__` handler should already cover it).

## Phase 3: Refusals (US2; FR-008)

- [X] T013 In `tests/test_why.py`, add failing tests with `hook.refusal` events appended
  directly: `why 2026-10-02:<n>` prints the refusal on that line; a line that is another
  kind, a line past the end, and a day with no directory each exit 1; an older record
  `{'reason': 'push to the default branch is refused'}` prints `command: not recorded`,
  `guard: not recorded`, `rule: push to the default branch is refused`,
  `fix: not recorded`; with no refusal at all, `why last refusal` (two words, unquoted)
  exits 1 with `no recorded refusal`; `last refusal` picks the newest event across days
  (a refusal yesterday and one today returns today's); `--full` adds `(event <id>)` to
  each line.
- [X] T014 In `cli/wuwei/commands/why.py`, add `refusal` (plan.md 3b). T013 and T001 (b)
  pass.

## Phase 4: Decisions (US3; FR-008)

- [X] T015 In `tests/test_why.py`, add failing tests on `VALID` saved as today's `D-3`:
  after an owner outcome `B` (as in T003), `main(['why', 'D-3'])` prints the
  `decision.present(..., 'brief')` lines, `weights: Correctness 10, Speed 2`,
  `margin: 0.47`, `class: not recorded`, `level: not recorded`, `decided: B by owner`;
  a record with a `Class: retry` line prints `class: retry`; a recorded
  `decision.decided` with `decided_by: 'cruise retry@L2'` prints `level: L2`; a pending
  record prints `decided: not recorded`; `why D-9` with no record exits 1.
- [X] T016 In `cli/wuwei/commands/why.py`, add `decided` (plan.md 3c). T015 passes.

## Phase 5: Board (US4; FR-010)

- [X] T017 In `tests/test_board_mcp.py`, add failing tests: with the `day` fixture's
  events replaced by one valid event, `structuredContent['./why.json']` maps `a` and `b`
  to `why.render(why.item(root, name), 'brief')`; with the fixture as it is (an event line
  without `payload`), `./why.json` is `{"unmeasured": ...}` and `isError` is false.
  Every existing board test passes unchanged.
- [X] T018 In `cli/wuwei/commands/board.py`, add `./why.json` and the description words
  (plan.md 4). T017 passes; run `tests/test_board_mcp.py`.

## Phase 6: Docs and polish (FR-011)

- [X] T019 Run `tests/test_docs.py`: `test_reference_lists_every_cli_command` fails on the
  new `why` command. In `docs/site/reference.md`, add the commands row and the `## Why`
  section (plan.md 5). `tests/test_docs.py` passes.
- [X] T020 Run the full suite (`python -m pytest -q`), including the `WUWEI_BENCH=1`
  hook budget tests if the task names them. Check every file written for em-dashes,
  emojis and absolute local paths and remove any.

## Phase 7: Review fixes

- [X] T021 (review F1) In `tests/test_why.py`, add a failing test with a token in a
  decision Question for `why fix-login` and `why D-3`, brief and `--full`. In
  `cli/wuwei/commands/why.py`, `render` takes `root` and passes every line through
  `security.redact(redact(line), security.load(root))`; `board.py` passes `root`.
- [X] T022 (review F2) In `tests/test_why.py`, add a failing test that a
  `guard.would_refuse` event is explained by `last refusal` and by its event id. In
  `refusal`, accept that kind and print `would have refused (shadow) at <ts>`. Update A2
  and the reference Why section.

## Dependencies

T001 to T004 first (the chain reads `decided_by` and the refusal fields). T005 to T012 in
order. T013 to T016 after T006 (they extend `why.py`). T017 and T018 after T010. T019 and
T020 last.
