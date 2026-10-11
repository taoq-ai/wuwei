# Feature Specification: outward send is an exact tool allowlist and the owner's own surfaces are local; tiers, drafts, learning cards, graph, who and reply go

**Feature Branch**: `b5-guards` (feature directory `specs/838-outward-allowlist/`)

**Created**: 2026-10-11

**Status**: Draft

**Input**: Issue #838, part 16 of the #789 deletion pass: "chore(outward): outward send is an
exact tool allowlist and the owner's own surfaces are local; tiers, drafts, learning cards,
graph, who and reply go".

## Context

Part 15 (#837) is built first on this branch:

- one switch, `guards.enforce`;
- `guards.FLOOR` holds `outward.check_tier`, so a held outward send blocks whatever the switch
  says;
- the strict branches of `outward.py`, `drafts.py`, `commands/outbound.py` and `tracker.py` are
  gone.

Today an outward MCP write meets a policy of several layers:

- a channel from tool patterns, server aliases and a name vocabulary;
- an audience class per party (owner, team, company, client, public) from `outbound.people`,
  channel lists, company domains and code-host orgs;
- topic patterns (sensitive, commitment, disagreement, thread);
- a tier table (`outbound.tiers`, defaults, broad rows, server modes, `default_tier`) that
  answers send, ask or block. Ask becomes a draft (`drafts.py`, `wuwei drafts`) that the owner
  approves on a card. An unknown connector becomes a learning card (`wuwei outbound learn`,
  `outbound answer`) that writes channels, people and classes into config, mirrored in a
  register (`graph.py`, `.wuwei/graph.json`, `wuwei who`). PR thread replies are classified
  too (`pr act`, `wuwei reply`).

Each layer makes the planner and seats reason about the process: which tier, which draft,
which card, which class.

The owner decided (#789, 2026-10-11):

- outward sending is one exact allowlist of tools in config (`outward.allow`);
- a write whose target resolves to the owner (their self-DM, their own canvas or page) is
  local, never an outward send;
- an unlisted tool that may send to other people is refused, naming the one config line to add,
  which the owner approves on an Owner step card in the session;
- outward duties (PR ping, tracker update, day summary, PR thread replies) run through WUWEI's
  own adapter ports, configured by the owner. They are not the guard's concern beyond the canary
  floor and the outward-text lint.

Telemetry and DORA stay untouched (owner, 2026-10-11).

## The outward guard after this part

For one PreToolUse call, in order:

| The call | Result |
| --- | --- |
| Bash | the canary and honeytoken egress check and the owner disposition marker check, as today (floor) |
| a native tool (`Read`, `Write`, `AskUserQuestion`, ...) | passes |
| outside a workspace scope | passes |
| an MCP read (by name words, #469) | passes |
| a local tool (#727 class: `LOCAL_SERVERS`, `Claude_Browser` preview tools, a server the owner aliased `local` in `outward.servers`) | the canary check only |
| a write to the owner's own surface (every destination is the owner's, below) | local: the canary check and the outward-text lint addressed to the owner; recorded as `outward.to_owner` |
| a tool named exactly in `outward.allow` | the canary check and the outward-text lint |
| a name that is neither read nor write and resolves to no channel (review, Assumption 3) | passes; the lint guard logs the line below |
| anything else (a write, or an unknown name with a channel) | refused (floor) with the line below; for a Slack, docs or mail call the owner's surface line comes first |

The refusal names the line and the card:

```text
outward: mcp__<server>__<tool> may send to other people and is not on outward.allow; the owner
adds it: bin/wuwei config set outward.allow '["mcp__<server>__<tool>"]' --add (it asks its
Owner step card), then run the call again
```

`config set` already asks its own Owner step card (#831), so the planner asks that card and
reruns. Nothing runs in a host terminal.

### How a target resolves to the owner

Part 16 extends the #727 local class from a property of a tool to a property of a call. A call
is local when the tool is local, or when it has at least one destination and every destination
is one of the owner's identities. The destinations are the values under `channel`,
`channel_id`, `recipient`, `recipients`, `to`, `cc`, `bcc`, `page_id`, `database_id` and the new
`canvas_id`, at any depth: Notion's `parent.page_id` counts. For mail, every address in the
text counts too (#501). No new mechanism is added; `outward.owner_only` decides, and the guard's
existing local branch serves both.

| Surface | The owner's config | Matches |
| --- | --- | --- |
| Slack self-DM | `outbound.owner.slack.dm` (a `D...` id) and `outbound.owner.slack.user` (a `U...` or `W...` id) | a message whose channel or recipient is one of them |
| Slack canvas | `outbound.owner.pages` (canvas ids, `F...`) | a canvas write whose `canvas_id` (or channel, for a DM canvas) is the owner's |
| Notion or Confluence page | `outbound.owner.pages` (page ids) | a page update by `page_id`, or a create whose `parent.page_id` is the owner's page |
| Mail to self | `outbound.owner.mail` | every recipient, cc, bcc and address in the text is the owner's |

`outbound.owner.code_host` stays as the owner's login (`plan.py` reads it). A code-host comment
is read by others, so it is never local.

A call with no destination (a canvas created without a channel, a page without a parent) does
not resolve to the owner. It needs the tool on `outward.allow`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An unlisted tool that may send is refused with its config line (Priority: P1)

**Why this priority**: the issue's first acceptance line. It is the one outward edge (design
9.2).

**Independent Test**: hook payloads through `guards/outward.py`.

**Acceptance Scenarios**:

1. **Given** `outward.allow = []`, **When** a seat calls `mcp__slack__slack_send_message` to a
   team channel, **Then** the hook refuses with the line above, naming the exact tool, with
   `guards.enforce` true or false (floor).
2. **Given** that tool on `outward.allow`, **When** the same call runs, **Then** it passes the
   canary check and the outward-text lint and goes out.
3. **Given** `outward.allow = ["mcp__slack__slack_send_message"]`, **When**
   `mcp__slack__slack_schedule_message` is called, **Then** it is refused. The match is exact:
   no pattern, no prefix, no case folding.
4. **Given** an MCP tool whose name is neither a read nor a write and that resolves to no
   channel (`mcp__x__resolve_library_id`), **When** it is called, **Then** it runs and the lint
   guard logs `guard.would_refuse` naming the line (Assumption 3).
5. **Given** a listed tool whose payload carries a canary or honeytoken, **When** it is called,
   **Then** it is refused by the canary floor, as today.
6. **Given** the refusal, **When** the planner runs the named `config set ... --add`, **Then**
   it prints the Owner step card (header `Owner step`, the exact command including `--add`),
   and on Yes it writes the line and the call passes on retry.

---

### User Story 2 - The owner's own surfaces are local (Priority: P1)

**Why this priority**: owner constraint (B5). The day report in the owner's DM and notes on
their own canvas or page are never outward sends.

**Independent Test**: hook payloads with each surface of the table above.

**Acceptance Scenarios**:

1. **Given** `outbound.owner.slack.dm = "D123"`, **When** a Slack send to channel `D123` runs
   through a tool not on `outward.allow`, **Then** it passes, records `outward.to_owner`, and
   the lint runs without the third-person owner rule.
2. **Given** `outbound.owner.pages = ["F1"]`, **When** a canvas update with `canvas_id = "F1"`
   runs, **Then** it passes.
3. **Given** `outbound.owner.pages = ["abc"]`, **When** a Notion create with
   `parent = {page_id: "abc"}` runs, **Then** it passes.
4. **Given** the owner's mail, **When** a mail goes to the owner with a cc to someone else,
   **Then** it is not local and needs `outward.allow`.
5. **Given** a Slack send with two destinations, one the owner's DM and one a channel, **When**
   it runs, **Then** it is not local.
6. **Given** `outbound.owner` unset, **When** any send runs, **Then** nothing resolves to the
   owner.

---

### User Story 3 - Tiers, drafts, learning cards, the graph, who and reply are gone (Priority: P1)

**Why this priority**: the issue's second acceptance line.

**Independent Test**: grep, `wuwei --help`, `init --upgrade` on an old config.

**Acceptance Scenarios**:

1. **Given** the code, **When** it is grepped, **Then** no module, command, config key,
   charter, skill or docs page refers to tiers, drafts, learning cards, the graph, `who` or
   `reply`. Historical text stays: CHANGELOG, `specs/`, and the design spec's dated retirement
   lines.
2. **Given** `wuwei outbound`, `wuwei drafts`, `wuwei who`, `wuwei reply`, `wuwei lint tone`,
   **When** run, **Then** argparse refuses an unknown command.
3. **Given** a config with `outbound.tiers`, `outbound.default_tier`, `outbound.learn`,
   `outbound.people`, `outward.modes`, `outward.classes`, `outward.draft_ttl` or any other key
   plan.md retires, **When** `init --upgrade` runs, **Then** each is removed and reported
   (#799), `.wuwei/graph.json` is removed (one explicit removal: `RETIRED_FILES` reaches only
   `memory/`), and the graph comment lines in config.toml go.
4. **Given** a day state with `drafts`, `outbound_learn` or `outbound_threads`, **When** any
   command reads the state, **Then** it reads without error; nothing writes those keys again.

---

### User Story 4 - WUWEI's own outward duties still go out (Priority: P1)

**Why this priority**: outward duties (owner, 2026-10-11): a PR ping, a tracker update, a docs
page, the day report and a PR thread reply are duties the code makes happen.

**Independent Test**: the adapter port decorator and `pr act --reply`.

**Acceptance Scenarios**:

1. **Given** a chat, tracker, docs or code-host port call (`registry.outward_operation`),
   **When** it runs, **Then** it passes the canary check and the outward-text lint and is
   performed. No tier, no draft.
2. **Given** a ticket that `plan approve` opens through the tracker port, **When** the owner
   approves the plan, **Then** the ticket is created. No `drafts approve` step remains.
3. **Given** `bin/wuwei pr act <pr> --reply "<text>"`, **When** it runs, **Then** the reply is
   posted through the code-host port (`obligations.reply`) after the lint. The scope-change card
   (#834) is unchanged.
4. **Given** the lint refuses a port text (owner third person, banned character, length),
   **When** it runs, **Then** the port returns exit 1 with the lint reason, as today.

---

### User Story 5 - No text sends the owner to a terminal (Priority: P2)

**Independent Test**: `tests/test_reasons.py`.

**Acceptance Scenarios**:

1. **Given** the code, **Then** the part 16 LEFT rows (`drafts.py`, `commands/drafts.py`) are
   gone with their files, and the strict learning-card y/N path (`outbound answer` without a
   card through `decision.owner_confirm` and `_host_confirm`) is gone with the command.

### Edge Cases

- A call with no destination never resolves to the owner, so a misconfigured empty
  `outbound.owner` loosens nothing.
- `outbound.owner.slack` ids keep their shape check (`U`/`W` user, `D` DM), so a channel id
  configured by mistake is never the owner.
- A tool the owner aliased `local` in `outward.servers` stays local (#727). Aliasing is the
  owner's word, written by `config set` on a card.
- `outward.servers` other values (`slack`, `tracker`, `docs`, `code_host`, `mail`, `other`)
  keep naming the channel the lint uses for `max_length` and `humanize_kinds`.
- A Slack `chat` port DM to the owner is local by the same rule.
- An old `guard.would_refuse` or `hook.refusal` naming a draft still shows in `why`: the rule
  and fix lines stay, and the draft lookup goes.
- Telemetry keeps its `OWNER_KINDS` and `draft.*` event names as the vocabulary of stored
  weeks; no new event is added.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `workspace.SCHEMA` `outward.allow`: a list of exact MCP tool names, default `[]`.
  `load_config` refuses an entry that is not `mcp__<server>__<tool>` with no whitespace,
  naming the key.
- **FR-002**: `guards/outward.py` has one send check (`check_send`, replacing `check_tier`) in
  the order of the table above, and `check_lint` for allowed and owner-local text.
  `guards.FLOOR` names `outward.check_send`.
- **FR-003**: `outward.owner_only` decides owner-local for every surface in the table;
  `outbound.owner.pages` (list of ids) is added; `DESTINATIONS` gains `canvas_id`.
- **FR-004**: `outward.check_call` (the port policy) is the canary check plus the lint; the
  tier and draft branches of `registry.outward_operation` go.
- **FR-005**: Deleted: the tier table, audience classes, topics and `classify` in `outward.py`;
  `drafts.py`, `commands/drafts.py`, `commands/outbound.py`, `graph.py`, `commands/who.py`,
  `commands/reply.py`, `commands/lint.py` (`wuwei lint tone`), and every caller branch
  (plan.md).
- **FR-006**: Retired config keys are added to `workspace.RETIRED`; `init --upgrade` removes
  `.wuwei/graph.json` (a regular file inside the workspace) and the graph comment lines.
- **FR-007**: The refusal and the card add no host-terminal text; the `config set` card command
  includes `--add` when given.
- **FR-008**: Charters, skills, docs pages, the template and the design spec (4.1, 4.3, 4.9, 9.2)
  describe the allowlist and the owner's surfaces; no page names tiers, drafts, learning cards,
  the graph, `who` or `reply`.
- **FR-009**: `tests/test_tone.py` keeps the CI tone budget; the measuring helpers it needs move
  into the test file.

### Key Entities

- **outward.allow**: exact MCP tool names that may send to other people.
- **outbound.owner**: the owner's identity per surface (`slack.user`, `slack.dm`, `mail`,
  `pages`, and `code_host`, which is never local).

## Success Criteria *(mandatory)*

- **SC-001**: the three acceptance lines of the issue hold, each with a test (US1, US2, US3).
- **SC-002**: grep finds no tier, draft, learning card, graph, `who` or `reply` reference
  outside history.
- **SC-003**: the touched test files pass; CI is the gate.

## Assumptions

1. **The tone lint command is `wuwei lint tone`.** The issue lists it; the owner keeps the CI
   tone budget test (tests/test_tone.py). The command and the charter line that tells seats to
   run it go; the measure functions move into the test, which keeps the budget.
2. **The outward-text lint stays** (design 4.3: owner name, pronouns, banned characters, length,
   AI tells). It is not tier machinery, and the issue does not list it. `outward.patterns` (the
   internal-state words for client audiences) has no audience left to apply to, so it retires.
3. **Unknown tool names run and log (review, B5 lead call: no new walls).** An MCP tool that is
   neither a read nor a write by name and resolves to no channel (`mcp__Claude_Browser__computer`,
   `mcp__claude-in-chrome__navigate`) passes, as under the old guarded default; the lint guard
   logs `guard.would_refuse` naming the `outward.allow` line, with `guards.enforce` on or off. A
   write, or an unknown name that resolves to a channel, is refused with the line.
4. **Allowed and local sends are floor-checked in both enforce settings.** The send check is on
   the floor: with `guards.enforce = false` an unlisted send still refuses, as approve-tier
   sends did under observe.
5. **The port path is WUWEI's duties.** Port writes are configured by the owner (adapters,
   `tracker.auto`, `docs.auto`, `shepherd.review_channel`, `outbound.owner_channel`) and pass
   without `outward.allow`. A seat reaches a port only through a WUWEI command.
6. **`outward.tool_patterns`, `outward.servers` and the name vocabulary stay** to give the lint
   its channel (`max_length`, `humanize_kinds`) and to keep #727's `local` alias. They decide no
   send.
7. **`outbound.code_host_orgs` stays** while `outward._external_tracker` decides tracker label
   creation (`tracker.creates_labels`); part 20 owns the tracker.
8. **State keys** `drafts`, `outbound_learn`, `outbound_threads` and `pr_reply_drafts` are no
   longer written and leave the generic-write allowlist. `decision_routes` and
   `decision_outcomes` stay listed because metrics and telemetry read them for past days;
   `reply_acks` is still written by `pr act --reply` (`obligations.reply` stays). An old
   `state.json` that holds a deleted key still reads.

## Deferred

- Part 18: the D-n record library (`decision.py`) and its MCP cards.
- Part 20: tracker label creation and `outbound.code_host_orgs`.
- Part 24: README and the docs site rewrite beyond the pages this part must clean.
