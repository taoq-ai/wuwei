# Feature Specification: outward control is one owner-configured tier table (send, ask, block)

**Feature Branch**: `496-outward-tiers`

**Created**: 2026-10-04

**Status**: Draft

**Input**: GitHub issue #496, "feat(outward): outward control is one owner-configured tier table
(send, ask, block) matched by tool, person, channel, audience class and topic, with audience
classes on people and channels learned on the card and client-facing defaults". Owner,
2026-10-04: "This should be configurable and decided by the owner. Block is just a tier; the
others would be ask first (confirm the draft) or always send, and each should be configurable
by tool and/or by person, to allow different levels of control. If a tool or a person is
client-facing, or the client itself, the control required is different."

## Current behaviour (read and reproduced on main, e6c65d6, read-only)

Reproduction: the notes name no dry-run workspace, so a scratch workspace in a temp directory
(`work_channels = ["C1"]`, `external_channels = ["C2"]`, `outbound.owner.slack = {user = "U01",
dm = "D01"}`, `outward.modes = {srv = "refuse"}`) ran `wuwei.outward.classify` in process for
Slack sends:

| Text | Destination | Result | Rule |
| --- | --- | --- | --- |
| `I will ship it tomorrow` | `C2` (client) | `(1, 'draft')` | `approval tier commitment for C2: outbound.commitment_patterns` |
| `I will ship it tomorrow` | `C1` (team) | `(1, 'draft')` | `approval tier commitment for C1: outbound.commitment_patterns` |
| `Your build is green` | `D01` (owner) | `(0, 'send')` | none |
| `tests passed @rev` | `C1` | `(1, 'draft')` | `unknown mention @rev: not an internal person in outbound.people` |

`workspace.SCHEMA['outbound']` has no `tiers` key and `outward.check_tier` takes no tool.

1. **Every hit means draft, whoever reads it.** `cli/wuwei/outward.py:386-387` (`classify`)
   checks the sensitive, commitment and disagreement patterns (`_flagged`, `:317-328`) before
   any audience rule, so a commitment to a client channel and to a team channel give the same
   draft. There is no `block` outcome: `classify` returns only `send` or `draft` (`:353-354`).
2. **Audience rules are hard-coded.** The DM, external (`is_*` flags,
   `outbound.external_channels`), unknown mention, `recipient_org`, external tracker board and
   unknown destination rules (`:388-418`, `:439-445`, `_external_tracker` at `:303-311`) are
   fixed branches. People and channels carry no class; `outbound.people` entries have only
   `email` and `org` (`cli/wuwei/workspace.py:157`).
3. **The connector mode is a second decision path.** `cli/wuwei/guards/outward.py:181-194`
   decides `outward.modes` (`refuse` as exit 2, `draft`, `send` through `outward.check_send` at
   `cli/wuwei/outward.py:331-350`) before and beside `check_tier`, with its own owner override
   (`:182-183`).
4. **Nothing shows or explains the policy.** `bin/wuwei outbound` has `tier` and `learn` only
   (`cli/wuwei/commands/outbound.py:13-27`); a draft's reason names a rule but not its place in
   any table, and nothing prints the rules a message passed.

## User Scenarios and Testing

### User Story 1 - The audience decides the tier (Priority: P1)

A seat sends through a connector or a port. WUWEI finds who reads it (each destination and
each addressed person, with an audience class) and the topics of the text, walks one ordered
table, and the first matching row gives `send`, `ask` or `block` for that party. The strictest
party decides the call. `ask` is a #493 draft and card; `block` is refused with the row named
and no card; `send` goes out after the lint.

**Why this priority**: the owner's request; a commitment to a client must not wait on a card
the owner might approve by habit.

**Independent Test**: `python -m pytest -q tests/test_outward.py -k tiers`.

**Acceptance Scenarios**:

1. **Given** `external_channels = ["C2"]` and a Slack send of `I will ship it tomorrow` to
   `C2`, **Then** exit 1, no draft row, and the reason is `outward: block by rule 3
   (audience=client topic=commitment) for C2: C2 in outbound.external_channels as client,
   outbound.commitment_patterns; the owner decides: bin/wuwei outbound tiers`.
2. **Given** the same text to `C1` in `work_channels`, **Then** a draft whose rule is `ask by
   rule 7 (topic=commitment) for C1: C1 in outbound.work_channels as team,
   outbound.commitment_patterns`, and its card is the #493 card.
3. **Given** `outbound.owner.slack.dm = "D01"` and `Your build is green` to `D01`, **Then** it
   is sent with the `outward.to_owner` event (#495, unchanged).
4. **Given** a channel in `outbound.channel_classes` as `public`, **Then** any send to it is
   `block` by rule 2.
5. **Given** `I disagree with the proposal.` to a client channel, **Then** `block` by rule 4;
   `Your salary review is in` to a client channel, **Then** `ask` by rule 5.
6. **Given** a team channel and a routine reply (`tests passed`) with no topic and no unknown
   person, **Then** no row matches and today's kind rules decide (sent).

### User Story 2 - The owner adds a row (Priority: P1)

The owner writes rows in `[outbound] tiers` with any subset of `tool`, `person`, `channel`,
`audience`, `topic` and the `tier`. Owner rows come before the defaults; the connector modes of
`outward.modes` are the first rows.

**Independent Test**: `python -m pytest -q tests/test_outward.py -k owner_row`.

**Acceptance Scenarios**:

1. **Given** `tests passed <@U07>` to `C1` and `U07` not in `outbound.people`, **Then** a draft
   by rule 9 (`audience=company`, `unknown mention @u07`).
2. **Given** the owner adds `{ person = "U07", tier = "send" }`, **Then** the same send goes
   out, and `bin/wuwei outbound tiers` prints that row as rule 1 tagged `owner`.
3. **Given** `{ person = "U07", tier = "send" }` and a DM to `U07`, **Then** it goes out (every
   party matched a `send` row; the DM kind rule does not run).
4. **Given** `outward.modes = {"<uuid>" = "refuse"}`, **Then** a write through that connector
   is `block` by rule 1 (`tool=mcp__<uuid>__.*`) with exit 1 and no draft; `draft` gives `ask`
   by rule 1; `send` gives `send` by rule 1.
5. **Given** a row with an unknown key (`persn = "U07"`) or a `tool` that is not a valid
   regular expression, **Then** `config.toml` does not load under any posture and `config
   check` names the row.
6. **Given** a seat runs `bin/wuwei config set outbound.tiers ...`, **Then** it is refused with
   the guard-settings reason (a seat never writes the table).

### User Story 3 - Posture floors stay above the table (Priority: P1)

**Independent Test**: `python -m pytest -q tests/test_outward.py -k floor tests/test_doctor.py -k tiers`.

**Acceptance Scenarios**:

1. **Given** `security.posture = "strict"` and `{ audience = "client", tier = "send" }`,
   **Then** a send to `C2` is `ask` by rule 6 (the default client row), the explain trace marks
   rule 1 `ignored under strict`, and `doctor` warns that rule 1 is ignored under strict.
2. **Given** the same row under `guarded`, **Then** the send goes out and `doctor` warns that
   rule 1 sends to a client audience (information only).
3. **Given** a message only the owner reads, **Then** it sends whatever the rows say (#495
   floor); **given** `WUWEI_SEAT_ROLE=shepherd`, **Then** every send is a draft (headless floor).

### User Story 4 - Classes are learned on the card (Priority: P2)

`bin/wuwei outbound learn` (#492) shows each new channel and person with its recommended class:
a channel the connector lists as shared with an external organisation is `client`, the rest
`team`; a reviewer of today's pull requests or a person named in today's records who is
internal is `team`. Approving records them.

**Independent Test**: `python -m pytest -q tests/test_outbound_learn.py -k class`.

**Acceptance Scenarios**:

1. **Given** a channel listing with `{"id": "C5", "shared": true}`, **Then** the card lists
   `channel #<name> (C5, <n> members): client, shared with an external org`.
2. **Given** `Approve`, **Then** `C5` is added to `outbound.external_channels` (class
   `client`), a team channel to `outbound.work_channels`, each person entry gets
   `class = "team"`, and the next commitment to `C5` is `block` by rule 3.
3. **Given** `Approve channels only`, **Then** both channel lists are written and no people.

### User Story 5 - The owner sees and explains the table (Priority: P2)

**Independent Test**: `python -m pytest -q tests/test_outbound.py -k "tiers or explain"`.

**Acceptance Scenarios**:

1. **Given** no owner rows, **Then** `bin/wuwei outbound tiers` prints the ten default rows
   numbered, tagged `default`, and a last line naming the kind rules; exit 0.
2. **Given** a pending draft id, **Then** `bin/wuwei outbound explain <id>` prints the stored
   rule, each party with its class and evidence, every row it passed and the row it matched,
   exit 0; an unknown id exits 1.
3. **Given** people in `outbound.people` without `class`, **Then** `doctor` warns once with one
   detail line per person (information only).

### Edge Cases

- A call with no destination and no addressed person (a tracker or docs write) has one party,
  the connector, with the connector's default class.
- A textless write (a monitoring resolve, a mode `send` connector) is decided by the table; it
  reaches the kind rules only when no row decides, which keep today's exit 2 for empty text.
- Mixed parties: block beats ask beats no row beats send. A call goes out by the table only
  when every party matched a `send` row; otherwise, with no `ask` or `block`, the kind rules
  decide.
- The shepherd review request form keeps its mentions out of the parties, as today.
- A connector default class from `outward.classes` applies only to MCP calls through that
  server; ports use the built-in default for their kind.
- Rule numbers shift when the owner adds a row; `outbound explain` recomputes with today's
  config and prints the stored reason beside it.

## Requirements

### Functional Requirements

- **FR-001** Tiers: `send` (the call goes on to the lint), `ask` (a #493 draft and card),
  `block` (exit 1, no draft, no card, the row named). `classify` returns
  `(0|1|2, 'send'|'draft'|'block')`.
- **FR-002** Audience classes `owner`, `team`, `company`, `client`, `public` (`AUDIENCES`).
  `outbound.people.<key>.class` (empty by default); `outbound.channel_classes.<id>`;
  `outward.classes.<server id>` (a connector's default for destinations and people it has not
  seen). A channel in `work_channels` is `team`, in `external_channels` `client`, unless
  `channel_classes` names it.
- **FR-003** Party classes, in order: the owner's identity is `owner`; the `is_dm`-free `is_*`
  audience flags make every destination `client`; a channel takes `channel_classes`, then the
  lists, then the connector default; a person takes its `class`, then `team` when internal by
  today's `_internal` evidence, then the connector default; `recipient_org` outside
  `outbound.code_host_orgs` and an external tracker board are `client`; a code-host pull
  request is `team` when measured as a team pull request (today's `_pr_context`), else the
  connector default. Built-in connector defaults: `tracker`, `docs` and `other` are `team`,
  every other kind `company`.
- **FR-004** Topics: `sensitive` (`sensitive_keywords`, `sensitive_patterns`), `commitment`,
  `disagreement`, all that match (not only the first).
- **FR-005** `outbound.tiers` is an ordered list of rows with optional `tool` (regular
  expression, full match, case-insensitive, against the tool name or the channel kind),
  `person` (id or `<namespace>:<id>`, case-insensitive), `channel` (id or class),
  `audience` (class), `topic` and required `tier`. Unknown row keys and invalid `tool` patterns
  are config errors under every posture.
- **FR-006** The effective table: one row per `outward.modes` entry (`{tool =
  "mcp__<server>__.*"}`, `send` to `send`, `draft` to `ask`, `refuse` to `block`), then the
  owner's rows, then the defaults (contracts/outbound-tiers.md). First match wins per party.
- **FR-007** Under `strict`, a `send` row never applies to a `client` or `public` party; the
  walk continues with the next row.
- **FR-008** The reasons follow contracts/outbound-tiers.md: an `ask` names the row in the
  #493 draft reason; a `block` is `outward: <fragment>; the owner decides: bin/wuwei outbound
  tiers`. No fragment holds `; `.
- **FR-009** When no row decides, today's kind rules decide unchanged except the audience
  branches the table replaced: DMs draft, `docs.auto`, `tracker.auto` with the port category,
  chat threads, chat with no single destination, the review ping and gate, and the
  acknowledgement, status, technical and mechanical reply shapes.
- **FR-010** `outward.check_send` and the guard's mode branches are removed; the guard passes
  the tool name to `outward.check_tier`. The lint guard's skip for a textless write through a
  `send` connector stays.
- **FR-011** `bin/wuwei outbound tiers` prints the effective table; `bin/wuwei outbound explain
  <draft id>` prints the trace. Both are read-only (`READ_ONLY`).
- **FR-012** `doctor` warns on people without a class and on owner `send` rows whose
  `audience` or `channel` is `client` or `public` (ignored under strict, information under
  guarded and observe).
- **FR-013** The learn card proposes shared channels as `client` and writes channels to
  `work_channels` or `external_channels` by class and `class = "team"` on people.
- **FR-014** `pr act --reply` and `outbound tier` handle `block` (print the reason, exit 1, no
  draft).
- **FR-015** No new import on the hook path; `CONFIG_CACHE_VERSION` bumped; `outbound.tiers`
  and `outbound.channel_classes` are private to profiles.
- **FR-016** Docs: concepts.md, configuration.md, security.md, reference.md, the workspace
  template.

### Key Entities

- Party: `{id, label, class, why}`; `why` is the class evidence used in reasons.
- Row: `{tool?, person?, channel?, audience?, topic?, tier}` with a source (`owner` or
  `default`).

## Success Criteria

- **SC-001** The five issue acceptance scenarios pass as tests through the guard or `classify`.
- **SC-002** With no owner rows and no classes set, every existing decision keeps its outcome
  (send stays send, draft stays draft) except three: a commitment or disagreement to a client
  audience is now `block`, a mode `refuse` connector exits 1 instead of 2, and a mode `send`
  connector no longer drafts topic hits (A5). Reason texts of table decisions change.
- **SC-003** The full suite passes, including the #346 import tests and the #362, #493 and #495
  reason tests (updated to the new texts).

## Assumptions

- A1 Lands on main after #492, #493, #495 and #502 (e6c65d6 holds them). It edits their code.
- A2 The issue's default "team `send` for tracker, docs and code_host" is not shipped as an
  unconditional row. Today those kinds send only through `tracker.auto`, `docs.auto` and a
  measured team pull request with an acknowledgement, technical or mechanical reply; an
  unconditional row would turn every seat tracker, docs and pull request write into a send on
  upgrade and make `tracker.auto` and `docs.auto` dead keys (constitution VII; design 4.9
  "unsure means approve"). Those kind rules are the fall-through below the table, shown as the
  last line of `outbound tiers`. The owner gets the literal default with one row, `{ audience =
  "team", tool = "tracker|docs|code_host", tier = "send" }`.
- A3 "Unknown" is not a sixth class: a person or destination WUWEI has not learned takes the
  connector's default class, `company` for chat, Slack, mail and the code host, so it asks
  (today's draft), and the learn card can then record it.
- A4 Channel classes: list membership is the class (`work_channels` team, `external_channels`
  client); `outbound.channel_classes` sets any other class. So no listed channel lacks a class
  and the `doctor` class warning covers people only.
- A5 The connector mode is the first row (issue). A mode `send` row therefore skips the topic
  rows, unlike #492's `check_send`: "always send" by tool is the owner's word. Under strict it
  still never reaches a client or public party (FR-007).
- A6 Owner rows come before the defaults, but two floors come before every row: the headless
  shepherd seat and a message only the owner reads (#495). `security.outbound` (canary and
  honeytoken) still runs before `classify`, and the lint after it.
- A7 (review F2) The draft card adds "Always send to this person" when an `ask by rule` row
  without a topic held a person, and "Always ask for this channel" when it held the destination
  channel. The option takes Drop's place (the card shows four options; Keep as draft names the
  drop command) and records `bin/wuwei drafts approve <id> --always`, which sends the draft and
  appends `{ person, tier = "send" }` or `{ channel, tier = "ask" }` to `outbound.tiers`.
- A8 (review F2) The learn card shows the recommended class per entry and adds one option per
  entry, `<id>-<class>`, that approves with that entry's other class: a channel team or client,
  a person team or company. A client channel goes to `external_channels`, a team one to
  `work_channels`, a person's class onto its `outbound.people` entry.
- A9 Block exits 1 (a finding), not 2: the mode `refuse` reason changes from exit 2 to exit 1.
  Both block a hook call.
- A10 The #493 reason keeps the draft id: `outward: draft <id>: ask by rule <n> (...): ...;
  the owner decides: bin/wuwei drafts show <id> --widget`.
- A11 `outbound explain` recomputes the trace with today's config instead of storing it on the
  draft row; for a code-host draft that reads the pull request through the code-host port.
- A12 Design 4.9 says every external party is an approve. The owner decided on 2026-10-04,
  after this item shipped, that the client commitment, client disagreement and `public`
  default rows are `ask`, not `block`: no default row blocks; the owner adds a `block` row.
  The design spec is amended only by its owner; this conflict is raised here and on the pull
  request, not resolved in the design spec.
- A13 `publish` stays owner-only (#478 grants) and is not part of this table; nothing in the
  publish guards changes.

### Builder corrections (implementation)

The plan as written broke SC-002 in four places; these corrections keep today's outcomes.

- B1 FR-003 and A3: the built-in `team` default for `tracker`, `docs` and `other` is the class
  of the connector itself (a call with no destination and no person). A person or destination
  the connector has not learned is `company` for every kind except `other` (`team`), unless
  `outward.classes` names one. Otherwise an unknown mention in a tracker comment with a
  `tracker.auto` category would send, where it drafts today
  (`test_tracker_auto_still_drafts_people_and_sensitive_text`).
- B2 FR-002: a channel in both `work_channels` and `external_channels` is `client`
  (`external_channels` is checked first), as "these override work channels" says today.
- B3 Edge case "textless write": a textless call that only a default `ask` row decides keeps
  today's exit 2 (nothing to show on a card). An owner row or a connector mode `draft` still
  holds a textless write as a draft, and `send` and `block` rows decide it.
- B4 The draft card under strict recommends Keep as draft for a row with a topic or a known
  audience; a row that held only an unknown destination, mention or DM recipient keeps Send
  now first, as today.
- B5 A DM with no destination (`is_dm` only) is a connector party and asks by rule 9; the DM
  kind rule (`approval tier direct message ...`) still drafts a DM to a team person. The tracker
  kind rule text drops "or the board is outside outbound.code_host_orgs" (the board is a party).

## Deferred

- Card options for any class other than the one alternative per learn entry (A8), and a card
  for a `block` decision.
