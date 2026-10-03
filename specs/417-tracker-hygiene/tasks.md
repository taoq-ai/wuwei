# Tasks: Tracker hygiene

Test first: run each test task, see it fail for the stated reason, then do the implementation
task that follows it. Run tests with `python -m pytest -q <file>` from the repository root.
Signatures, texts, templates and line anchors are in plan.md. Core tests use the fake port in
`tests/fakes/tracker.py` through `monkeypatch.setattr(registry, 'load', ...)`; adapter tests
replay recorded fixtures as `tests/test_reference_adapters.py` `replay` does. No network.

## Config, state keys and event kinds (FR-001, FR-002)

- [X] T001 In `tests/test_workspace.py`, add a failing test: a default config has the nine
  `[tracker]` keys with the 5.11 defaults; `skip_tiers = ["LIGHT"]`, `auto = ["merge"]`, `log =
  ["items"]` and `create = ["items"]` each raise `ConfigError`; `adapters.tracker` stays
  `none`; `templates/workspace/config.toml` loads. Fails today: `KeyError: 'required'`.
- [X] T002 In `cli/wuwei/workspace.py` `SCHEMA['tracker']`, add the keys; in
  `templates/workspace/config.toml`, add the commented lines and fix the `[outbound]` tracker
  comment; in `cli/wuwei/state.py` `STATE_PRODUCERS` add `tickets` and `tracker_log`; in
  `cli/wuwei/commands/event.py` `EVENT_PRODUCERS` add the five kinds.
- [X] T003 In `tests/test_env_credentials.py`, add a failing test: `JIRA_API_TOKEN`, `JIRA_EMAIL`,
  `GITHUB_TRACKER_TOKEN` are kept from `env.child_environment()` and redacted; `JIRA_SITE` is
  kept from seats and not redacted; `config check` with `adapters.tracker = "jira"` and no
  variables names all three Jira variables. Fails today: the names are not credentials.
- [X] T004 In `cli/wuwei/env.py` (`CREDENTIALS`, `PUBLIC`) and `cli/wuwei/commands/config.py`
  `requirements`, add the variables.

## Port, HTTP helper, outward and drafts (FR-008, FR-010)

- [X] T005 In `tests/test_adapters.py`, add `('tracker', 'comment', ('item', 'text', 'category'),
  False)` to `CALLS`; add a test that `adapters.tracker.none.comment('ENG-1', 'x', 'progress',
  root=tmp)` returns exit 2 `tracker adapter is none`. Fails today: `PARAMETERS` mismatch and no
  `comment`.
- [X] T006 In `cli/wuwei/registry.py` `PARAMETERS['tracker']`, add `comment`; in
  `adapters/tracker/none.py`, add `comment` (outward decorated).
- [X] T007 In `tests/test_reference_adapters.py`, add failing tests for `adapters/_http.py`
  `request`: `method='GET'` with `payload=None` sends no body and uses GET; `method='PUT'` with
  an empty 204 body returns `{}`; existing callers still POST JSON. Fails today: `TypeError`
  (no `method`) and `JSONDecodeError` on the empty body.
- [X] T008 In `adapters/_http.py`, extend `request` and add `settings(root)`.
- [X] T009 In `tests/test_outward.py`, add a failing table test for `outward.classify(text, root,
  config, {'item': 'ENG-1', 'text': text, 'category': c}, kind='tracker')`: `progress`, `pr`,
  `close` send with defaults; `decisions`, `verdicts`, `items`, `bugs` draft; `bugs` sends when
  in `auto`; a text with `@pat`, a sensitive keyword or a commitment pattern drafts whatever
  `auto` says; with `adapters.tracker = "github"` and `project = "outside/repo"` not in
  `code_host_orgs` every category drafts; a nested `draft` with `category` and `parent` is valid
  input to `outward._text`. Fails today: every tracker write drafts and `category` is an
  unsupported field.
- [X] T010 In `cli/wuwei/outward.py`, add `category` and `parent` to `METADATA_FIELDS`, the
  tracker branch in `classify` and `_external_tracker`.
- [X] T011 In `tests/test_drafts.py`, add failing tests: a tracker `comment` that drafts stores a
  row with operation `comment` and `drafts approve` sends it through `comment`; approving a
  tracker `create` draft with category `items` whose adapter returns `{'id': 'ENG-9', 'url':
  ...}` records `tickets[item] == {'id': 'ENG-9', 'source': 'create'}`, one `tracker.created`
  event and a `written` `tracker_log` entry. Fails today: `drafts: unsupported operation` and
  nothing recorded.
- [X] T012 Create `cli/wuwei/tracker.py` with `CLASSES`, `KINDS`, `ticket` and `record` (plan.md;
  top-level imports `re`, `wuwei.state`, `wuwei.workspace` only); in `cli/wuwei/drafts.py`, add
  `comment` to `OPERATIONS['tracker']` and the `tracker.record` call in `approve`.

## The rule: `tracker.check` and the refusal points (US1, FR-003, FR-004, FR-005)

- [X] T013 New `tests/test_tracker.py`: failing table test for `tracker.check` and
  `tracker.ticket`: `off` with adapter `none` and with `required = false`; `ticket` when
  `tickets` has the item; `skipped` for lead tier `light` and for recorded `gates.tier` `light`
  with `skip_tiers = ["light"]`; `missing` with no tier at all; a recorded `gates.tier`
  `standard` overrides a lead `light` (missing); the missing reason equals the plan.md text; a
  pending `items` tracker draft for the item switches it to `bin/wuwei drafts approve
  <draft>`. Fails today: `AttributeError: check`.
- [X] T014 In `cli/wuwei/tracker.py`, add `in_force`, `check` and `pending`.
- [X] T015 In `tests/test_dispatch.py`, add failing tests: tracker `linear` (fake port), an
  approved item at `gate` with no ticket: `main(['dispatch', 'next', item])` exits 1 and stderr
  names `bin/wuwei tracker create <item>` and `bin/wuwei plan set <item> ticket=<id>`; with
  `tickets` seeded in the day's `state.json` it returns the gates action; a `light` lead tier
  with `skip_tiers = ["light"]` dispatches while the recorded tier is `light` and refuses once it
  is `standard`; `tracker_call(item, 'claim')` claims the ticket id and the event has `ticket`.
  Fails today: dispatch proceeds without a ticket.
- [X] T016 In `cli/wuwei/dispatch.py` `next_step`, call `tracker.check` after the tier block; in
  `tracker_call`, use `tracker.ticket(...) or item` and add `ticket` to the event payload.
- [X] T017 In `tests/test_build_next.py`, add a failing test: with a tracker configured and
  `required` in force, `build next <item>` for an item without a ticket exits 1 with the reason
  and writes no `builds` row; with a ticket the claim goes to the ticket id (fake port records
  `('claim', ('ENG-7',), ...)`). Fails today: build starts and claims the item id.
- [X] T018 In `cli/wuwei/commands/build.py` `next_action`, call `tracker.check` before `_save`.
- [X] T019 In `tests/test_plan.py`, add failing tests: `plan approve` with two candidates without
  tickets exits 1, stderr lists both reasons, state has no approved items; a candidate with
  `"ticket": "ENG-3"` and one discovered with `source == 'tracker'` record `tickets` with
  sources `candidate` and `tracker`; an invalid `ticket` value is exit 2; `--import-yesterday`
  carries the prior day's ticket with source `yesterday`; a `light` candidate under
  `skip_tiers = ["light"]` is approved without a ticket and one `tracker.skipped` event is
  written. Fails today: approve ignores tickets.
- [X] T020 In `cli/wuwei/plan.py`, add the `ticket` check in `_proposal` and the ticket logic in
  `approve`.
- [X] T021 In `tests/test_intraday_intake.py`, add a failing test: with `required` in force,
  `discovery.intake` of a `start`-eligible candidate without a ticket records an owner
  proposal whose `reason` names `tracker create`; `main(['plan', 'add', item])` exits 1; a
  candidate from the tracker source is admitted with its id as ticket. Fails today: admitted.
- [X] T022 In `cli/wuwei/plan.py` `add`, add the ticket choice and check.
- [X] T023 In `tests/test_plan.py`, add failing tests for `plan set`: `main(['plan', 'set', item,
  'ticket=ENG-4'])` with `created` exit 0 records `{'id': 'ENG-4', 'source': 'set'}` and one
  `plan.set` event; `created` exit 2 exits 2 and records nothing; an unknown item exits 1;
  `owner=pat` exits 2. Fails today: no `set` verb.
- [X] T024 In `cli/wuwei/plan.py` add `set_ticket`; in `cli/wuwei/commands/plan.py` add the verb;
  in `cli/wuwei/commands/__init__.py` add `plan set` to `WRITES`.
- [X] T025 In `tests/test_agent_launch.py`, add a failing test: a logged builder brief for an
  item without a ticket, tracker in force: the PreToolUse `Agent` check returns exit 1 with the
  reason and reserves no seat; with a ticket it launches; with adapter `none` it launches.
  Fails today: the launch is reserved.
- [X] T026 In `cli/wuwei/guards/agent_launch.py` `reserve`, add the lazy check.
- [X] T027 In `tests/test_hooks.py`, extend nothing; run it to confirm no new hook import
  (`wuwei.profiles`, `wuwei.registry` on paths that did not load it) after T026.

## Creation (US2, FR-006)

- [X] T028 In `tests/test_tracker.py`, add failing tests for `tracker create`: `--bug <item>
  "<title>" --evidence "cli/x.py:12"` with defaults drafts once (exit 1, prints `bin/wuwei drafts
  approve`), the draft's `inputs['draft']` has `category == 'bugs'`, `parent` = the item's
  ticket and the evidence in `description`; a second identical call writes no new draft or
  event; with `bugs` in `auto` it creates (exit 0), writes one `tracker.created` event with
  class, subject, ticket and parent, and a second call prints the ticket and writes nothing;
  evidence `/srv/x/file.py:3` exits 1 and writes nothing; `--follow-up` with `create = ["bugs"]`
  exits 1 naming `tracker.create`; `tracker create <item>` builds title and description from the
  proposal candidate; adapter `none` exits 2. Fails today: no `tracker` command.
- [X] T029 In `cli/wuwei/tracker.py`, add `create`; new `cli/wuwei/commands/tracker.py` with
  `create`, `log`, `done`; add the three paths to `WRITES` in `cli/wuwei/commands/__init__.py`;
  extend `tests/fakes/tracker.py` with `create`, `comment`, `created`.

## Comments (US3, FR-007)

- [X] T030 In `tests/test_build.py`, add a failing test: `complete_checks` with two commands, one
  failing, writes a `build.checked` event with `passed == 1` and `failed == 1`. Fails today:
  the payload has only `item`.
- [X] T031 In `cli/wuwei/commands/build.py`, add `extra` to `_save` and the counts in
  `complete_checks`.
- [X] T032 In `tests/test_tracker.py`, add the acceptance 3 test: an item with ticket `ENG-1`;
  today's events seeded through the CLI writers (a `decision.decided` naming the item, a phase
  change to `gate`, a `gate.received` with one blocking finding); `main(['tracker', 'log'])`
  with defaults sends the progress comment (`[<day> <item>] Phase: gate.`), drafts the decision
  and verdict comments (`Review quality (initial): FIX, 1 blocking findings.`), and records
  three `tracker_log` outcomes; a second run makes no port call and no new event. Add: a
  `pr.raised` gives `Pull request: acme/app#1.`; a merged phase gives `Merged in acme/app#1.`
  and no `Phase: merged.`; a `plan carry` gives `Carried to <day + 1> (D-1).` and no decision
  comment; kinds not in `log` are skipped; an item without a ticket is skipped; adapter `none`
  exits 0 with no call. Fails today: no `tracker.log`.
- [X] T033 In `tests/test_tracker.py`, add the acceptance 4 test: `max_per_item_per_day = 3` and
  five progress entries: two single comments, one fold `Folded 3 updates: progress 3`, one
  `tracker.folded` event with the counts; a later entry that day is recorded `folded` with no
  call and no event. Add: a comment the port refuses (exit 1 without a stored draft) is recorded
  `refused` with its reason and not retried; a port exit 2 records nothing for that key, `log`
  returns 2, and the next run retries it; a fold holding a `decisions` entry is sent with
  category `decisions`. Fails today: no `tracker.log`.
- [X] T034 In `cli/wuwei/tracker.py`, add `log` with the templates, claim and settle, cap and
  fold.
- [X] T035 In `tests/test_watch.py`, add a failing test: `watch.sweep` calls `tracker.log` once;
  when it returns 2 the sweep counts one more `unreadable` and exits 2. Fails today: not called.
- [X] T036 In `cli/wuwei/watch.py` `sweep`, add the `tracker.log` block.

## Close (US4, FR-009)

- [X] T037 In `tests/test_close_branches.py`, add the acceptance 6 test: an approved item merged
  today with ticket `ENG-1` and no `tracker.call` done event exit 0: `closing.unresolved` is a
  finding naming `bin/wuwei tracker done <item>`; with `strict_close = false` it is not a
  finding and the line is printed to stderr; after `main(['tracker', 'done', item])` with the
  fake transition exit 0 the finding is gone; `wuwei close` runs `tracker.log` once after
  `closing.check` returns 0. Fails today: no finding, no log.
- [X] T038 In `cli/wuwei/closing.py` `unresolved` and `cli/wuwei/commands/close.py` `run`, add the
  check and the log call.
- [X] T039 In `tests/test_outcome_metrics.py`, add a failing test: `_references` keys an item with
  a recorded ticket by the ticket id, so `history` and `created` are called with `ENG-1`. Fails
  today: called with the item id.
- [X] T040 In `cli/wuwei/metrics.py` `_references`, key by ticket.

## Adapters (US5, FR-010)

- [X] T041 Record fixtures `tests/fixtures/tracker/linear.json`, `jira.json`, `github.json`
  (responses in call order, neutral ids). New `tests/test_tracker_adapters.py`: one test
  parametrized over the three adapters replays its fixture and calls `backlog`, `claim`,
  `transition`, `create` (with a parent), `comment`, `history`, `created` (outward
  `check_call` monkeypatched to `(0, '')`): every call exits 0; backlog rows have `id`, `title`,
  `url`, `updated`, `state`; `create` returns `{id, url}`; history rows have `createdAt` and
  `toState.name`; `created` is a string; asserts the request method and URL per call (Jira GET
  for transitions, PUT for assignee; Linear `parentId`; GitHub `Related: <parent>` in the body
  and the `bug` label). Plus: a missing credential exits 2 naming it with no request, for
  each adapter; `JIRA_SITE` without `https://` exits 2. Fails today: no `jira` or `github`
  module, Linear has no `comment` and returns `{'id': uuid}`.
- [X] T042 In `adapters/tracker/linear.py`, extend `create` and add `comment`; update
  `tests/test_reference_adapters.py:87` and `tests/test_drafts.py:370` for the new return and
  draft shape.
- [X] T043 New `adapters/tracker/jira.py`.
- [X] T044 New `adapters/tracker/github.py`.

## Setup, interview, doctor (US6, FR-011)

- [X] T045 In `tests/test_setup.py`, add a failing test: a repository whose `README.md` links
  `https://linear.app/acme` prints `tracker links: linear.app (<repo>/README.md)`; nothing in
  config changes. Fails today: no line.
- [X] T046 In `cli/wuwei/commands/setup.py` `discover`, add the link scan.
- [X] T047 In `tests/test_interview.py`, add a failing test: `question('tracker')` lists Linear,
  Jira, GitHub, None in that order; `effects('tracker', 'jira PROJ')` sets `adapters.tracker`
  and `tracker.project`; `effects('tickets', 'All but light items')` sets `skip_tiers`;
  `effects('updates', 'Nothing')` sets `tracker.auto = []`. Fails today: no Jira, no questions.
- [X] T048 In `cli/wuwei/interview.py` `QUESTIONS`, change `tracker` and add `tickets` and
  `updates`; adjust `tests/test_docs.py::test_interview_options_lead_with_plain_words` only if
  its fixed option list breaks.
- [X] T049 In `tests/test_doctor.py`, add a failing test: tracker `linear`, `required` true and a
  backlog exit 2 gives a `fail` tracker row naming `LINEAR_API_KEY` and `bin/wuwei config set
  tracker.required false`; exit 0 is `ok`; `none` is `ok`. Fails today: no row.
- [X] T050 In `cli/wuwei/commands/doctor.py`, add `_tracker` and append it in `diagnose`.

## Owner surfaces, docs, charters (FR-011)

- [X] T051 In `tests/test_next.py`, add a failing test: an item with ticket `ENG-1` at `implement`
  gives a step text holding `item-1 (ENG-1)`. In `tests/test_listen.py`, a negotiation loop
  notice for that item ends with `Ticket: ENG-1.`. In `tests/test_board_mcp.py`, the Work table
  has a `Ticket` column and a `Tickets created` table lists a `tracker.created` event. Fails
  today: no ticket shown.
- [X] T052 In `cli/wuwei/commands/next.py` `step`, `cli/wuwei/listen.py` `notify` and
  `cli/wuwei/commands/board.py` `read`, show the ticket.
- [X] T052a In `tests/test_dispatch.py`, add the end-to-end acceptance 1 test (passes once T016,
  T029 and T052 are in; if it fails, fix the code, not the test): fake port `create` returning
  `{'id': 'ENG-7', 'url': ...}`, `auto` including `items`; `dispatch next` exits 1 naming
  `tracker create`; `main(['tracker', 'create', item])` exits 0; `dispatch next` returns the
  gates action; `main(['board'])` output has `ENG-7` in the item's row.
- [X] T053 Run `tests/test_docs.py` after T002 and T029: it fails on the new template keys and
  commands. Then update `docs/site/configuration.md`, `adapters.md`, `concepts.md` (glossary:
  ticket, tracker hygiene, fold), `daily.md` and `reference.md` until it passes; no paragraph
  that mentions cruise without "not built".
- [X] T054 In `tests/test_charters.py`, add a failing assertion that `charters/_common.md` (the
  one home every builder and gate reads; `test_charter_sentences_have_one_home` forbids a copy
  per charter) names `tracker create --bug` as the exception to the follow-up rule, and
  `charters/planner.md` names `tracker create <item>` and `tracker create --follow-up`. Then edit
  `charters/_common.md` and `charters/planner.md` and regenerate `agents/` with `bin/wuwei agents
  build`.

## Finish

- [X] T055 Update existing tests that configure a tracker and dispatch items (plan.md "Existing
  tests that change") so they pass with `required` in force or set `required = false`.
- [X] T056 Run `python -m pytest -q`; everything passes. Grep the changed files for em-dashes,
  emojis and absolute local paths; remove any.

## Build notes

- T030 landed in `tests/test_build_next.py` (it has the seat fixture), T037 in `tests/test_stop.py`
  (it has the close fixture); `tests/test_close_branches.py` has no workspace fixture.
- `bin/wuwei tracker` joins the Daily group of `bin/wuwei --help` (`tests/test_cli.py` refuses an
  ungrouped command).
