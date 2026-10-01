# Tasks: Mandate block in briefs, assume-and-record, time-boxed external waits, ask metrics, and a negotiation-loop nudge per work item

Test first: run each test task, see it fail for the stated reason, then do the
implementation task that follows it. Run tests with `python -m pytest -q <file>` from the
repository root using the interpreter the task names. Signatures, texts and order are in
plan.md. Item ids in new tests are words (`alpha`, `beta`), never a single letter that an
option table could contain.

## Phase 1: Config and class levels (US1, FR-002)

- [X] T001 In `tests/test_workspace.py`, add failing tests: an empty config loads
  `decisions.wait_hours == 24`, `decisions.cruise.enabled is True`,
  `decisions.cruise.levels == {}`, `steward.loop_window_hours == 4`,
  `steward.loop_threshold == 9`; `levels.approach = 1` loads; `levels.merge = 4`,
  `levels.message = 2`, `levels.unknown = 1` and `decisions.cruise.margin = 0.2` each raise
  `ConfigError` naming the key. Fails today: `decisions` is an unknown key.
- [X] T002 In `cli/wuwei/workspace.py`, extend `SCHEMA` and `load_config`; in
  `cli/wuwei/decision.py`, add `CLASSES` and `level` (plan.md).
- [X] T003 In `tests/test_decision.py`, add a failing table test for `decision.level`: the
  default level per class; `levels.approach = 1` gives 1; `levels.defer = 3` stays 0 (only
  lowers); `enabled = false` gives 0 for every class. Fails today: no `level`.
- [X] T004 Make T003 pass in `cli/wuwei/decision.py` if T002 did not already.

## Phase 2: Mandate block (US1, FR-001)

- [X] T005 In `tests/test_brief.py`, add failing tests for `brief.launch_prompt` and
  `brief.seat_action('builder', ...)` on a workspace with a logged builder brief (issue
  acceptance 1): first line `WUWEI brief: <path>`; contains `Mandate (design 5.2):`,
  `Decide alone:`, `Decide and record:`, `Go to the owner`, `Nothing else is a question.`;
  the assumption sentence and `retry, park, accept-residual, merge` under record;
  `defer, scope-cut, re-plan, dependency-bump, message, other` under owner; with
  `levels.approach = 1` the assumption sentence is absent and `approach` is in the owner
  list; with `enabled = false` record says `none.`; with a `.wuwei/charters/lead.md`
  holding the `## Owner preferences (interview)` block and `- risk: Also set trust_surface
  for changes touching: billing.` plus `deploy.deny = ["npm publish*"]` the prompt names
  both; the prompt has no em-dash. Fails today: no mandate.
- [X] T006 In `cli/wuwei/brief.py`, add `mandate` and append it in `launch_prompt` (plan.md).
- [X] T007 In `tests/test_runtime.py` (Codex dispatch tests), add a failing assertion that
  the Codex task prompt ends with the same `brief.mandate(root)` text. Fails today.
- [X] T008 In `adapters/runtime/codex.py` `dispatch`, append the mandate.
- [X] T009 Run `tests/test_dispatch.py`, `tests/test_build_next.py`, `tests/test_agent_launch.py`
  and `tests/test_runtime.py`; fix only tests that compare a whole prompt literal, never the
  guard.

## Phase 3: A seat question without a record is flagged (US2, FR-003, FR-004)

- [X] T010 In `tests/test_decision.py`, add failing table tests for
  `guards.decision.unrecorded(text, root)` and `check_stop(payload)`: no `?` line is 0; a
  question with no id is 1 with the citation hint; a question citing a lint-passing `D-1`
  today is 0; citing a missing `D-9` is 2 (the shared `check_question` fails closed on an
  unreadable record, and the hook blocks on 2 as on 1); a `?` only inside a fenced block or a `>` quote
  is 0; `stop_hook_active: true`, agent type `general-purpose`, and a cwd outside a
  workspace are 0 and write nothing. Fails today: no `unrecorded`, no `check_stop`.
- [X] T011 In `cli/wuwei/guards/decision.py`, add `QUESTION`, `unrecorded`, `check_stop` and
  the `GUARDS` row; in `cli/wuwei/guards/__init__.py`, add `'SubagentStop': None` to
  `MODULES['decision']`; in `cli/wuwei/steward.py`, extract `add_notes` from `review`.
- [X] T012 In `tests/test_steward.py`, add a failing test (issue acceptance 2): an approved
  item `alpha` in phase `gate` with a stopped builder seat whose transcript carries the
  brief reference; `check_stop` with a last message `Should I use a cache here?` returns 1;
  `state.read_state()['steward_notes']` holds `alpha-question-<agent>` whose text names the
  missing decision record; `dispatch.next_step('alpha')` raises `Refused` containing the
  note id and `decision record`; a second identical stop adds no second note. Fails today on
  the refusal text.
- [X] T013 In `cli/wuwei/dispatch.py` `next_step`, include the note text in the refusal.
- [X] T014 In `tests/test_hooks.py`, add a failing hook-level test piping a SubagentStop
  payload (from `tests/payloads/SubagentStop/example.json`, cwd in a temp workspace, agent
  type `wuwei:builder`, a last message with a question and valid `Blocked:`, `Gap:`,
  `Change:` lines) through `python3 -P -m wuwei hook SubagentStop`: exit 2 and stdout
  `{"decision": "block", ...}` whose reason contains `Cite a decision D-n`. Passes after
  T011; run it before T011 to see it fail.
- [X] T015 In `tests/test_guard_mutation.py`, add the `PROBES` row for
  `('decision', 'SubagentStop', None, 'check_stop')` with a WUWEI agent type and a question
  message, expected exit 1; `test_every_registered_guard_has_a_mutation_probe` fails until
  the row exists, and the disabled guard must turn its probe red.
- [X] T016 In `tests/test_runtime.py`, add a failing test: a Codex `result` whose recorded
  `rawOutput` asks `Which option do you want?` with retro lines returns exit 1 with the hint.
  In `tests/test_listen.py` (where the headless shepherd fixture lives), add a failing test: a fake `runtime.headless` returning
  `result: 'Shall I reply to the reviewer?'` makes `shepherd.headless` return 1 and the
  `shepherd.finished` payload carries `exit: 1`. Fail today: both return 0.
- [X] T017 In `adapters/runtime/codex.py` `result` and `cli/wuwei/shepherd.py` `headless`,
  call `unrecorded` (plan.md).

## Phase 4: Assume and record is reviewable (US3, FR-005)

- [X] T018 In `tests/test_verdict.py`, add failing tests: a FIX verdict whose only finding is
  `Assumption: medium specs/x/spec.md:12 assumed one process; would break when two
  processes share it; blocks: no` (with Head, probe, class sweep and retro lines) lints
  clean; the same without the failure scenario is refused with `finding 1: missing failure
  scenario`; a line `Assumptions: reviewed` does not start a finding. Fails today: `no
  finding with severity`.
- [X] T019 In `cli/wuwei/verdict.py` `finding_blocks`, extend `explicit` (plan.md).
- [X] T020 In `tests/test_brief.py`, add a failing test: a gate brief's text contains the
  `Assumptions: review the item's Assumptions:` header line; a builder brief does not.
- [X] T021 In `cli/wuwei/brief.py` `write`, add the gate header line.

## Phase 5: External confirmation and the time box (US4, FR-006)

- [X] T022 In `tests/test_decision.py`, add failing tests for `wuwei decision route D-1
  --external alpha` on a two-way own-branch record: exit 0, prints `owner`, `decision_routes`
  holds D-1, `items.alpha.assumption` is `{kind: external, decision: D-1, day, since, status:
  waiting}`, the `decision.routed` event carries `item: alpha`; an unknown item exits 1 and
  writes nothing; a repeat call writes nothing; `dispatch.next_step` for `alpha` is not
  refused because of the pending D-1 (issue: reversible work is never blocked). Fails
  today: unknown option `--external`.
- [X] T023 In `cli/wuwei/commands/decision.py` and `cli/wuwei/decision.py` `route_owner`,
  add the external route (plan.md).
- [X] T024 In `tests/test_decision.py`, add a failing table test for
  `decision.weekday_hours`: Friday 12:00 to Monday 12:00 in `Europe/Amsterdam` is 24;
  Monday 09:00 to Tuesday 08:00 is 23; a Friday to Monday span crossing the October DST change is 24 (the changed hour falls
  on Sunday, which never counts).
  Fails today: no `weekday_hours`.
- [X] T025 In `cli/wuwei/decision.py`, add `weekday_hours`.
- [X] T026 In `tests/test_watch.py`, add failing tests for `decision.waits` through
  `watch.sweep` with `WUWEI_NOW` moved (issue acceptance 3): two-way record, goal `G-1`,
  past 24 weekday hours: assumption `confirmed`, one `decision.waited` with
  `outcome: confirmed` and the recommendation, item phase unchanged, record still pending;
  one-way record: item `parked`, `blocked`, `decision: D-1`, `outcome: parked`, and
  `wuwei decision outcome D-1 <option>` resumes it; an `unplanned` or `trust_surface` item
  with a two-way record parks; under 24 weekday hours (a weekend in between) or an answered
  record changes nothing; a second sweep writes nothing new; an unreadable record makes the
  sweep count `unreadable` and exit 2. Fails today: no `waits`.
- [X] T027 In `cli/wuwei/decision.py` add `waits`; in `cli/wuwei/watch.py` `sweep`, call it.

## Phase 6: Negotiation loops (US5, FR-007 to FR-010)

- [X] T028 In `tests/test_steward.py`, add failing tests for `steward.negotiation` and
  `steward.review` with `WUWEI_NOW` fixed (issue acceptance 4): with
  `steward.loop_threshold = 6`, item `alpha` with two records naming it (mtime inside the
  window), three `gate.received`, one repeated `brief written` for `(alpha, builder)` and
  one `build.fix_opened` in the last four hours raises exactly one `negotiation.loop` event
  with `counts` `{records: 2, verdicts: 3, redispatches: 1, continuations: 1}`, two `last`
  entries and a `reason` starting `alpha is going back and forth:`; a second `review` the
  same day writes nothing; two `build.fix_opened` today with no other exchange raise it
  alone; with defaults nine exchanges raise nothing and ten raise one; exchanges older than
  the window and `build.checked` rows do not count; a record whose option table contains
  `alpha` but whose Question and Context do not is not counted; a concurrent pair of
  reviews (as `test_concurrent_reviews_record_one_note`) writes one event; `past_goal` is
  true when `memory/goals.md` gives the item's goal a date before today and false when the
  file is missing. Fails today: no `negotiation`.
- [X] T029 In `cli/wuwei/decision.py` add `naming`; in `cli/wuwei/steward.py` add `_Raised`
  and `negotiation`, and call it at the end of `review`.
- [X] T030 In `tests/test_signal_status.py`, add failing tests: `classify` gives `nudge` for
  `negotiation.loop` with `past_goal: false`, `page` with `past_goal: true`, `silent` for
  `negotiation.notified`, `nudge` (Decisions lane) for `decision.waited`; extend
  `test_emitted_kinds_have_intended_tiers` with the three kinds; `status.line(snapshot)`
  shows `loops 1` after one `negotiation.loop` event and still `loops 1` after a second
  `review`, no `loops` part with none; `nudges` lists the loop with its reason. Fails
  today: no `loops` part, `negotiation.notified` is a nudge.
- [X] T031 In `cli/wuwei/signal.py` and `cli/wuwei/commands/status.py`, add the tier, the
  silent kind and the `loops` count (plan.md).
- [X] T032 In `tests/test_listen.py`, add failing tests next to
  `test_pr_change_reaches_the_owner_dm_once` with the same owner-DM fixture: one
  `negotiation.loop` event gives one DM equal to its reason and one `negotiation.notified
  {item}` event; a second tick sends nothing; `control_plane.content = "none"` sends `An
  update is waiting in the workspace.`; a reason the outward lint refuses sends
  `LOOP_FALLBACK`; a transport exit 2 records nothing and the tick returns 2; assert the
  fallback and a generated reason pass `outward.lint(..., to_owner=True)`. Fails today: no
  loop DM.
- [X] T033 In `cli/wuwei/listen.py` `notify`, add the loop DM and `LOOP_FALLBACK`.

## Phase 7: Ask metrics (US6, FR-011)

- [X] T034 In `tests/test_metrics.py`, add failing tests (issue acceptance 5): routed D-1
  (Question names `alpha`), D-2 (Context names `alpha` and `beta`), D-3 (no item) give
  `asks_per_item == {'alpha': 2, 'beta': 1, 'day': 1}`; D-1 answered by the owner with its
  routed recommendation and D-2 with another option give `unnecessary_asks == 1`; no day
  state gives `unmeasured` for both. In `tests/test_report_retro.py`, assert the report and
  the retro text contain `asks_per_item` and `unnecessary_asks`. Fails today: keys absent.
- [X] T035 In `cli/wuwei/metrics.py` `collect`, add both metrics.

## Phase 8: Producer-only state and events (US7, FR-012)

- [X] T036 In `tests/test_state_allowlist.py`, add failing rows:
  `('negotiation_loops', 'wuwei steward run')`, `('items.A.assumption', 'wuwei decision
  route --external')` to the state refusal test and `('negotiation.loop', 'wuwei steward
  run')`, `('negotiation.notified', 'wuwei listen')`, `('decision.waited', 'wuwei sweep')`
  to the event refusal test. Fails today on the producer names.
- [X] T037 In `cli/wuwei/state.py` and `cli/wuwei/commands/event.py`, add the producer names
  (plan.md).

## Phase 9: Charters, skill, agents, template, docs (US7)

- [X] T038 In `tests/test_charters.py`, change the `cycle budget` `RULES` row to the
  negotiation budget anchor and add assertions that `_common.md` contains `Assumptions:`,
  `mandate` and `design reconsideration` exactly once each; in `tests/test_docs.py`, add a
  failing test that `configuration.md` documents `decisions.wait_hours`,
  `decisions.cruise.enabled`, `decisions.cruise.levels`, `steward.loop_window_hours`,
  `steward.loop_threshold`; `concepts.md` names the mandate block, `Assumptions:`,
  `--external` and `negotiation.loop`; `daily.md` names `loops N`; `reference.md` names
  `decision route D-n --external` and the `Assumption:` finding kind. Fails today.
- [X] T039 Edit `charters/_common.md` (version 1.1.0) and `skills/wuwei-plan/SKILL.md`, then
  regenerate `agents/*.md` with `python3 -P -m wuwei agents build` and confirm
  `python3 -P -m wuwei agents check` exits 0.
- [X] T040 Edit `templates/workspace/config.toml`, `docs/site/configuration.md`,
  `docs/site/concepts.md`, `docs/site/daily.md` and `docs/site/reference.md` (plan.md);
  keep every paragraph that names cruise saying it is not built.

## Phase 10: Verify

- [X] T041 Run `python -m pytest -q` from the repository root; everything passes.
- [X] T042 Check every changed file for em-dashes, emojis and absolute local paths; confirm
  `git diff --stat main` lists no new module under `cli/` and no new dependency.
