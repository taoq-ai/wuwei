# Tasks: outward control is one owner-configured tier table

Test first: run each test task, see it fail for the stated reason, then do the implementation
task that follows it. Run tests with `python -m pytest -q <file>` from the repository root
using the interpreter the pipeline names. Signatures, texts and line numbers are in plan.md;
reason and output texts in `contracts/outbound-tiers.md`. Fixtures: `configured`, `payload()`,
`opaque()`, `write_config()`, `set_posture()`, `with_owner()` (`tests/test_outward.py`), the
#492 learn fixtures (`tests/test_outbound_learn.py`). Neutral ids only (`C1`, `C2`, `C3`,
`C5`, `D01`, `U01`, `U07`, `U09`, `dev@example.test`, server
`00000000-0000-4000-8000-000000000001`); no absolute local path, no em-dash and no emoji in any
file.

## Phase 1: config (FR-002, FR-005, FR-015)

- [X] T001 In `tests/test_outward.py`, add failing `test_tier_config`: a workspace with
  `[outbound] tiers = [{ person = "U07", tier = "send" }]`, `[outbound.channel_classes] C4 =
  "public"`, `"slack:U07" = { email = "dev@example.test", class = "team" }` and
  `[outward.classes] "<uuid>" = "company"` loads with those values; an empty workspace loads
  `tiers == []`, `channel_classes == {}`, `classes == {}`. Fails today: unknown key.
- [X] T002 In `tests/test_outward.py`, add failing `test_tier_row_validation` (US2 5): a row
  `{ persn = "U07", tier = "send" }` raises `ConfigError` naming `outbound.tiers.0.persn` under
  `guarded` (not only `strict`); `{ tool = "(", tier = "ask" }` raises naming
  `outbound.tiers.0.tool`; `{ tier = "maybe" }`, `{ audience = "boss", tier = "ask" }` and a
  row without `tier` raise. Fails today: unknown key `tiers`.
- [X] T003 In `cli/wuwei/workspace.py`, add `AUDIENCES`, `TOPICS`, the schema keys and the
  `load_config` row checks (plan section 1); `CONFIG_CACHE_VERSION = 9`.
- [X] T004 [P] In `tests/test_profiles.py`, add a failing assert that `outbound.tiers` and
  `outbound.channel_classes` are in `profiles.PRIVATE`. Then add them in
  `cli/wuwei/profiles.py`.

## Phase 2: the table and the parties (FR-001, FR-003, FR-004, FR-006, FR-007, FR-008)

- [X] T005 In `tests/test_outward.py`, add failing `test_tier_table`: `outward.table(config)`
  on the empty fixture returns the ten default rows of the contract tagged `default`; with
  `outward.modes = {"<uuid>" = "refuse"}` and one owner row, rule 1 is `{'tool':
  'mcp__<escaped uuid>__.*', 'tier': 'block'}` with source `owner` and note ` (outward.modes)`,
  rule 2 the owner row, rule 3 the owner default; `outward.render` gives `{ person = "U07",
  tier = "send" }`. Fails today: no attribute `table`.
- [X] T006 In `cli/wuwei/outward.py`, add `DEFAULT_TIERS`, `MODE_TIERS`, `KEYS`, `table`,
  `render`; turn `_flagged` into `_topics` (plan sections 2).
- [X] T007 In `tests/test_outward.py`, add failing `test_tiers_acceptance` (US1 1-3, issue
  acceptance 1) through `guards.outward.check_tier` with `opaque('slack_send_message')` and
  `[outward.servers] "<uuid>" = "slack"`, `external_channels = ["C2"]`, `with_owner`:
  `I will ship it tomorrow` to `C2` returns `(1, <block reason of the contract>)` and adds no
  `drafts` row; to `C1` returns a #493 held reason whose rule is `ask by rule 7
  (topic=commitment) for C1: C1 in outbound.work_channels as team,
  outbound.commitment_patterns`; `Your build is green` to `D01` returns `(0, '')`. Fails today:
  the client send is a draft.
- [X] T008 In `tests/test_outward.py`, add failing `test_tiers_defaults` (US1 4-6) on
  `outward.classify(..., why=why)`: a `channel_classes` `public` channel is `(1, 'block')` by
  rule 2; `I disagree with the proposal.` to `C2` is block by rule 4; `Your salary review is
  in` to `C2` is a draft by rule 5; `tests passed` to `C1` is `(0, 'send')` with `why == []`;
  `thanks <@U09>` to `C1` is a draft by rule 9 whose evidence starts `unknown mention @u09`;
  a textless `other` write is `(0, 'send')` by rule 10 and `I disagree` through `other` is a
  draft by rule 8. Each fragment has no `; `. Fails today: no block, old texts.
- [X] T009 In `tests/test_outward.py`, add failing `test_tier_classes`: `is_shared` on a
  `work_channels` destination makes it client (block on a commitment); `people.class =
  "client"` on `slack:U07` makes `<@U07>` in `C1` a client party; `recipient_org = "other-org"`
  is a client party; a GitHub `tracker.project` outside `code_host_orgs` is a client `board`
  party (draft by rule 5); `outward.classes "<uuid>" = "team"` makes an unknown Slack
  destination team, so `thanks` to `C9` through that connector is sent by the kind rules.
  Fails today: unknown keys, old texts.
- [X] T010 In `tests/test_outward.py`, add failing `test_tiers_mixed_parties`: a payload with
  `channel = "C1"` and `channel_id = "C2"` and a commitment is block by rule 3;
  an owner DM `D01` plus `recipients = ["U09"]` asks by rule 9; `{ person = "U07", tier = "send"
  }` with a DM to `U07` sends while `<@U07>` in `C1` with prose that is not a routine reply
  drafts by `approval tier unclassified` (kind rules). Fails today: no rows.
- [X] T010a In `tests/test_outward.py`, add failing `test_owner_row_person` (US2 1-3, issue
  acceptance 2) on `outward.check_tier`: `tests passed <@U07>` to `C1` is held by rule 9;
  after `write_config` of `[outbound] tiers = [{ person = "U07", tier = "send" }]` it returns
  `(0, '')`, and a DM to `U07` returns `(0, '')`. Fails today: unknown key `tiers`.
- [X] T010b In `tests/test_outward.py`, add failing `test_tier_floor_strict` (US3 1-3, issue
  acceptance 3): strict and `{ audience = "client", tier = "send" }`: `thanks` to `C2` is held
  by rule 6 and the `trace` list from `classify(..., trace=trace)` holds `rule 1 owner {
  audience = "client", tier = "send" }: ignored under strict`; under guarded the same send is
  `(0, 'send')`; with `WUWEI_SEAT_ROLE=shepherd` an owner DM and a `send` row still draft.
  Fails today: no `trace` keyword.
- [X] T011 In `cli/wuwei/outward.py`, add `_owner_ids` (and use it in `owner_only`),
  `DEFAULT_CLASS`, `_default`, `_person`, `_parties`, `_matches`, `decide`, `blocked`, and
  rewrite `classify` and `check_tier` (plan sections 3 to 6). Delete `check_send`. T007 to
  T010b pass, except the guard paths that need T015.
- [X] T012 In `tests/test_outward.py`, update the existing reason tests to the contract texts:
  `RULES` (rows 1, 2, 3 and 6), `test_check_tier_appends_the_rule`,
  `test_hook_refusal_names_draft_and_why_reads_it`, `test_draft_names_unknown_audience`,
  `test_dm_recipient_rule`, `test_tracker_github_outside_code_host_orgs_drafts`; run the file
  and fix only texts, never outcomes, except the three SC-002 changes.

## Phase 3: connector modes in the guard and seat limits (US2; FR-010)

- [X] T014 In `tests/test_outward.py`, add failing `test_mode_rows` (US2 4): with
  `outward.modes "<uuid>" = "refuse"` a write through the connector returns exit 1 with a block
  reason naming `rule 1 (tool=mcp__...__.*)` and `outward.modes`, no draft row and no
  `wuwei.drafts` import; `draft` gives a held reason with `ask by rule 1`; `send` gives `(0,
  '')` for a commitment text. Update `test_class_modes` and `test_guard_to_owner_floor` to
  these outcomes (refuse exit 1, block words). Fails today: refuse is exit 2 with the old text.
- [X] T015 In `cli/wuwei/guards/outward.py`, add `DM_TOOL` and replace the mode branches
  (plan section 6). T014 passes.
- [X] T018 [P] In `tests/test_protect_state.py`, add a test that an agent Bash call
  `bin/wuwei config set outbound.tiers '[{ person = "U07", tier = "send" }]'` is refused with
  `GUARD_CONFIG` (US2 6). Expected to pass without code changes; if it fails, fix the key
  split in `cli/wuwei/guards/protect_state.py`.
- [X] T019 [P] In `tests/test_hooks.py`, add a row to the held-call import test: a blocked
  call does not import `wuwei.drafts`. Expected to pass after T011 and T015.

## Phase 4: callers and the card (FR-013, FR-014)

- [X] T020 [P] In `tests/test_drafts.py`, add failing tests: a draft whose rule is an `ask by
  rule 9 ... unknown destination C9 ...` fragment gets the `outbound learn` hint on Send now;
  `unknown DM recipient` in the rule gets the #495 hint while the identity is missing; under
  strict an `ask by rule` draft puts Keep as draft first. Then edit `cli/wuwei/drafts.py`
  `widget` (plan section 7).
- [X] T021 [P] In `tests/test_pr_actions.py`, add a failing test: `pr act --reply` with a
  reply the table blocks (a `client`-classed PR party via `outward.classes`, or a monkeypatched
  `classify` returning `(1, 'block')` with a fragment in `why`) prints the blocked reason, exits
  1 and creates no draft. Then edit `cli/wuwei/pr_actions.py:422-424`.
- [X] T022 In `tests/test_outbound_learn.py`, add failing tests (US4): a listing with a shared
  channel `C5` proposes it with class client and the card line `channel #<name> (C5, <n>
  members): client, shared with an external org`; `Approve` writes `C5` to
  `external_channels`, the team channel to `work_channels` and `class = "team"` on each person;
  then a commitment to `C5` through the guard is block by rule 3 (issue acceptance 4);
  `Approve channels only` writes both lists and no people. Update the existing card text
  asserts. Fails today: shared channels are not proposed.
- [X] T023 In `cli/wuwei/commands/outbound.py`, edit `propose`, `record`, `apply` and
  `MODE_TEXT` (plan section 8).

## Phase 5: visibility (FR-011, FR-012)

- [X] T024 In `tests/test_outbound.py`, add failing `test_outbound_tiers_prints_table`
  (US5 1): `main(['outbound', 'tiers'])` exits 0 and prints the header, rows `1` to `10`
  tagged `default` and the kind rules line; with one owner row it is rule 1 tagged `owner`
  (issue acceptance 2); under strict an owner client `send` row ends `(ignored under
  strict)`. Fails today: invalid choice `tiers`.
- [X] T025 In `tests/test_outbound.py`, add failing `test_outbound_explain` (US5 2, issue
  acceptance 5): after a held commitment to `C1` through the guard, `main(['outbound',
  'explain', <id>])` exits 0 and prints the stored rule, `party C1: team, ...`, each rule
  line with `passed` up to `rule 7 default { topic = "commitment", tier = "ask" }: matched`, and
  the `now:` line; an unknown id exits 1. Fails today: invalid choice `explain`.
- [X] T026 In `tests/test_outbound.py`, add failing `test_outbound_tier_block`: `outbound tier`
  with a commitment to `C2` on stdin prints `{"tier": "block", "exit": 1}` and the blocked
  reason on stderr, exit 1.
- [X] T027 In `cli/wuwei/commands/outbound.py`, add `tiers`, `explain` and the `run` block
  branch; in `cli/wuwei/commands/__init__.py`, add both paths to `READ_ONLY`. Run
  `tests/test_cli_known_command.py` and add the paths where its tables list them.
- [X] T028 In `tests/test_doctor.py`, add failing tests (US5 3, US3 1-2, issue acceptance 3):
  a person without `class` gives a `warn` row `outbound classes` with one detail line; an owner
  `{ audience = "client", tier = "send" }` row gives a `warn` row `outbound tiers` saying `rule
  1 is ignored under strict` under strict and `rule 1 sends to a client audience` under
  guarded; neither row with no people and no such row (`ok`).
- [X] T029 In `cli/wuwei/commands/doctor.py`, add `_outbound(config)` and call it from
  `_workspace` (plan section 9).

## Phase 6: docs (FR-016)

- [X] T030 In `tests/test_docs.py`, add a failing `test_outbound_tiers_docs`: concepts.md has
  an `## Outbound tiers` section naming `send`, `ask`, `block` and the five classes and the
  client example; configuration.md names `outbound.tiers`, `outbound.channel_classes`,
  `outward.classes` and the people `class`; security.md names the strict floor and that a seat
  never writes the table; reference.md names `outbound tiers` and `outbound explain`; the
  template mentions `tiers` and `channel_classes`.
- [X] T031 Edit `docs/site/concepts.md`, `docs/site/configuration.md`,
  `docs/site/security.md`, `docs/site/reference.md` and `templates/workspace/config.toml`
  (plan section 11). Update any existing doc test that pins the old mode or draft texts.

## Phase 7: finish

- [X] T032 Run `python -m pytest -q`; everything passes. Grep the changed files for
  em-dashes, emojis and absolute local paths and remove any.

## Phase 8: review fixes

- [X] T033 (F1) Rebase the work onto main 42deb75 (#505, #506): keep #505's `_text`, its
  nonempty-text check ahead of `classify` and its channel-only `destinations`; drop the
  guard's mode `refuse`, `draft` and `send` branches, `check_send`, `mode` and `CLASS_MODES`
  (the mode row replaces them); an empty text classifies as #505 does. Port
  `test_text_fields_corpus`, `test_connector_writes_through_the_guard` and
  `test_guard_owner_mail_with_outside_cc_is_not_owner_only` to `check_tier` (refuse is block,
  exit 1). Set `CONFIG_CACHE_VERSION = 11`.
- [X] T034 (F2) In `tests/test_drafts.py`, add failing `test_card_adds_a_tier_row`; in
  `cli/wuwei/drafts.py`, add `always_row` and the Always option on the card, and
  `drafts approve --always`, which appends the row to `outbound.tiers` before the claim.
- [X] T035 (F2) In `tests/test_outbound_learn.py`, add failing `test_learn_card_sets_a_class`;
  in `cli/wuwei/commands/outbound.py`, add one `<id>-<class>` option per learn entry and apply it.
  Point the doctor `outbound classes` fix at the learn card.
- [X] T036 (F3) In `tests/test_doctor.py` and `tests/test_outbound.py`, extend the tier row
  tests; add `outward.reaches_client` and use it in doctor and the `outbound tiers` tag.
