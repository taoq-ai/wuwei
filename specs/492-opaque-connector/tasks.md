# Tasks: any connector name resolves its channel, config lists keep their defaults, unknown connectors, channels and people are learned on one card

**Input**: `specs/492-opaque-connector/` (spec.md, plan.md, contracts/outbound-learn.md)

Test first: run each test task with the command given and see it fail for the expected
reason before its implementation task starts. Run from the repository root with the
interpreter your task names. Fixtures only: UUID servers
`00000000-0000-4000-8000-00000000000n`, channels `C01`, `C02`, people `U01`, `U02`,
`ada@example.com`, organisation `acme`. No absolute local paths, emojis or em-dashes in any
file.

## Phase 1: US1, any connector name resolves its channel

- [X] T001 Test, `tests/test_outward.py`: `test_vocabulary` (plan Design 2), a table over
  `wuwei.guards.outward.resolve(tool, None)` for UUID-server names:
  `conversations_add_message`, `chat_postMessage`, `add_reaction` slack; `create_issue`,
  `add_issue_comment` tracker; `create_draft`, `label_message`, `trash_thread` mail;
  `append_block`, `create_page` docs; `create_issue_label` (ambiguous), `send_message`,
  `frobnicate_widget` empty; `conversations_search_messages`, `channels_list`,
  `slack_search_public` empty (reads). Run `python -m pytest -q tests/test_outward.py -k
  vocabulary` (fails: no `resolve`).
- [X] T002 Implement `_words`, `VOCABULARY` and `resolve` without the alias step in
  `cli/wuwei/guards/outward.py`; `tool_kind` uses `_words`; `_check` calls `resolve` at both
  match sites (plan Design 2). Rerun T001; pass.
- [X] T003 Test, `tests/test_outward.py`: `test_resolve_opaque` (spec US1 scenarios 1 to 3):
  through `check_tier` and the hook, `mcp__<uuid>__conversations_search_messages` exits 0
  with no event, `mcp__<uuid>__slack_send_message` and
  `mcp__<uuid>__conversations_add_message` draft with `channel slack` in the reason. Run
  `python -m pytest -q tests/test_outward.py -k resolve_opaque` (fails:
  `slack_send_message` gets the unmatched-write refusal).
- [X] T004 Implement the brand-anywhere built-in rules in `cli/wuwei/workspace.py` and bump
  `CONFIG_CACHE_VERSION` to 7 (plan Design 1). Rerun T003 and `python -m pytest -q
  tests/test_outward.py tests/test_workspace.py`; the existing rule rows still pass.
- [X] T005 Test, `tests/test_outward.py`: `test_alias_resolves_and_reads_still_pass` (spec
  US1 scenario 4): with `[outward.servers]` mapping a UUID to `slack`,
  `mcp__<uuid>__send_message` drafts with `channel slack`, `conversations_history` and
  `slack_read_channel` pass; a channel outside the constraint (`"chat"`) is a config error.
  Run `python -m pytest -q tests/test_outward.py -k alias` (fails: unknown key
  `outward.servers`).
- [X] T006 Implement `SCHEMA['outward']['servers']` in `cli/wuwei/workspace.py` and the alias
  step of `resolve` in `cli/wuwei/guards/outward.py` (plan Design 1 and 2). Rerun T005;
  pass.
- [X] T007 Test, `tests/test_outward.py`: add `RECORDED_OPAQUE` (the #469 Slack, Linear and
  GitHub lists plus a mail list: `create_draft`, `update_draft`, `send_message`, `forward`,
  `label_message`, `trash_thread`, `get_thread`, `search_threads`, `list_drafts`, each under
  a UUID server) with outcomes `read`, `draft` or `learn`, and `test_recorded_opaque_tools`;
  add `test_learn_reasons` (spec US1 scenarios 5 and 6: an unknown write in each posture and
  `frobnicate_widget` under strict and as the guarded nudge name the connector and
  `bin/wuwei outbound learn --tool <tool>`; with `outbound.learn = "off"` the reason names
  only the draft) and `test_no_config_set_in_reasons` (every reason those tests produce lacks
  `config set`). Update the #469 tests that pin `config set outward.tool_patterns` or exit 2
  for names the vocabulary now resolves: `test_real_mcp_write_names`,
  `test_recorded_server_tools`, `test_unmatched_write_names_the_line` (renamed
  `test_unmatched_write_names_learn`), `test_unknown_tool_recorded_once`, `test_probe_tools`
  (spec A12). Run `python -m pytest -q tests/test_outward.py -k "recorded or learn or
  real_mcp or unmatched or unknown_tool or probe or config_set"` (fails: reasons carry the
  config line; `outbound.learn` unknown).
- [X] T008 Implement `SCHEMA['outbound']['learn']` in `cli/wuwei/workspace.py` and the new
  reasons in `_unmatched`, `cli/wuwei/guards/outward.py` (plan Design 3). Rerun T007; pass.
- [X] T009 Test, `tests/test_outward.py`: `test_draft_names_unknown_audience` (spec US3
  scenario 1 at the guard): a send through an aliased `mcp__<uuid>__send_message` to `C01`
  (not a work channel) with `thanks <@U01> <@U02>` drafts and the reason names `C01`, `2
  mentions` and `bin/wuwei outbound learn`; to a work channel with known people the reason is
  the plain draft text; with `learn = "off"` no learn text. Also assert `classify` returns
  the same `(code, tier)` as before for these inputs. Run `python -m pytest -q
  tests/test_outward.py -k unknown_audience` (fails: no learn text).
- [X] T010 Implement `MENTION` and `unknown_audience` in `cli/wuwei/outward.py` (`classify`
  uses `MENTION`) and the draft-branch suffix in `_check`, `cli/wuwei/guards/outward.py`
  (plan Design 3 and 4). Rerun T009 and `python -m pytest -q tests/test_outward.py
  tests/test_hooks.py`; pass, the #346 import tests unchanged.

## Phase 2: US2, config lists keep their defaults

- [X] T011 Test, `tests/test_setup.py`: `test_list_set_appends` (spec US2 scenarios 1 and 2:
  `outbound.work_channels` gets the effective list plus `C1`; `outward.tool_patterns` keeps
  the five built-in rules plus the new one), `test_list_set_replace` (`--replace` writes only
  `C1`), `test_table_set_adds_entries` (spec US2 scenario 3: two `config set outbound.people`
  calls keep both entries; the written keys are quoted), `test_replace_refused_on_scalar`
  (spec US2 scenario 5: exit 1, nothing written). Extend the file's `config_set` helper with
  a `replace` argument. Run `python -m pytest -q tests/test_setup.py -k "appends or replace
  or adds_entries"` (fails: the value replaces the list).
- [X] T012 Implement `schema_at`, `effective`, `merged` and the `set_value` change in
  `cli/wuwei/commands/setup.py`, `set --replace` in `cli/wuwei/commands/config.py`, and the
  quoted paths in `calibrate.apply`, `cli/wuwei/calibrate.py` (plan Design 5). Rerun T011
  and `python -m pytest -q tests/test_setup.py tests/test_calibrate.py`; pass.
- [X] T013 Test, `tests/test_setup.py`: `test_config_show_tags` (spec US2 scenario 4):
  `config show outward.tool_patterns` after one owner rule prints six rows, five `default`
  and one `owner`; a scalar prints one row; an unknown key exits 1. Run `python -m pytest -q
  tests/test_setup.py -k show_tags` (fails: no `show` action).
- [X] T014 Implement `config show` in `cli/wuwei/commands/config.py` (plan Design 5). Rerun
  T013; pass.

## Phase 3: US4, no reason tells a seat to edit the guard's config

- [X] T015 Test, `tests/test_protect_state.py`: `test_guard_config_set_refused` (spec US4
  scenario 1), a seat payload (`agent_id` set) running `bin/wuwei config set <key> '[]'` for
  `outward.tool_patterns`, `outbound.work_channels`, `security.posture` and `grants.x` under
  observe, guarded and strict: refused, the reason names the owner and `outbound learn` and
  lacks `propose the line` and `config set`; `owner.name` keeps today's reason. Run
  `python -m pytest -q tests/test_protect_state.py -k guard_config` (fails: today's reason).
- [X] T016 Implement `GUARD_KEYS`, `GUARD_CONFIG` and the `config set` branch in
  `cli/wuwei/guards/protect_state.py` (plan Design 8). Rerun T015; pass.
- [X] T017 Test, `tests/test_protect_state.py`: `test_outbound_learn_planner_only` (spec US4
  scenario 2: a seat running `bin/wuwei outbound learn --tool mcp__<uuid>__send_message` is
  refused with a reason naming the planner; the registered planner session passes under
  guarded and strict) and `test_config_show_outbound_learn_passes` (a seat running
  `bin/wuwei config show outbound.learn` and `bin/wuwei outbound learn --help` passes). Run
  `python -m pytest -q tests/test_protect_state.py -k "planner_only or show_outbound"`
  (fails: the seat is not refused).
- [X] T018 Implement the `('outbound', 'learn')` row and the planner pass in
  `cli/wuwei/guards/protect_state.py` (plan Design 8). Rerun T017 and `python -m pytest -q
  tests/test_protect_state.py`; pass.

## Phase 4: US3, unknown connector, destination or people learned and confirmed once

- [X] T019 Test, `tests/test_outbound_learn.py` (new): `test_reserved` (`wuwei event
  outbound.learned` and `outbound.proposed` exit 1; `state.set_state('outbound_learn', ...)`
  raises `reserved`). Run `python -m pytest -q tests/test_outbound_learn.py -k reserved`
  (fails: the kinds are free).
- [X] T020 Implement the producers in `cli/wuwei/state.py` (`STATE_PRODUCERS`) and
  `cli/wuwei/commands/event.py` (`EVENT_PRODUCERS`) (plan Design 9). Rerun T019; pass.
- [X] T021 Test, `tests/test_outbound_learn.py`: `test_learn_guards` (contract Flow 1 to 8):
  `"off"` exits 1; an invalid `--tool` exits 1; an unresolved tool without `--as` exits 1
  naming `--as`; a Slack tool without listings exits 1 and prints the listing step with the
  full command; listings with `--as mail` exit 1; a missing file exits 2; rows with a bad id,
  a `|` or newline in a name, an extra key or a duplicate id exit 1 naming the file. Nothing
  is written in any case. Run `python -m pytest -q tests/test_outbound_learn.py -k guards`
  (fails: no `learn` action).
- [X] T022 Implement the `learn` subparser, `learn` steps 1 to 8 and `_rows` in
  `cli/wuwei/commands/outbound.py` (plan Design 6; contract Flow, Listing files). Rerun T021;
  pass.
- [X] T023 Test, `tests/test_outbound_learn.py`: `test_proposal_filters` (contract Proposal;
  spec US3 scenario 8): with today's `pr_reviewers` `{"acme/app#7": ["ada", "bo"]}` and
  `shepherd.authors` or `author_logins` mapping their emails, a shared channel, a `D` id, an
  external channel and an existing work channel are dropped; reviewers by email and by
  mention are proposed; a stranger is not; a person named only in today's `plan.md` is
  proposed with `card` and not without; `email` entry when the domain is in
  `company_domains`, `org` entry when only the organisation is in `code_host_orgs`, neither
  skipped with the `not proposed` line; an already aliased server with nothing new exits 1.
  Call `propose` directly on fixture state. Run `python -m pytest -q
  tests/test_outbound_learn.py -k filters` (fails: no `propose`).
- [X] T024 Implement `propose` in `cli/wuwei/commands/outbound.py` (contract Proposal).
  Rerun T023; pass.
- [X] T025 Test, `tests/test_outbound_learn.py`: `test_card` (spec US3 scenario 2): under
  `"card"` and guarded, one run with the fixture listings writes exactly one `D-n` record
  that `bin/wuwei decision lint` accepts, routes it (`decision_routes`), stores
  `outbound_learn[D-n]` with `answered` null, and prints one widget whose question is
  `D-n: Connector <uuid> is Slack; add 1 work channel and 2 people? ...` with labels
  `Approve (Recommended)`, `Approve channels only`, `Defer: keep as drafts` and record
  `wuwei decide D-n "<label>"`; a second run prints the same widget and writes no second
  record. Run `python -m pytest -q tests/test_outbound_learn.py -k card` (fails: no record).
- [X] T026 Implement `ask` and Flow steps 4, 9 and 10 (card branch) in
  `cli/wuwei/commands/outbound.py` (contract Decision record, State). Rerun T025; pass.
- [X] T027 Test, `tests/test_outbound_learn.py`: `test_answers` (spec US3 scenarios 3 to 5),
  each through `commands.decision.owner_outcome` with a fake confirm: `approve` writes
  `outward.servers`, `C01` in `outbound.work_channels` and `slack:U01`, `slack:U02` in
  `outbound.people`, records one `outbound.learned` event with ids only and marks `answered`,
  and the same send (`mcp__<uuid>__send_message`, `C01`, `thanks <@U01> <@U02>`) then passes
  `check_tier` and `check_lint`; `channels` writes alias and channel and the send still
  drafts; `keep` writes nothing, the send drafts, and a new `outbound learn` for that server
  exits 1 naming the kept decision; answering twice writes nothing new. Run `python -m pytest
  -q tests/test_outbound_learn.py -k answers` (fails: the answer writes no config).
- [X] T028 Implement `apply` and Flow step 5 in `cli/wuwei/commands/outbound.py`, and the
  `owner_outcome` change in `cli/wuwei/commands/decision.py` (plan Design 6 and 7; contract
  Apply). Rerun T027 and `python -m pytest -q tests/test_decision.py`; pass.
- [X] T029 Test, `tests/test_outbound_learn.py`: `test_auto` (spec US3 scenario 6):
  `"auto"` under guarded and under observe writes the config at once with reviewers only (a
  record-named person is not learned), prints no widget, writes no record and records one
  `outbound.learned` event with `mode` `auto`; under strict it writes a record and prints the
  widget as under `"card"`. Run `python -m pytest -q tests/test_outbound_learn.py -k auto`
  (fails: auto still asks).
- [X] T030 Implement the `"auto"` branch of Flow step 10 in `cli/wuwei/commands/outbound.py`.
  Rerun T029; pass.

## Phase 4b: scope addition (classes and modes, spec FR-016 to FR-018)

- [X] T033 Test, `tests/test_outward.py`: `test_vocabulary` rows for camelCase Jira names,
  a Notion block append, a GitHub PR comment, Sentry `resolve_issue`, `mute_alert` and
  `update_alert_rule` (other) and `resolve-library-id` (nothing); the opaque GitHub PR comment
  drafts; `test_class_modes`: a Jira comment, a Notion append and a GitHub PR comment through
  fixture UUID connectors draft by class, a Sentry resolve without text passes as `other`
  `send`, a disagreement drafts, an owner-name lint refuses, and owner modes `draft`,
  `refuse` and `send` (a Slack send to an unknown channel passes) apply; reads ignore modes.
- [X] T034 Implement `other`, `outward.modes`, the vocabulary rows, `mode` and the mode
  branch in `cli/wuwei/guards/outward.py`, `check_send` in `cli/wuwei/outward.py`, and the
  schema in `cli/wuwei/workspace.py`. Rerun T033; pass.
- [X] T035 Test, `tests/test_outbound_learn.py`: `test_card` shows `is Slack, mode draft` and
  `Approve, mode send`; `test_other_card`: `--as other` gives `is other, mode send`, the
  `refuse` answer records `outward.servers` and `outward.modes`; `test_template_tables_are_sections`.
- [X] T036 Implement the card rows and the mode answer in `cli/wuwei/commands/outbound.py`;
  template sections and docs. Rerun T035; pass.

## Phase 5: docs and the full suite

- [X] T031 Docs (plan Design 10): `docs/site/configuration.md`, `docs/site/security.md`,
  `docs/site/reference.md`, `templates/workspace/config.toml`, `skills/wuwei-plan/SKILL.md`.
  Run `python -m pytest -q tests/test_docs.py tests/test_templates_errors.py tests/test_reasons.py tests/test_workspace.py`
  and fix any documented-key or template check it names.
- [X] T032 Run the full suite, `python -m pytest -q`; everything passes. Check every file
  written for em-dashes and emojis and remove any; check no absolute local path or owner
  data (channel ids, names) entered the repository.
