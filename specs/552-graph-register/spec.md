# Feature Specification: People, channels and tools register

**Feature Branch**: `552-graph-register`
**Created**: 2026-10-08
**Status**: Draft
**Input**: GitHub issue #552: people, channels, tools and their relations are one register
with typed edges that the config sections become views over, with `wuwei who` to walk it
and `wuwei why` citing the edge that decided a hold.

## Root cause

What WUWEI learns about a workspace is relational, but nothing models the relations. Each
reader parses its own flat section, each writer writes its own key, and no record or
command joins them:

- Readers, one section each: `cli/wuwei/outward.py:460-529` (`_parties`) reads
  `outbound.channel_classes`, `external_channels`, `work_channels` and, through `_person`
  (`:443-457`), `outbound.people`; `:433-440` (`_default`) reads `outward.classes`;
  `:397-404` (`table`) reads `outward.modes`; `cli/wuwei/guards/outward.py` (`resolve`)
  reads `outward.servers`; `cli/wuwei/shepherd.py:46` and `:210` read `shepherd.authors`;
  `cli/wuwei/voice.py:54-56` (`audience`) reads `voice.sources`; `outward.py:115` reads
  `owner.handles`; `outward.py:232-236` reads `outbound.owner`.
- Writers: `cli/wuwei/commands/outbound.py:387-431` (`apply`, the learn card) writes four of
  those keys through `setup._edit`, which ends in `cli/wuwei/commands/config.py:236-256`
  (`offer`). `offer` (`:252`) and `cli/wuwei/commands/init.py:360` (`upgrade`) are the only
  two places that write `config.toml`. Neither records that a person was seen in a channel,
  what a person's mail address, login and chat id are to each other, or which connector a
  learned channel came through.
- Explanations: `cli/wuwei/commands/why.py:170-198` (`refusal`) prints the guard's reason
  text, which names a config key (`C1 in outbound.external_channels as client`), never the
  relation; there is no command that answers "who is in this channel and what tier applies"
  (`outbound explain` needs a draft id and prints the tier table walk, not the people).

## User Scenarios and Testing

### User Story 1: The owner or the planner asks who a channel is (Priority: P1)

A workspace has learned, on cards, a connector, its channels and the people in a thread.
The owner runs `bin/wuwei who C01` (or the planner runs `bin/wuwei who C01 --json`) and
gets the channel's class, the people known to be in it, the tier a routine message there
gets, and the edges behind each fact, in plain words. Nothing is written, and every guard
decides exactly as before.

**Why this priority**: it is the owner's ask: navigate the knowledge instead of reading six
sections and the guard code.

**Independent Test**: neutral workspace in `tmp_path`; one `outbound learn` card with a
`--channels` file (C01, not shared), a `--thread` file for `C01` with participants U01 and
U02 at internal addresses, answered `approve`; then `who` in text and JSON.

**Acceptance Scenarios**:

1. **Given** that learned workspace, **When** `bin/wuwei who C01` runs, **Then** it exits 0
   and prints the node `channel:C01` with its name, `class team (outbound.work_channels)`,
   the people `person:slack:U01` and `person:slack:U02` with their names and classes, and
   `a routine message here: send`.
2. **Given** the same, **When** `bin/wuwei who C01 --json` runs, **Then** stdout is one JSON
   list with one object `{node, name, edges, tier, rule}` where `tier` is `send` and `edges`
   holds the class edge and both `member_of` edges, each `member_of` edge naming the card.
3. **Given** the same, **When** `bin/wuwei who U01` runs, **Then** it prints
   `person:slack:U01`, its class edge from `outbound.people`, its address edge, the channel
   it is a member of, and the tier of a routine direct message to it.
4. **Given** a connector `acme` learned with mode `draft`, **When** `bin/wuwei who
   mcp__acme__send_message` or `bin/wuwei who connector:acme` runs, **Then** it prints
   `connector:acme` with `sends_through slack (outward.servers)` and `mode draft
   (outward.modes)` and the tier a routine write through it gets.
5. **Given** a login mapped in `shepherd.authors` to a mail address and a chat mention,
   **When** `bin/wuwei who login:dev` runs, **Then** it prints the address and the chat
   person the login maps to, and the tier through that chat person.
6. **Given** a name no node has, **When** `who` runs, **Then** it exits 1 and names
   `bin/wuwei outbound learn` as the way people and channels are learned.
7. **Given** the same fixture, **When** every outbound and outward guard decision is
   computed once from `config.toml` and once from a config whose modeled keys are replaced
   by the register's views, **Then** every decision and reason is identical (the
   register-or-view invariant).

### User Story 2: An upgraded workspace has the register and doctor is clean (Priority: P1)

An existing workspace with people, channels, connectors, author mappings, owner handles and
voice sources in `config.toml` runs `bin/wuwei init --upgrade`. The register is created
from those sections once, the sections stay where they are with a comment naming the
register, and `bin/wuwei doctor` reports the register as matching.

**Independent Test**: neutral workspace whose `config.toml` sets every modeled key; run the
upgrade; read `.wuwei/graph.json`; run `doctor` in-process.

**Acceptance Scenarios**:

1. **Given** that workspace without `.wuwei/graph.json`, **When** `bin/wuwei init
   --upgrade` runs, **Then** it writes `.wuwei/graph.json`, prints `Upgraded
   .wuwei/graph.json: <n> nodes and <m> edges from config.toml`, the register holds a node
   for every people key, channel id, connector id, author address, login, mention, owner
   handle and voice audience the sections held, and every owner value in `config.toml` is
   unchanged.
2. **Given** the upgraded workspace, **Then** each modeled table header in `config.toml`
   carries the comment line naming the register, once; a second upgrade adds nothing and
   prints no register line.
3. **Given** the upgraded workspace, **When** `bin/wuwei doctor` runs, **Then** its
   `register` row is `ok` and names the node and edge counts.
4. **Given** the owner then hand-edits `config.toml` (adds `outbound.work_channels =
   ["C09"]`), **When** `doctor` runs, **Then** the `register` row is `warn`, names
   `outbound.work_channels` as the drifted key and offers `bin/wuwei init --upgrade`, which
   takes the config value into the register; afterwards the row is `ok`.
5. **Given** `--dry-run`, **Then** the upgrade prints `Would upgrade .wuwei/graph.json: ...`
   and writes nothing.
6. **Given** a fresh `bin/wuwei init`, **Then** the workspace has an empty register and
   `doctor` reports it `ok`.

### User Story 3: Every write path keeps register and view together (Priority: P1)

Every command that writes a modeled key (`outbound learn` apply, `setup`, `setup slack`,
`calibrate --answer`, `config set` with or without `--from-card`, `config promote`, `drafts
approve --always`, `grants`) writes the register in the same step as `config.toml`, through
the one config writer.

**Acceptance Scenarios**:

1. **Given** an upgraded workspace, **When** `bin/wuwei config set outbound.work_channels
   '["C05"]'` is confirmed, **Then** the register has `channel:C05 class team` with view
   `outbound.work_channels` and `doctor` stays clean.
2. **Given** an `outbound learn` card answered `approve` with a thread of participants,
   **Then** the register gains the connector, channel and people nodes with their names,
   the view edges, and a `member_of` edge from each approved participant to the thread's
   channel naming the card; `doctor` stays clean.
3. **Given** a damaged `.wuwei/graph.json`, **When** any config write runs, **Then** it
   writes `config.toml` as today with its usual exit, leaves the damaged register untouched
   and prints one stderr warning naming the fix (move the file aside, run `bin/wuwei init
   --upgrade`); no guard reads the register, so a damaged one never stops a card answer.
4. **Given** an agent tool call (Write, Edit or a Bash redirect) that targets
   `.wuwei/graph.json`, **Then** the records floor refuses it under every posture with a
   hint naming the commands that write it.

### User Story 4: `wuwei why` names the edge that decided a hold (Priority: P2)

A message to a client channel is held as a draft. The owner runs `bin/wuwei why
draft-<id>` or `bin/wuwei why last refusal` and sees, after the rule, the register edge
that gave the channel its class.

**Acceptance Scenarios**:

1. **Given** `C01` in `outbound.external_channels` in the register and a slack write to
   `C01` held by the outward guard as a draft, **When** `bin/wuwei why <draft id>` runs,
   **Then** it exits 0 and prints the held rule and `edge: channel:C01 class client
   (outbound.external_channels)`.
2. **Given** the hook recorded that hold as a refusal, **When** `bin/wuwei why last
   refusal` runs, **Then** the same `edge:` line follows the refusal's rule line.
3. **Given** a hold decided by a connector's mode row (`outward.modes`), **Then** the edge
   line names `connector:<server> mode draft (outward.modes)`.
4. **Given** a hold whose deciding party has no edge (an unknown destination that took the
   connector's built-in default class), **Then** the line reads `edge: not recorded`.
5. **Given** an unknown draft id, **Then** `why` exits 1 and names `bin/wuwei drafts`.

### Edge Cases

- A channel in both `work_channels` and `external_channels`, and one also in
  `channel_classes`: each key keeps its own edge and view, so the precedence the guard
  applies (channel_classes, then external, then work) reads the same lists.
- A people entry with no fields (`"slack:U9" = {}`) is still a node of the
  `outbound.people` view.
- Mixed-case keys and duplicate list items survive the round trip unchanged.
- `who` with a bare name that matches more than one node prints every match.
- A missing register: `who` exits 1 naming `bin/wuwei init --upgrade`; doctor warns with the
  same fix; a config write creates the register.
- A symlinked or invalid register is damaged: `who` exits 2 with the fix; writers and
  `init --upgrade` warn with the fix, write the config as today and never overwrite the
  damaged file; doctor's row is `warn` (never `fail`, which would hold `setup` at Next).
- `who` never calls a port: a code-host login with no chat mapping has no tier line, and
  says the pull request rules decide there.

## Requirements

### Functional Requirements

- **FR-001**: The workspace has one register, `.wuwei/graph.json`, holding nodes (kinds
  `person`, `channel`, `connector`, `login`, `address`, `org`, `voice`, `repo`) and typed
  edges (`member_of`, `class`, `sends_through`, `mode`, `maps_to`, `reviews`). Node ids
  use the target key forms of design 5.8.1 (`channel:<id>`, `person:<ns>:<id>`,
  `repo:<org>/<name>`); edges whose target is a value (a class, a mode, a channel kind)
  carry the bare word.
- **FR-002**: Every modeled config key (Assumption A4) is a view: each of its entries is
  one or more edges that name the view key, and the view computed from the register equals
  the key's value in the loaded config. Edges with no view (a person seen in a channel) are
  register-only and name the card that wrote them.
- **FR-003**: Guards, sweeps and every other reader keep reading `config.toml` through
  `workspace.load_config`; no guard, decision or reason text changes.
- **FR-004**: The one config writer (`config.offer`) writes the register before it writes
  `config.toml`, from the same validated text. A register it cannot read or write is never
  overwritten: the writer prints one warning naming the fix and writes `config.toml` with
  its usual exit (#530: the register decides nothing, so it never blocks a write).
- **FR-005**: `outbound learn` apply adds, after a clean write, the names of approved
  channels and people as node names and a `member_of` edge from each approved thread
  participant to the thread's channel, naming the card.
- **FR-006**: `bin/wuwei who <name>` (read-only) resolves a node id, a people key, a bare
  id, a node name or an MCP tool name, and prints per match: the node and its name, its
  class (when it has one), its known people (for a channel), its edges each with view or
  card, and the tier a routine message there gets, computed by `outward.classify`, the
  function the guard calls. `--json` prints a list of `{node, name, edges, tier, rule}`.
  Exits 0 found, 1 no match or no register, 2 damaged register or unreadable config.
- **FR-007**: `bin/wuwei why <draft id>` prints the draft's held rule and the `edge:`
  lines of the register edges that decided it (an edge of a node the rule names whose view
  key the rule names); `why last refusal` and `why <event id>` add
  the same lines to an outward refusal that names a draft.
- **FR-008**: `bin/wuwei init --upgrade` builds the register from the config sections when
  it is missing or differs from them, keeping register-only edges and names, prints one
  line, adds the comment naming the register above each modeled table header once, and
  changes no owner value; `--dry-run` writes nothing; a damaged register is a warning with
  the fix and the rest of the upgrade runs. A fresh `init` ships an empty register.
- **FR-009**: `bin/wuwei doctor` has a `register` row: `ok` with counts, `warn` for a
  missing register or a drift (detail names each drifted view key; fix and apply
  `init --upgrade`), and `warn` for a damaged one (fix: move it aside, then `init
  --upgrade`; no apply). Never `fail`: `setup` treats a failing workspace row as required
  (A13). The template row does not repeat the
  register line.
- **FR-010**: `.wuwei/graph.json` is protected by the records floor with a hint naming the
  commands that write it.
- **FR-011**: Docs: `docs/site/configuration.md` gains the section "People, channels and
  tools" (the model, the views, `who`, drift); each modeled key's description points at it;
  `docs/site/reference.md` lists `bin/wuwei who` and the `why` edge line.

### Key Entities

- **Register** (`.wuwei/graph.json`): `{"version": 1, "nodes": {<id>: {"name"?, "view"?}},
  "edges": [{"from", "type", "to", "view"? | "card"?}]}`.
- **View key**: a dotted config key whose value is computed from the edges that name it.
- **Edge citation**: one line `<from> <type> <to> (<view or card>)`.

## Success Criteria

### Measurable Outcomes

- **SC-001**: For a fixture that sets every modeled key, the views computed from the
  register equal the loaded config's values for all of them, and a table of guard calls
  gives identical decisions and reasons from either source.
- **SC-002**: `who <channel>` answers class, people and tier in one command; the owner or
  planner opens no config section or guard code to get them.
- **SC-003**: After `init --upgrade` on that fixture, `doctor`'s register row is `ok`; one
  hand edit of a modeled key turns it `warn` naming that key; `init --upgrade` returns it to
  `ok`.
- **SC-004**: Every command that writes a modeled key leaves the register row `ok`.
- **SC-005**: The existing outward, outbound, learn, why, doctor, init and setup tests pass
  unchanged.

## Assumptions

- **A1**: A JSON file under `.wuwei/`, not a `[graph]` table: a table would make
  `config.toml` both the source and the view, and the records floor already knows how to
  protect a JSON record (`memory/targets.json`).
- **A2**: The guards keep reading `config.toml`, so the register and the view are written
  together by the one writer, register first. The view text is made by the existing writer
  (`setup._settle`, `configtext.place`) as today, and the register's view edges are built
  from that same validated text, so there is no TOML generator to keep in step. A hand edit
  of `config.toml` (an owner action in a host terminal) is drift; `init --upgrade` takes the
  config value into the register, because the owner's own edit is the owner's intent.
- **A3**: The tier rows (`outbound.tiers`) and the defaults stay rules, not edges: they
  decide by class and topic, and `who` computes the tier through `outward.classify`.
- **A4**: Modeled view keys: `outbound.people`, `outbound.channel_classes`,
  `outbound.work_channels`, `outbound.external_channels`, `outbound.owner.slack.user`,
  `outbound.owner.slack.dm`, `outbound.owner.mail`, `outbound.owner.code_host`,
  `outward.servers`, `outward.modes`, `outward.classes`, `shepherd.authors`,
  `owner.handles`, `voice.sources`, and `repos.<n>.shepherd.reviewers` (view
  `repos.shepherd.reviewers`, keyed by repository name).
- **A5**: Not modeled: `shepherd.lead_login`, `shepherd.reviewers`,
  `shepherd.reviewers_exclude`, `outbound.company_domains`, `outbound.code_host_orgs`,
  `outward.tool_patterns`: single settings and boundary lists, not relations between nodes.
- **A6**: Tool nodes are not stored: a tool's connector is the server id in its name, as
  `guards/outward.resolve` reads it; `who` walks from the tool name to the connector.
- **A7**: `member_of` from a person to a channel is register-only. Its one writer is the
  learn card for a thread's participants (they posted there); mentioned people and listed
  channels on one card are not assumed to be members.
- **A8**: The owner is the node `person:owner`; a handle that has the Slack user id shape
  maps to `person:slack:<id>`, any other to `login:<handle>`.
- **A9**: `tests/test_invariants.py` and the design 9.2 invariant table are not on this
  base; the register-or-view invariant is pinned in `tests/test_graph.py`. If #530's test
  lands first, the builder adds the row there too. The design spec is amended only by its
  owner, so it is not edited here.
- **A10**: #507 (deletion pass) has not landed on this base; the register models what the
  sections hold today. #444's PoC under `scripts/poc` is left alone.
- **A11**: The #522 tone rule is not on this base; `who` prints one fact per line in plain
  words.
- **A12**: Node names come only from learn cards; a node made from config alone has no
  name.
- **A13**: The register is an explanation record, not a guard input. Every failure to read
  or write it is a warning with the fix (`who` excepted, which exists to read it and exits
  2), so it adds no refusal and no stop to any write path (#530, owner 2026-10-08: autonomous
  and agile, not bureaucracy).
- **A14**: A thread participant already in `outbound.people` needs no card (#526), so no
  `member_of` edge is written for it on that path: the register is written only by the CLI
  after an owner answer or an owner-confirmed config write. `who` lists the people the cards
  recorded.

## Deferred

- Design spec 3.3 (workspace layout) and 9.2 (invariant table) rows for the register: owner
  amendment.
