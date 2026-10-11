# Implementation Plan: delete decision cards, decide and steward steering; owner decisions come from next on one card

**Branch**: `b4-setup-records` | **Date**: 2026-10-11 | **Spec**: [spec.md](spec.md)

Line numbers are at 9639dd8, the batch base. Parts 12 (#832) and 13 (#833) land first on this
branch, so:

- `commands/setup.py`, `interview.py`, `profiles.py`, `commands/calibrate.py`,
  `consolidation.py`, `commands/consolidate.py` and their decision uses are gone;
- `card_write`, `_from_card`, `assignment` and `declared` are in `commands/config.py`;
- `decision.py` imports `ROLES` from `commands.agents`;
- `guards/decision.py` `TOPICS` is `{'goals'}`;
- `skills/wuwei-plan` already says `config set` asks its own card.

Locate code by function name; lines shifted in `commands/next.py`, `commands/doctor.py`,
`brief.py`, `plan.py` and `commands/build.py`.

## Summary

Owner decisions come from `next` (or from the command that parked an item) as one Owner step
card. The CLI applies the safe choice when the owner says No. Seat decision records, routing,
classes, the mandate, the decision guard, `decide` and `decision` go. So do external waits,
the decision digest, steward steering notes and the steward tool-call trigger. The Owner step
recording and the `wuwei hook` refusal stay: `record_gate` moves to `guards/answers.py`, and
the refusal stays in `guards/protect_state.py`. Two callers keep a narrowed record library
until their parts: the learning cards (part 16) and MCP decisions (part 18).

## Technical Context

Stdlib-only Python 3.11+, pytest dev-only. Net deletion. There is one new subcommand
(`plan resume`), one new helper (`sessions.owner_answer`) and one moved answer path
(`outbound answer`). Run only the touched test files; CI runs the suite.

## Constitution Check

- I: nothing added.
- II: `dispatch next`, `plan resume` and `pr act` exit 1 while they wait on the owner and print
  the card. A damaged events row is no answer.
- III: one owner-answer reader (`sessions.owner_answer`, under `needs_owner`); one park writer
  (`plan.park`, the state-only half of `dispose`).
- IV: red tests first for each row of the spec table, the hook branches and the deletions.
- V: about 2,500 lines of code and 4,000 lines of tests go.
- VII: the floors stay. Records are written by the workflow and answered by the owner, and a
  merge the policy does not clear is the owner's decision. No guard on a publishing edge
  changes.
- Design spec ownership: part of the owner-approved #789 pass.

## Process control: what each removed unit was

| Unit | Kind | Where its job goes |
| --- | --- | --- |
| Seat decision records, `decision route`, CISR classes, mandate classes, `autonomy.mode` | (a) seats and the planner reason about which record, class and route | seats assume and record two-way choices in the spec; a one-way or scope question is an ESCALATE or a `Blocked:` line |
| Decision guard `check_write` (record lint), `check_question` (citation), `check_stop` (seat question note) | (a) | nowhere |
| `record_gate` Owner step branch | (b) only the owner's answer in a main session counts (#831) | `guards/answers.py`, unchanged |
| `record_gate` D-n hash and Draft branches | (b) for the cards parts 16 and 18 still ask | `guards/answers.py`, until those parts |
| Bash `wuwei hook` refusal | (b) no forged hook payload (#831) | `guards/protect_state.check_bash`, unchanged |
| Gate card (`dispatch.CARD`, `_card`), mandate taking PARK and ESCALATE | (a) plus a missing owner decision | `dispatch.next_step` asks the Owner step card of `bin/wuwei dispatch next <item>`; No parks in code |
| Round cap park with a record (`_parked` through `plan.dispose`) | (b) no fix round past the cap | kept: `plan.park` in code; `next` names `plan resume` once |
| `decide` and `owner_outcome` resume of a parked item | (b) only the owner resumes parked work | `wuwei plan resume <item>`, through `needs_owner` |
| `plan.dispose`, `build._park`, scanner and PR scope records | (a) the record; the park is (b) | state, event and the `plan resume` line; the scope ask uses the `pr act` card |
| Close held by pending owner records | (a) once no item writes records | nowhere; open items still hold the close (kept) |
| External waits (`decision.waits`), negotiation loops | (a) | nowhere |
| Watch two-way decision digest | (a) | nowhere |
| Steward steering notes and `steward ack`, the dispatch refusal on an unacknowledged note | (a) the planner reasons about steward notes | nowhere; the round cap is the budget (b, kept) |
| Steward tool-call trigger (`maybe_run_for_tool_calls`, `steward.due`, the `next` row) | (a) | nowhere; the steward runs at sweep and close |
| Doctor `trace decisions` row and fix (pre-#352 migration) | (a) | nowhere |

No (b) check is lost.

## Files to delete (7)

- `cli/wuwei/commands/decision.py`, `cli/wuwei/commands/decide.py`
- `cli/wuwei/guards/decision.py` (after `record_gate` and its helpers move; `git mv` to
  `guards/answers.py`, then trim)
- `tests/test_decision_classes.py`, `tests/test_decision_digest.py`
- `scripts/headless_e2e.py` and `tests/test_headless_e2e.py` (the D-1 `/dev/tty` drive, per the
  #831 handoff)

## Files to edit, code (33)

### `cli/wuwei/sessions.py`

- Add `owner_answer(root, command, detail, token='')`. It returns `'Yes'`, `'No'` or None from
  today's latest `gate.asked` row that carries the asked topic: `owner_topic` with replies `''`,
  `'Yes'` and `'No'`. `needs_owner` becomes
  `None if owner_answer(...) == 'Yes' else <the same refusal text>`.
- `take_over` check (208-210): drop the pending decision routes clause and its text.

### `cli/wuwei/guards/answers.py` (moved from `guards/decision.py`)

- Keep `record_gate`, `_answer`, `_draft_answer`, `_pending_drafts`, `DRAFT_ID` and
  `GUARDS = [Guard('PostToolUse', 'AskUserQuestion', record_gate)]`.
- In `record_gate`, keep the Owner step branch exactly. Keep the D-n branch (header is a
  `D-<n>` citing today's record, for the learning and MCP cards) and the Draft branch. Delete
  the `gate_question` + `TOPICS` branch and the `gate_question` card branch (#529 config
  cards, gone with `--from-card`).
- Delete `is_decision`, `opaque`, `check_write`, `_morning`, `gate_question`, `TOPICS`,
  `check_question`, `QUESTION`, `unrecorded`, `check_stop`.

### `cli/wuwei/guards/__init__.py`

- `MODULES`: `'answers': {'PostToolUse': 'AskUserQuestion'}` replaces `'decision'`.
- `AREAS`: `'answers': 'records'`; drop `'decision'` and `'decision.check_question'`.

### `cli/wuwei/guards/agent_launch.py`

- 6: drop the `noqa` comment naming `decision.py`.

### `cli/wuwei/dispatch.py`

- Delete `CARD`, `_card`, `_waiting`.
- `_parked(root, item, reason)`: `plan.park(item, reason, root)` and return
  `{'action': 'escalate', 'reason': reason, 'command': f'wuwei plan resume {item}'}`.
- `next_step`:
  - delete the `steward.review(root)` call and the steward-note refusal;
  - a parked or escalated item returns the same `plan resume` action, read from
    `items.<item>.disposition.reason` or the phase;
  - for `asked` roles (PARK, ESCALATE) under the cap, the token is `sha256` over
    `item:round:role:verdict:file` of the asked records, `[:12]`, and the detail is
    `Gate <role> says <VERDICT> on <item>: <finding head>. Yes opens a fix round; No parks the item.`.
    `sessions.owner_answer(root, f'bin/wuwei dispatch next {item}', detail, token)` then
    decides:
    - Yes falls through to `build.open_fix`;
    - No returns `_parked(root, item, f'gate {role} {VERDICT}: {finding}')`;
    - None returns `{'action': 'escalate', 'reason': ..., 'command': f'wuwei dispatch next {item}', 'card': sessions.owner_card(...)}`.
- The round cap branch is unchanged except it parks through `_parked` (no record).

### `cli/wuwei/plan.py`

- `dispose(item, outcome, reason, root)` writes no record. In one state write it sets
  `items.<item>.disposition = {'kind': outcome, 'reason': reason}`, and for `parked` the phase
  and status as today. The event is `plan.disposed` with the payload
  `{'item', 'outcome', 'reason'}`. It returns None. Add `park(item, reason, root)` as
  `dispose(item, 'parked', reason, root)`.
- Add `resume(item, root)`:
  `if reason := sessions.needs_owner(root, shlex.join(['bin/wuwei', 'plan', 'resume', item]), f'Resume {item}: {why}', token): raise state.StateError(reason)`.
  `why` is the disposition reason or the phase, and `token` is `sha256(reason)[:12]`. It
  requires phase parked or escalated with status blocked. It sets
  `phase = resume_phase`, `status = 'queued'`, pops `disposition` and `decision`, under kind
  `plan.resumed`.
- `gate_widget` keeps `decision.widget` and `decision.gate` (the record library keeps them).

### `cli/wuwei/commands/plan.py`

- Register `resume` (`item`), calling `plan.resume`; carry and park print the item line, not
  a D-n.

### `cli/wuwei/commands/build.py`

- `_park`: no record and no `decision_outcomes`. `action = {'action': 'park', 'reason': reason}`,
  and the item is parked through the same state write.
- `parked_line`: `build: parked {item}: {reason}; run wuwei plan resume {item} after revising
  its brief; it asks the owner its Owner step card`.
- `run` (50): the `row.get('decision')` condition becomes `row['phase'] in ('parked',
  'escalated')`. 252: the text names `wuwei plan resume <item>`.

### `cli/wuwei/commands/next.py`

- `THEN`: add `'owner-step': 'Run it; on exit 1 ask the Owner step card it prints with
  AskUserQuestion, then run it again on Yes. Then run wuwei next.'`. `THEN['pr']` adds
  `on exit 1 with an Owner step card, ask it, then run it again on Yes`.
- `approved()`: dispositions from `items.<name>.disposition.kind` in `('carried', 'parked')`,
  not `decision_outcomes`.
- `_seen`: drop `steward.due` and `due`.
- `step`:
  - delete the pending decision rows (`from wuwei.decision import answered` and the loop);
  - delete the tool-call steward row (the `due` branch; the launch row for a written steward
    brief stays);
  - delete the close-holding decision row.
- `resolve` (the `verdicts` branch): `escalate` returns
  `_row(name, f"{item}: {action['reason']}", action['command'], item=item, then=THEN['owner-step'])`.

### `cli/wuwei/commands/dispatch.py`

- 38, 53: unchanged (`escalate` exits 1); the printed JSON carries `card`.

### `cli/wuwei/pr_actions.py`

- `_thread` scope branch (438-472): drop the record. `answer = sessions.owner_answer(root,
  f'bin/wuwei pr act {ref}', detail, fingerprint[:12])`. The detail is `Reviewer asks a
  scope change on {ref} ({target}): "<first 200 characters>". Yes makes it in a fix round; No
  leaves the thread for you.`
  - Yes returns `_fix(...)`;
  - No sets `answer = {'option': 'defer'}` and goes on;
  - None prints the `needs_owner` refusal and returns 1.

  Drop `pr_action_decisions`.
- `_verify` and `record_disposition`: no D-n. The marker is
  `WUWEI {kind} {ref} {day}` and the record is `{'kind', 'comment_id', 'day'}`.
- The `ACTIONS` texts stay.

### `cli/wuwei/commands/pr.py`

- `disposition`: drop `--decision`.

### `cli/wuwei/closing.py`

- `unresolved`:
  - delete the decision scan (the `decisions` directory, `decision_routes`,
    `decision_outcomes`, pending owner findings);
  - a disposed item reads `items.<name>.disposition`;
  - `resolved` PRs come from `pr_dispositions` by ref;
  - drop the `decision` import.

### `cli/wuwei/scanner.py`

- `_trace_response`: keep the park and the `scanner.finding` event. Delete the record body,
  `scanner_decisions` and the `decision` import. The parked items carry
  `disposition = {'kind': 'parked', 'reason': 'scanner chain <chain>'}`.

### `cli/wuwei/steward.py`

- Delete `pending`, `review`, `_Raised`, `negotiation`, `add_notes`, `acknowledge`,
  `decision_queue` and `maybe_run_for_tool_calls`.
- `run`: drop `notes`, `queue` and the `tool-calls` trigger; the body drops `Notes:` and
  `Decision queue:`; triggers are `sweep` and `close`.

### `cli/wuwei/commands/steward.py`

- `run` only; drop `ack` and the `tool-calls` choice. Docstring: launch steward reviews.

### `cli/wuwei/guards/traces.py`

- Drop the steward call (126-135) and the `steward` field of `_digest`. It reads an old
  digest with a `steward` key without error and rewrites it as `{'tool_calls': n}`.

### `cli/wuwei/watch.py`

- Delete the two-way decision digest (116-160) and its call. Delete
  `counts['external_waits']` (274-276).

### `cli/wuwei/decision.py` (the record library for parts 16 and 18)

- Keep:
  - `FIELDS`, `DECISION_ID`, `ENGINEERING`, `LENSES`, `OPTION_COLUMNS`, `OPTIONAL`,
    `STATUS_QUO`, `CLASSES`, `NO_RECOMMENDATION`, `RECORD`;
  - `table`, `number`, `options`, `_scored`, `evaluate`, `_explained`, `first`,
    `lens_lines`, `widget`, `gate`, `card_hash`, `record_widget`, `option_id`;
  - `today_path`, `route_owner` (without `cisr`), `answered`, `set_outcome`,
    `owner_confirm`, `no_card`, `decided_record`, `owner_record`, `write`;
  - `naming`, for the telemetry, metrics and tracker readers.
- Delete `ROUTINE`, `MARGIN`, `lens_table` (`write` and `evaluate` use `LENSES`), `present`,
  `config_keys`, `lint`, `record_rejection`, `clarification_fields`, `lint_clarification`,
  `lint_file`, `margin`, `cisr`, `route`, `weekday_hours`, `waits` and `seat_outcome`.
- `no_card`: drop the strict sentence (LEFT row). `owner_confirm` keeps `_host_confirm` until
  part 18: relabel that LEFT row to 18.

### `cli/wuwei/commands/outbound.py`

- Add `answer` (`wuwei outbound answer <D-n> <label> [--card <hash>]`): the moved
  `owner_outcome`, narrowed to records with an `outbound_learn` row. That means the
  learned-connector branch and the outcome write; no item resume, no `decision.reversed`.
- `_widget` passes
  `record='{cli} outbound answer {id} "<label>" --card {card}'`.
- The declined text drops the host terminal (the card hash path is the only path).

### `cli/wuwei/commands/config.py`

- Delete `card_write`, `_from_card`, `assignment`, `declared` and `--from-card`; `set_value`
  keeps only the Owner step path (#831).

### `cli/wuwei/brief.py`

- `mandate`: return the three fixed lines of US4.1 plus the `deploy.deny` sentence; drop
  `decision`, `autonomy`, the classes and the route text.

### `cli/wuwei/report.py`

- Delete `decisions`, `CISR`, `mandate_lines`, `class_lines`, `## Taken under mandate`,
  `## Decisions by class` and `## Decisions answered`. `## Parked` lists
  `- <item>: <disposition reason or phase>`. 218: drop the `steward.every_tool_calls` setting.

### `cli/wuwei/retro.py`

- 40-70: a `Change: Hard rule:` note becomes a line under a new `## Hard rule changes`
  section of the retro, not a record; its other proposals are unchanged.
- `_blocks`: `Followed` is `parked: <reason>` or `fix round <n>` or `none yet`; drop the card.

### `cli/wuwei/commands/why.py`

- Drop the D-n target, `question`, the decision group and the record explanation; a parked
  item says `waiting on: wuwei plan resume <item>`. Keep the event-based groups.

### `cli/wuwei/commands/status.py`

- Drop `decision.one_way`, the decisions list and the negotiation loop count.

### `cli/wuwei/memory.py`

- `constraints`: drop `Open decisions`.

### `cli/wuwei/commands/doctor.py`

- Delete `_legacy_traces`, `LEGACY_TRACE`, `SUPERSEDED`, `_supersede_preview`, `_supersede`,
  the `trace decisions` row and the `trace-decisions` FIXES entry.
- The `answered cards` fix becomes `the planner runs each card's record command (the card
  names it)`, which also deletes the LEFT row text.

### `cli/wuwei/signal.py`, `cli/wuwei/commands/event.py`, `cli/wuwei/state.py`

- Drop the kinds:
  - `decision.waited`, `decision.digest`, `negotiation.loop`, `steward.due`, `steward.notes`
    and `steward.acknowledged`;
  - `decision.rejected`;
  - `gate.card` and `pr.action.decision`.

  Add `plan.disposed` and `plan.resumed` (CLI producers `wuwei plan park|carry` and
  `wuwei plan resume`). `config.set` loses its producer with `card_write`: drop it.
- `state.py` producers: drop `steward_notes`, `steward_acks`, `negotiation_loops`,
  `scanner_decisions`, `pr_action_decisions`, and keep `decision_routes` and
  `decision_outcomes` for the learning card. Name `wuwei outbound answer` as their writer.
  The state validator accepts the dropped keys as legacy for old days.

### `cli/wuwei/outward.py`

- 840-843: drop the supervised branch (no `autonomy`).

### `cli/wuwei/workspace.py`, `templates/workspace/config.toml`

- SCHEMA: delete `autonomy`, `decisions` and `steward`; `SURFACES` drops `"digest"`; delete the
  `decisions.lenses` check (780-782).
- `RETIRED`: add `'autonomy', 'decisions', 'steward', 'owner.verbosity.digest'`.
- Template: delete `[autonomy]`, `[decisions]`, `[steward]` and the `digest` verbosity comment.

### `cli/wuwei/telemetry.py`

- 30 `GUARDS`: `'answers'` replaces `'decision'`. Counts unchanged (Assumption 8).

## Files to edit, tests (about 40)

The rule: delete a test with the code it covers; port a test whose behaviour stays; never
relax an assertion on the round cap, gate at head, the merge policy, the Owner step or the hook
refusal.

- New, red first:
  - `tests/test_dispatch.py`: PARK and ESCALATE ask the card (US1.1), Yes opens the fix round
    (US1.2), No parks (US1.3), a new round needs a new answer (US1.5), and the cap parks and
    names `plan resume` (US2.1).
  - `tests/test_plan.py`: `plan resume` refuses without the owner and resumes with
    `owner.answer` (US2.2); dispose writes a disposition and no record (US2.5).
  - `tests/test_sessions.py`: `owner_answer` returns Yes, No and None, and `needs_owner`
    still matches it.
  - `tests/test_pr_actions.py`: the scope thread asks the card, and Yes and No (US3).
  - `tests/test_next.py`: the `verdicts` row carries `THEN['owner-step']`, with no decision or
    steward-due rows.
  - `tests/test_build.py`: the build park line (US2.3).
- `tests/fakes/owner.py`: import `record_gate` from `wuwei.guards.answers`.
- `tests/test_card_confirms.py`: keep the Owner step cases; delete the `decide`,
  `config set --from-card` and decision card cases.
- `tests/test_protect_state.py`: the `wuwei hook` refusal cases stay unchanged (US5.2).
- `tests/test_decision.py`: keep the `evaluate`, `write`, `record_widget`, `option_id`,
  `owner_confirm` and `answered` cases the library keeps; move the `record_gate` cases to
  `tests/test_answers.py` (the Owner step, D-n and Draft topics). Delete the lint, route,
  show, outcome, template, decide, `check_write`, `check_question`, `check_stop`, waits,
  naming-free and clarification cases.
- `tests/test_outbound_learn.py`: answer through `outbound answer`.
- `tests/test_mcp.py`: drop the `decide` alias cases; `mcp decide` stays.
- `tests/test_steward.py`: delete the notes, ack, negotiation, queue and tool-call cases;
  keep run at sweep and close.
- `tests/test_traces.py`, `tests/test_hooks.py` (`MODULES` pin, `test_calibrate_is_off_every_hook_path`
  payloads), `tests/test_guard_mutation.py`, `tests/test_parser_warns.py`, `tests/test_shell.py`:
  the `decision` guard rows become `answers` or go with the deleted checks.
- `tests/test_watch.py`: delete the digest and waits cases.
- `tests/test_stop.py`, `tests/test_close_parked.py`, `tests/test_pr_ownership.py`: dispositions
  without D-n (`WUWEI parked <ref> <day>`); delete the pending owner record cases.
- `tests/test_build.py`, `tests/test_build_next.py`, `tests/test_report_retro.py`,
  `tests/test_why.py`, `tests/test_status` cases in `tests/test_signal_status.py`,
  `tests/test_memory.py`, `tests/test_sessions.py`, `tests/test_doctor.py`,
  `tests/test_records_after_dryrun4.py`, `tests/test_operator_records.py`,
  `tests/test_state_allowlist.py`, `tests/test_tracker.py`, `tests/test_metrics.py`,
  `tests/test_telemetry.py`, `tests/test_e2e_day.py`, `tests/test_path_day.py`,
  `tests/test_process_depth.py`, `tests/test_posture.py`, `tests/test_outward.py`,
  `tests/test_merge.py`, `tests/test_drafts.py`, `tests/test_who.py`, `tests/test_cli.py`,
  `tests/test_workspace.py`, `tests/test_templates_errors.py`, `tests/test_headless_shepherd.py`,
  `tests/test_shepherd.py`, `tests/test_commit_push.py`: the edits the code changes force
  (decision ids, routes, mandate lines, report sections, retired keys).
  - `test_path_day`: a fixture day writes no `D-*.md` (SC-002).
- `tests/test_reasons.py`: delete the five part 14 LEFT rows. Relabel `decision.py`
  `at the host terminal` to 18 (the MCP caller of `owner_confirm`). Add no new row.
- `tests/test_invariants.py`: drop the `CALLED`, `OWNED` and `EXEMPT` rows that name deleted
  functions; keep the wall lint.
- `tests/test_tone.py`: re-measure `cards` and `charters` after the text changes; never raise
  a budget.

## Files to edit, governance and docs (17, plus the generated agents)

- `charters/_common.md`:
  - Decisions rule 1 keeps "Assume and record" through "gates review it as a finding". The
    rest becomes: "A one-way door, a goal or scope change, or a trust-boundary change is not
    yours: a sentinel says ESCALATE and names it in the finding; a builder names it under
    `Blocked:` and stops. `wuwei next` asks the owner."
  - Rule 2 (route) goes.
  - Rule 5's last cap sentence: "the CLI parks the item at the cap; name the finding and what
    would unpark it in the verdict."
  - Rule 8: "PARK and ESCALATE stop the item; `wuwei next` asks the owner whether to open a
    fix round."
- `charters/planner.md` "What the planner records" 1: "Owner decisions come from `wuwei next`,
  one at a time, on the Owner step card a command prints." `charters/lead.md` 21: "park with
  `wuwei plan park <item> --reason`". `charters/builder.md` 11, `charters/sentinel-arch.md`
  14, `charters/sentinel-goal.md` 14, `charters/sentinel-security.md` 14: route through
  Assumptions or ESCALATE, not a record. `charters/steward.md` 1 and 3: drop the tool-call
  trigger, steering notes, acknowledgement and decision pre-triage. Then
  `bin/wuwei agents build`.
- `skills/wuwei-plan/SKILL.md` (the `card` bullet and headless line), `skills/wuwei-retro/SKILL.md`
  and `skills/wuwei-report/SKILL.md` (Owner questions paragraph): an owner question comes from
  `wuwei next`, and a command that refuses with an Owner step card prints it. Ask it with
  AskUserQuestion as printed, then run the same command again on Yes. The headless case
  leaves the item for `next`. The retro skill's "Hard rule" note goes to the retro's
  `## Hard rule changes` section.
- `docs/specs/2026-09-24-wuwei-design.md`:
  - 5.2: the Briefs mandate paragraph uses the three fixed lines, and the Records paragraph
    keeps the #357 sentence and drops #529 and #600;
  - 5.4: owner questions come from `next`;
  - 5.5: drop steering notes and the tool-call trigger;
  - 5.8, 5.8.1, 5.8.2: replace with one paragraph on the owner decision table of spec.md;
  - 4.1: drop the decision guard rows; add `answers` (PostToolUse AskUserQuestion).
- `docs/site/reference.md`: delete the `decide`, `decision` and `steward ack` rows (and the
  duplicate `decide` row the lead noted); add `plan resume`, `outbound answer`.
  `docs/site/concepts.md`, `docs/site/configuration.md` (`[autonomy]`, `[decisions]`,
  `[steward]`), `docs/site/daily.md` ("5. Owner decisions"), `docs/site/security.md`,
  `docs/site/agent.md` if it names them, and `README.md`: the same.
- `.specify/memory/constitution.md` VII: no change needed. Its floors still hold.

## RETIRED

Added to `workspace.RETIRED` in this part: `autonomy`, `decisions`, `steward`,
`owner.verbosity.digest`. No workspace file is retired; old `decisions/D-*.md` stay in their
days.

## Handoff

- Part 16: delete `outbound answer`, the learning card's records and
  routes, the `record_gate` Draft and D-n branches it uses, `decision_routes` and
  `decision_outcomes`, and the LEFT rows for `commands/outbound.py`.
- Part 18: delete the MCP records, then the rest of `decision.py`, `guards/answers.py`'s D-n
  branch, `owner_confirm` and `_host_confirm` with its relabelled LEFT row.
- Part 23: move `card_topic`, `OWNER_STEP`, `owner_card`, `owner_topic`, `owner_answer`,
  `needs_owner` and `guards/answers.record_gate`'s Owner step branch to the module that stays.
  Part 17 carries the `wuwei hook` refusal into the edge guard.
- Part 22: `plan resume`, the `dispatch next` owner card and the `pr act` scope card are the
  owner decision rows the derived `next` must keep.

## Risks

- Behaviour change: under observe and guarded, PARK and ESCALATE no longer auto-resolve. They
  wait for the owner (Assumption 1). An unattended day parks nothing by itself on a PARK
  verdict; that item waits at its gate.
- `tests/test_path_day.py` and `tests/test_e2e_day.py` encode the mandate path; they must be
  rewritten to answer the owner cards with `tests/fakes/owner.py`, not loosened.
- The PR disposition marker format changes; an owner marker posted before the upgrade does not
  verify.
- The traces digest file changes shape; an old file must still read.
- This part is the largest of the batch; build it in the tasks' order, with the hook branches
  (Phase 1) first.
