# Implementation Plan: outward send is an exact tool allowlist and the owner's own surfaces are local; tiers, drafts, learning cards, graph, who and reply go

**Branch**: `b5-guards` | **Date**: 2026-10-11 | **Spec**: [spec.md](spec.md)

Line numbers are at 703b40de, the batch base. Part 15 (#837) lands first on this branch, so:

- `workspace.posture` is gone and `guards.enforce` exists;
- `guards.FLOOR` holds `outward.check_tier`;
- the strict branches of `outward.py` (`decide`, `check_lint`), `drafts.py`,
  `commands/outbound.py` and `tracker.py` are gone, with the three `tracker.py` LEFT rows.

Locate code by function name: part 15 shifted lines in those files.

## Summary

The outward guard keeps three answers for an MCP write: local (a #727 local tool, or a call
whose every destination is the owner's own surface), allowed (an exact name in
`outward.allow`), or refused, naming the `config set ... --add` line whose Owner step card adds
it. The canary floor and the outward-text lint (design 4.3) stay on every send. WUWEI's own
adapter ports (the outward duties) keep the canary check and the lint and lose the tiers and
the drafts. Deleted with their tests, config keys, docs and charter lines:

- the tier table, audience classes and topics;
- the draft queue and `wuwei drafts`;
- `wuwei outbound` (`tier`, `tiers`, `explain`, `learn`, `answer`);
- the register (`graph.py`, `.wuwei/graph.json`) and `wuwei who`;
- `wuwei reply`;
- `wuwei lint tone`.

## Technical Context

Stdlib-only Python 3.11+, pytest dev-only. Net deletion. One new config key (`outward.allow`),
one new owner key (`outbound.owner.pages`), and one new destination key (`canvas_id`). Run only
the touched test files; CI runs the suite.

## Constitution Check

- I: nothing added.
- II: the send check fails closed. An unreadable payload or config is exit 2; an unknown tool
  name is a refusal.
- III: one send policy (`guards/outward.check_send`), one owner predicate
  (`outward.owner_only`) and one port policy (`outward.check_call`).
- IV: red tests first for the three acceptance lines (US1, US2, US4), then deletions with their
  tests.
- V: about 3,000 lines of code and 4,500 lines of tests go.
- VII: outward sends to other people stay the owner's decision (`outward.allow`, on the floor);
  canary egress stays a records floor.
- Design spec ownership: part of the owner-approved #789 pass.

## Process control: what each removed unit was

| Unit | Kind | Where its job goes |
| --- | --- | --- |
| Tier table (`DEFAULT_TIERS`, `BROAD_ROWS`, `MODE_TIERS`, `outbound.tiers`, `default_tier`, `outward.modes`), audience classes (`outbound.people`, `channel_classes`, `work_channels`, `external_channels`, `company_domains`, `outward.classes`), topics (sensitive, commitment, disagreement, thread) and `classify` | (a) seats and the planner reason about which tier a message takes | one exact allowlist; the owner adds a tool once |
| Draft queue (`drafts.py`, `wuwei drafts`, Draft cards in `guards/answers.py`, `draft.*` events, `outward.draft_ttl`) | (a) | nowhere: an allowed send goes out, an unlisted one is refused before it is written |
| An outward send to other people through an unknown or unlisted tool | (b) a send outside WUWEI's policy | `check_send` refuses it on the floor, naming the line |
| Canary and honeytoken egress, owner disposition markers | (b) records floor | unchanged in `check_send` |
| Learning cards (`outbound learn`, `outbound answer`, `outbound.learn`, `outbound_learn`, `outbound_threads`), the strict y/N leftover | (a) | nowhere; `config set outward.allow ... --add` on its card |
| Register (`graph.py`, `.wuwei/graph.json`, `who`, doctor `register` row, `why` edge lines, `config set` sync) | (a) a second copy of config | nowhere |
| `wuwei reply`, PR reply tiering in `pr_actions.act` | (a) | `pr act --reply` posts through the code-host port (canary and lint) |
| `wuwei lint tone` | (a) a tool seats run on their own prose | nowhere; the CI tone budget (tests/test_tone.py) stays |
| `outward.patterns` internal-state words | (a) applied by audience class, which is gone | nowhere |
| Doctor `outbound classes` and `outbound tiers` rows | (a) | nowhere |

No (b) check is lost.

## Design

### `cli/wuwei/guards/outward.py`

- `check_tier` becomes `check_send(payload)`, and `_check(payload, policy)` keeps its Bash and
  marker branches unchanged. For an MCP tool in a workspace scope:
  1. a native tool, a tool with no scope, or `tool_kind(tool) == 'read'`: `(CLEAN, '')`;
  2. `local(tool, inputs, config)`: `security.outbound(inputs, root)`. When the call is
     owner-only (not a local tool), also append `outward.to_owner` (moved from
     `outward.check_tier`);
  3. `tool in config['outward']['allow']` (exact string): `security.outbound(inputs, root)`;
  4. else: `FINDINGS, NOT_ALLOWED.format(tool=tool)`.
- `local(tool, inputs, config)`: `resolve(tool, config) == {'local'}` or
  `outward.owner_only(inputs, config, kind)`, where `kind` is the resolved channel when there is
  exactly one, else `'other'`. This extends the #727 class; there is no second mechanism.
- `NOT_ALLOWED = ("outward: {tool} may send to other people and is not on outward.allow; the "
  "owner adds it: bin/wuwei config set outward.allow '[\"{tool}\"]' --add (it asks its Owner "
  "step card), then run the call again")`.
- `check_lint` (profile relaxable) runs `outward.check_lint` and `humanize_lint` for allowed and
  owner-only calls. It skips local tools, reads, and refused calls (`check_send` refuses them
  first, and the hook reports the most specific reason).
- `_unmatched`, the `outward.unknown_tool` event and the `drafts.spend` and `drafts.hold`
  branches go. `resolve`, `tool_kind`, `WRITES`, `LEADING`, `READS`, `VOCABULARY`, `OTHER`,
  `LOCAL_SERVERS`, `LOCAL` and `DM_TOOL` stay: they give the lint its channel and the local
  class.
- `GUARDS = [Guard('PreToolUse', None, check_send), Guard('PreToolUse', None, check_lint,
  profile_relaxable=True)]`.
- `guards/__init__.py` `FLOOR`: `outward.check_tier` becomes `outward.check_send`.

### `cli/wuwei/outward.py`

- Keep:
  - `EMOJI`, `PRONOUNS`, `TELLS`, `tells`, `KINDS`, `HUMANIZE`, `humanize_lint` (drop the
    `draft` parameter), `_normalize`, `OWNER_UNSET`, `lint`;
  - `TEXT_FIELDS`, `METADATA_FIELDS`, `BOOL_FIELDS`, `DESTINATIONS` (add `'canvas_id'`),
    `NOT_TEXT`, `_snake`, `_strings`, `_text`;
  - `OWNER`, `SLACK_SHAPE`, `owner_only`, `_owner_ids`, `_external_tracker` (part 20).
- `OWNER` gains `'docs': 'pages'`. `_owner_ids(config, kind)` returns the casefolded Slack ids
  that pass `SLACK_SHAPE`, plus `outbound.owner.pages` for `chat`, `slack` and `docs`; the mail
  address for `mail`. `owner_only` is unchanged otherwise. It needs at least one target, every
  target the owner's, and for mail every address in the text.
- `check_lint(inputs, root, config, channels, *, to_owner=False)`: the `internal_word` branch is
  gone (part 15 took its strict half). The lint channel is the one resolved channel, else
  `'other'`, so an ambiguous channel no longer exits 2.
- `check_call(inputs, root, config, channels, *, port=False)`: `security.outbound`, then
  `check_lint`, then `humanize_lint`, then `profile_result`. No tier, no draft.
- Delete:
  - `REVIEW_REQUEST`, `internal_word`, `PATTERN_FLAGS`, `APPROVAL_REQUIRED`;
  - `_internal`, `_result`, `_pr_context`, `MENTION`, `_keyword_pattern`, `_pattern`, `_topics`;
  - `DEFAULT_TIERS`, `BROAD_ROWS`, `MODE_TIERS`, `KEYS`, `DEFAULT_CLASS`, `UNLEARNED_CLASS`,
    `BLOCKED`, `table`, `reaches_client`, `render`, `blocked`;
  - `_default`, `_person`, `_parties`, `_matches`, `decide`, `channel_ids`, `classify`,
    `check_tier`.

### `cli/wuwei/registry.py` `outward_operation`

- The `drafts.hold` branch goes. A port refusal returns `Result(code, <chat text>, reason)` as
  today.

### Owner config

```toml
[outbound]
# Your own identity per surface; a write whose every destination is yours is local, never an
# outward send: your Slack DM or user id, your mail, your own canvas and page ids.
# owner = {slack = {user = "U123", dm = "D123"}, mail = "you@example.test", code_host = "your-login", pages = ["F123", "<notion page id>"]}
```

`workspace.SCHEMA` `outbound.owner.pages = [(str, None), []]`. `outbound.owner_channel` stays
(the report DM is the owner's own).

### `outward.allow`

`workspace.SCHEMA` `outward.allow = [(str, None), []]`. `load_config` refuses an entry that
does not fullmatch `mcp__[A-Za-z0-9_.-]+__\S+`, as `outward.allow.<n>: not an MCP tool name;
the owner fixes it with bin/wuwei config set outward.allow`. Template:

```toml
[outward]
# Exact MCP tool names that may send to other people. An unlisted write is refused, naming the
# bin/wuwei config set outward.allow '["<tool>"]' --add line, which asks your Owner step card.
allow = []
```

### `commands/config.py`

- `set_value`: the card command includes `--add` when given
  (`shlex.join([..., args.key, args.value, *(['--add'] if add else [])])`), so the card shows
  the exact command the refusal named. Test first.
- `offer`: delete the `graph.sync` block.
- `run` (config check): drop the outbound tier lines, if any are left.

### `init --upgrade` (`commands/init.py`)

- Delete the `graph.annotate`, `graph.build` and `graph.save` block and its `named` and
  `graph_changed` lines.
- Remove every line equal to the old `graph.COMMENT` from config.toml, and print
  `Upgraded config.toml: remove the graph comments`. Copy the comment text as a literal into
  init.py: `graph.py` is deleted.
- `.wuwei/graph.json` goes too. `RETIRED_FILES` only reaches files under `memory/`, behind the
  `inside` guard (`init.py:437-439`), so add one explicit removal next to it: `.wuwei/graph.json`
  when it is a regular file, not a symlink, and inside `destination`. Print
  `Upgraded .wuwei/graph.json: remove (no longer read)` (`Would upgrade` under `--dry-run`), and
  count it in the "No workspace changes needed" test (around 512).
- The `doctor` template row filter (`'graph.json' not in line`) goes.
- The three graph comment lines in `templates/workspace/config.toml` (59, 189, 261) go.

## RETIRED

`workspace.RETIRED` gains:

- outbound: `outbound.tiers`, `outbound.default_tier`, `outbound.learn`, `outbound.people`,
  `outbound.channel_classes`, `outbound.work_channels`, `outbound.external_channels`,
  `outbound.company_domains`, `outbound.sensitive_keywords`, `outbound.sensitive_patterns`,
  `outbound.commitment_patterns`, `outbound.disagreement_patterns`;
- outward: `outward.modes`, `outward.classes`, `outward.draft_ttl`, `outward.patterns`.

`outbound.code_host_orgs` stays (Assumption 7).

## Files to delete (8, plus 5 test files)

- `cli/wuwei/drafts.py`, `cli/wuwei/commands/drafts.py`, `cli/wuwei/commands/outbound.py`,
  `cli/wuwei/graph.py`, `cli/wuwei/commands/who.py`, `cli/wuwei/commands/reply.py`,
  `cli/wuwei/commands/lint.py` (its measure helpers move into `tests/test_tone.py` first);
- `templates/workspace/graph.json`;
- `tests/test_drafts.py`, `tests/test_outbound.py`, `tests/test_outbound_learn.py`,
  `tests/test_graph.py`, `tests/test_who.py`. Move the helpers other files import first:
  `test_drafts.held` (used by `test_owner_edits.py`, whose draft cases go anyway),
  `test_graph.CONFIG` (used by `test_workspace.py:1568`, whose register cases go), and
  `test_decision.py:347`'s import of `RECORD` from `wuwei.commands.outbound` (inline the
  record text).

`specs/095-outbound-tiers/` and `specs/011-outward-lint/` are history: they stay, and the
template stops linking them. Command registration needs no edit: `__main__.py` discovers
`commands/*.py`.

`obligations.reply` and `_thread_reply` stay: `pr act --reply` posts through them, and the
`reply_acks` ledger they write is read by `obligations._replies`. Only the `wuwei reply` command
goes.

## Files to edit, code (about 25)

- `guards/outward.py`, `guards/__init__.py` (`FLOOR`), `outward.py`, `registry.py`: Design.
- `guards/answers.py`: delete `DRAFT_ID`, `_pending_drafts`, `_draft_answer` and the `Draft`
  header branch of `record_gate`. The Owner step and D-n branches stay (part 18).
- `workspace.py`: the SCHEMA `outbound` and `outward` keys above, `AUDIENCES`, `TOPICS`, the
  `outbound.tiers` validation (around 747-755), `RETIRED`, `outward.allow` validation, and
  `outbound.owner.pages`.
- `pr_actions.py` `act` (around 421-493): after the scope branch, a reply posts through
  `obligations.reply(...)`. The port lints it, and a lint refusal prints the reason and returns
  1. The `classify`, `blocked`, draft-reply and `humanize_lint(draft=True)` branches go. The
  ACTIONS route name `'outbound_tier_then_reply'` (95) becomes `'reply'`
  (`tests/test_pr_ownership.py:72-73` pins it).
- `guards/protect_state.py`: drop `'graph.json'` from the protected names (72) and the
  `bin/wuwei who` hint (115-117).
- `status.py` (34-37, 102-104, 138): the `draft.*` attention rows and their clearing go.
- `commands/shepherd.py:11` and `commands/docs.py:12`: help text drops "outbound tiers" and
  "draft".
- `tracker.py`: `pending` (75-80) and the `queued` lookup (185-187) go; `check` returns the
  card text only for a missing ticket; `_held` goes with its callers (a held ticket no longer
  exists).
- `plan.py` (428-440): the `drafts.approve` branch goes; `tracker.create` sends.
- `docs.py`: the pending docs draft line (264-269), the `outward: draft` outcome (189-190) and
  the `earlier` draft scan (338-339) go.
- `metrics.py` `collect` (739-750): read the stored `drafts` rows of past days directly
  (`(data or {}).get('drafts', {})`, rows that are dicts with the fields used), so the 5.6 voice
  metric stays computable for old days. Drop the `drafts` import. No new rows are written.
- `commands/why.py`: `_draft`, `edges` and the draft lookup (240-265) go; the rule and fix lines
  stay.
- `commands/doctor.py`: `_outbound` (382-400), `_register` (403-420), the `graph.json` filter
  (288), and the draft half of `_unrecorded` (691-700) go.
- `commands/config.py`: Design.
- `commands/init.py`: Design.
- `commands/event.py`: the `draft.*`, `outbound.*`, `decision.routed` and `reply:` producer rows
  go. An old event stays readable.
- `commands/next.py`: any `drafts` row or THEN text (the builder greps `drafts`).
- `signal.py`: drop `draft.*`, `outbound.*`, `reply:` and `pr.reply.drafted` from `SILENT`.
- `state.py` `STATE_PRODUCERS` (it is the generic-write allowlist that
  `tests/test_state_allowlist.py` pins): delete `drafts`, `outbound_learn`, `outbound_threads`
  and `pr_reply_drafts`; `reply_acks` now names `wuwei pr act`; `tickets` drops
  `wuwei drafts approve`. `decision_outcomes` and `decision_routes` stay, because
  `decision.answered`, `metrics` and `telemetry` read them for past days (telemetry untouched);
  their producer text becomes `none since #838; read for past days`. An old `state.json` that
  holds a deleted key still reads: nothing validates the keys on read.
- `decision.py`: delete `route_owner` (its only caller was `outbound learn`); the docstring
  drops the learning cards. `widget` and `gate` (plan, close, shepherd), `naming`, `answered`,
  `today_path` and the MCP card functions stay; `owner_confirm`'s y/N path stays only for the
  MCP cards until part 18.
- `shepherd.py`: drop any `drafts` or `classify` use (`ping_gate` stays: `pr ping` uses it).
- `tests/test_reasons.py`: delete the LEFT rows `('drafts.py', 'host terminal', 16)` and
  `('commands/drafts.py', 'from the owner host terminal', 16)`.

## Files to edit, governance and docs

- `charters/_common-authoring.md:32`: drop the `bin/wuwei lint tone <path>` sentence (the five
  rules stay).
- `charters/_common.md:23`: a held ticket no longer exists. Replace "When it is held, the reason
  names the rule and the planner's card" with "When it is refused, note the reason in your
  report and go on".
- `charters/shepherd.md:12`: "do not record a draft as sent" becomes "a refused post remains
  owed".
- `charters/_common-authoring.md:11`: "Route a technical claim, disagreement, scope statement or
  sensitive audience through the configured owner and channel policy" and "A draft is not a sent
  message" become "A send through a tool not on `outward.allow` is refused; it names the line the
  owner adds. A refused post is not a sent message."
- `commands/next.py` and `commands/config.py`: the part 15 texts that say "held sends" say
  "unlisted outward sends".
- Run `bin/wuwei agents build` to rebuild `agents/*.md`; never edit `agents/` by hand.
- `skills/wuwei-plan/SKILL.md:16` and `skills/wuwei-report/SKILL.md:16`: drop
  `wuwei drafts show <id> --widget` from the widget examples, and add one sentence: "An outward
  refusal names `wuwei config set outward.allow ... --add`; run it, it asks its card".
- `templates/workspace/config.toml` `[outward]` (162-188) and `[outbound]` (190-229): the
  `allow` key and the owner line with `pages`. Delete the tier, class, draft, learn and register
  comments and keys, and keep `max_length`, the humanize keys, `tool_patterns`, `servers` (now
  only the `local` alias and the lint channel), `owner`, `owner_channel` and `code_host_orgs`.
- `docs/specs/2026-09-24-wuwei-design.md`:
  - 4.1 row "chat, tracker or docs adapter call" becomes "an MCP tool not on `outward.allow` that
    is not local";
  - 4.3 drops the audience text;
  - 4.9 becomes "Outward sends (owner, 2026-10-11, #838)": the allowlist, the owner's surfaces
    table, the port duties; the tier text is retired with a dated line;
  - 9.2 row "Outward send": "an MCP send to other people only through a tool on `outward.allow`;
    the owner's own surfaces are local";
  - 5.8 (706-709): drop "The learning cards of `outbound learn` and"; 5.11 and 5.12: tracker
    and docs writes through the port send after the lint (no draft);
  - 5.13 keeps its `draft.*` event vocabulary (stored weeks; telemetry untouched); section 15
    is retired history and stays.
- docs pages (the acceptance names docs; `tests/test_docs.py` pins the command table, every
  template key and every config section):
  - `docs/site/configuration.md`: 15 (sections table), 38 (`tracker.auto`), 73 and 161 (links
    into the people section), 256 (`docs.auto`), 303-334 (keep `banned_characters`,
    `max_length`, `humanize*`, `tool_patterns`, `servers`; add `outward.allow`; delete the
    rest), 336-356 (the people section becomes "Your own surfaces": `outbound.owner` and
    `pages`);
  - `docs/site/reference.md`: 23 (drafts), 33 (lint), 40 (outbound), 47 (reply), 55
    (shepherd tiers), 64 (who), 110-128 ("Outward draft queue"), 386-394 (`why` draft), 411-412,
    and the duplicated `mcp` and `decide` rows the lead noted (leave one copy);
  - `docs/site/concepts.md`: 186, 188-191 ("Drafts and cards" becomes "Cards"), 192-209
    ("Outbound tiers" becomes "Outward sends": the allowlist and the surfaces table), 232, 248;
  - `docs/site/daily.md`: 271-275, 298-299; `docs/site/security.md`: 59, 61, 70, 74;
  - `README.md`: 37 (the register line goes), 110 (the anchor becomes `concepts.md#cards`).
  The builder greps `drafts`, `tiers`, `outbound learn`, `outbound tier`, `wuwei who`,
  `wuwei reply`, `graph.json`, `register` and `lint tone` under `docs/site`, `README.md`,
  `charters`, `skills` and `templates`, and leaves none.

## Files to edit, tests

Line numbers are at 703b40de; part 15 already rewrote the posture writers.

- `tests/test_outward.py` (126 tests). The `configured` fixture (14-31) drops `default_tier` and
  `work_channels`.
  - Keep: the lint, tells and humanize cases (`lint_table`, `configured_lint`,
    `missing_owner_fails_closed`, `channel_limits_cannot_be_bypassed`, `owner_handles`,
    `unicode_identity_obfuscation`, `character_default_corrections`, `ports_require_workspace`,
    `channel_id_limit`, `emoji_presentation_selector`,
    `owner_addressed_lint_skips_third_person_rules_only`, `tells_*`, `humanize_lint_*`,
    `hook_lint_humanizes_mcp_writes`, `no_config_set_in_reasons`,
    `text_fields_keep_known_checks`, `every_free_text_adapter_write_goes_through_the_port`);
    `name_words`, `vocabulary`, `resolve_opaque`, `alias_resolves_and_reads_still_pass`,
    `recorded_opaque_tools`; and the `local_*` cases (2171-2207) except
    `local_shapes_are_exact`.
  - Rewrite onto `check_send`: `standard_profile`, `port_boundary`, `check_call_send_humanizes`,
    `owner_facing_templates_are_plain` (drop `commands/outbound.py` from its list),
    `rule_defaults_and_configured_tool_patterns`, `docs_tool_patterns`,
    `to_owner_event_and_lint`, `guard_to_owner_*`, `connector_writes_through_the_guard`,
    `textless_write`, `tool_input_not_an_object`, `terminal_hook_judges_the_command`,
    `owner_only`, `owner_only_ignores_non_dm_shapes`,
    `guard_owner_mail_with_outside_cc_is_not_owner_only`.
  - Delete: every tier, umbrella, class, topic, thread, draft, learn, unknown-tool, internal-word
    and `why` draft case. That is the inventory's delete list: `send_or_draft` through
    `keyword_pattern_matches_the_per_word_search`, including `internal_word`,
    `internal_state_*`, `unmatched_*`, `recorded_server_tools`, `tier_*`, `thread_*`,
    `owner_config` (rewritten as a `pages` case).
  - Add: US1 (refused unlisted with enforce true and false, allowed exact, exact match only,
    unknown name refused, canary on an allowed tool) and US2 (one case per surface row, mixed
    destinations, no destination, `owner` unset).
- Canary floor through the send check (rewrite, never delete): `tests/test_canary.py` (207, 226,
  237, 269, 388, 558), `tests/test_stop.py` (34, 494, 499), `tests/test_profiles.py` (27-29,
  157-180, 283-290), `tests/test_guard_mutation.py:28` (the `check_tier` row becomes
  `check_send`).
- Port policy: `tests/test_reference_adapters.py` (98-134, 315-334) and
  `tests/test_tracker_adapters.py` (71-76) keep monkeypatching `outward.check_call` (the name
  stays) and drop the tier keys from their configs. `tests/fakes/tracker.py` keeps the
  decorator.
- `tests/test_hooks.py`: delete `test_only_a_held_call_imports_the_draft_queue` (1517-1528); the
  outward refusal through the hook; the `guards.MODULES` pin.
- `tests/test_enforce.py` (from part 15): the floor key is `outward.check_send`.
- `tests/test_invariants.py`: `CARD` (14) drops `drafts show`; `CALLED` (22-24) drops the
  `drafts.py` and `outward.check_tier` rows and names `check_send`.
- `tests/test_answers.py`: delete `pending_draft`, `draft_question` and the two Draft cases
  (58-91); keep the D-n case.
- `tests/test_owner_edits.py`: delete `asked_draft` and the two draft cases (90-128); keep the
  goals cases.
- `tests/test_why.py`: delete `HOLD`, `held` and the four draft cases (338-383); edit 446.
- `tests/test_pr_actions.py`: delete the six tier and draft reply cases (204-284); edit 10,
  82-90 and 507-515 (`action == 'reply'`, no `drafts.read`); add `pr act --reply` posts through
  `obligations.reply` after the lint. `tests/test_pr_ownership.py:72-73`: the route name.
- `tests/test_obligations.py`: delete only the cases that run the `wuwei reply` command
  (`reply_command` helper 250 and its users); keep the `obligations.reply` and ledger cases;
  drop the `'reply'` param of `test_me_override_is_not_accepted`.
- `tests/test_shepherd.py`: delete `test_review_request_outbound_tier_uses_fresh_gate` (749);
  keep the thread reply cases that call `obligations.reply` (the function stays); edit the
  config at 32-33.
- `tests/test_headless_shepherd.py` (198-259): no `outward: draft` reason.
- `tests/test_signal_status.py`: edit 320-376 (no draft, outbound or reply kinds); delete
  `test_draft_events_use_decisions_lane` (465); keep `test_outward_to_owner_is_silent_and_reserved`
  (`outward.to_owner` is still written).
- `tests/test_state_allowlist.py` (38, 45-46, 53, 122-124, 204-207) and `tests/test_state.py`
  (783-786): the `STATE_PRODUCERS` changes.
- `tests/test_quiet_sweeps.py:121-132`, `tests/test_records_after_dryrun4.py:178-181`,
  `tests/test_watch.py:574-582`: delete the draft cases.
  `tests/test_operator_records.py:43-44`: drop the two draft events.
- `tests/test_protect_state.py`: delete `test_register_is_cli_owned` (951-960); 1032 names
  another command.
- `tests/test_docs_system.py`: delete `drafts_of`, `test_docs_page_queues_a_draft` and
  `test_close_names_a_pending_draft`; strip the `drafts_of(day) == []` asserts.
- `tests/test_tracker.py`: delete the six held and draft cases (76, 168, 186, 196, 205, 412);
  edit 142-163 and 312-319 (the ticket is created).
- `tests/test_plan.py` (696-739), `tests/test_intraday_intake.py` (299-374, 437): no pending
  draft; the ticket is created at approve and at `plan add`.
- `tests/test_doctor.py`: delete `test_outbound_tier_rows`, `test_register_row` and
  `test_template_row_leaves_the_register_to_its_row`; edit `test_answered_cards_row` (559-593),
  `test_workspace_rows_healthy` (301) and `ws` (97-98).
- `tests/test_config_writer.py`: delete the two register cases (247-270); move the other cases
  onto surviving keys (104-215).
- `tests/test_config_set.py`: move onto surviving keys (115-315); add: the card command shows
  `--add`.
- `tests/test_config_transition.py`: rewrite `test_config_check_reports_two_tables` (117-135);
  add the RETIRED removal, the `graph.json` removal and the comment removal.
- `tests/test_workspace.py`: delete the register cases (1566-1630); edit 207-215, 1466,
  1480-1492; add `outward.allow` validation and `outbound.owner.pages`.
- `tests/test_decision.py`: inline `RECORD` (345-359); delete `route_owner` cases if any.
- `tests/test_metrics.py` (245-274): the voice and tells metrics read the stored rows.
- `tests/test_next.py:663-685`: the report DM stays (`owner_channel`).
- `tests/test_dispatch.py:1604`: the `code_host_orgs` line stays (Assumption 7).
- `tests/test_path_day.py` (161-168) and `tests/test_e2e_day.py`: no draft step.
- `tests/test_tone.py`: inline `AVERAGE`, `LONGEST`, `line`, `measure` and `sentences` from
  `commands/lint.py`; delete the `main(['lint', 'tone', ...])` cases (104-131); keep the budget
  cases.
- `tests/test_charters.py:119`: drop the `bin/wuwei lint tone <path>` phrase; the five-rule check
  stays.
- `tests/test_reasons.py`: the two LEFT rows.
- `tests/test_telemetry.py`, `tests/test_memory.py`, `tests/test_build.py`,
  `tests/test_close_parked.py`: unchanged unless they seed `drafts` or `outbound_learn`; run
  them.

## Risks

- An MCP tool with an unknown name is now refused until the owner adds it (Assumption 3). The
  refusal names the exact line and the card, so it takes one turn. Tools the planner uses that
  are neither local nor reads (for example session helpers) need one card each.
- Port writes (duties) lose the tier gate. They keep the canary floor and the lint, and their
  destinations come from owner config. A seat reaches a port only through a WUWEI command.
- `outbound.owner.pages` is new; until the owner sets it, canvas and page writes need
  `outward.allow`.
- State keys from old days stay in their files. The `STATE_PRODUCERS` check above decides how
  they read.
- The inventory of tests to delete is large; the builder greps each removed symbol after the
  deletion (`grep -rn "drafts\|classify\|outbound learn\|graph\.\|who\b\|lint tone" cli tests`).

## Handoff

- Part 18 deletes the rest of `decision.py` (the MCP cards) and its LEFT rows.
- Part 20 decides `outbound.code_host_orgs` and `_external_tracker` with the tracker.
- Part 24 rewrites the docs site; this part leaves no tier, draft, learning card, graph, `who` or
  `reply` text there.
