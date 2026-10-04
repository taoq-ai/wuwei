# Feature Specification: any connector name resolves its channel, config lists keep their defaults, unknown connectors, work channels and people are learned and confirmed on one card, and no reason tells a seat to edit the guard's config

**Feature Branch**: `492-opaque-connector`

**Created**: 2026-10-04

**Status**: Draft

**Input**: GitHub issue #492, "fix(outward): any connector name resolves its channel (alias,
pattern anywhere in the name, vocabulary), config lists keep their defaults, unknown
connectors, work channels and people are learned from the connector and confirmed on one
card, and no reason tells a seat to edit the guard's config". Owner report on 0.15.0: a
review ping to four reviewers in a Slack work channel through a claude.ai Slack connector
(`mcp__<uuid>__slack_send_message`) could not be sent, and making it work took three
owner-only config edits in a host terminal. Owner: "All this should be done automatically."

## Root cause (read and reproduced on main, 58becfc)

Reproduced read-only with a scratch probe outside the repository that imports the guard
module and matches fixture tool names `mcp__00000000-0000-4000-8000-000000000001__<name>`
against the built-in rules and `tool_kind`:

| name | built-in rule | `tool_kind` | guard outcome on main |
|---|---|---|---|
| `slack_send_message` | none | write | refused, reason is a `config set outward.tool_patterns` line |
| `conversations_add_message` | none | write | refused, same line |
| `chat_postMessage`, `add_reaction`, `create_draft`, `save_issue` | none | write | refused, same line |
| `frobnicate_widget`, `append_block`, `trash_thread` | none | unknown | nudge or refusal by posture, same line |
| `slack_search_public`, `conversations_search_messages`, `channels_list`, `users_list` | none | read | passes |

1. **Brand before the last `__`.** `cli/wuwei/workspace.py:189-193`: every built-in
   `outward.tool_patterns` rule has the shape `mcp__.*<brand>.*__...`, so the brand must sit
   in the server segment. A claude.ai connector's server segment is a UUID and the brand is
   in the tool name (`mcp__<uuid>__slack_send_message`), so no rule matches
   (`cli/wuwei/guards/outward.py:108-109` and `123-124`).
2. **The only way out is a config line.** `cli/wuwei/guards/outward.py:141-169`
   (`_unmatched`) builds `bin/wuwei config set outward.tool_patterns '[...]'` (lines 150-151)
   and returns it as the reason for an unmatched write (line 153) and an unknown tool (lines
   159 and 168). The session read that as an instruction to edit the guard's own config.
3. **A list in config replaces its default.** `cli/wuwei/workspace.py:498` and `514-519`:
   a key present in the file replaces the schema default, and `cli/wuwei/commands/setup.py:85-98`
   (`set_value`) writes the given value as is. Setting `outward.tool_patterns` to one rule
   drops the five built-in rules.
4. **Unknown destinations and mentions draft with no way out.** `cli/wuwei/outward.py:342-344`
   drafts any mention that is not internal by `outbound.people`, and `364-367` drafts any
   destination not in `outbound.work_channels`. The guard's draft reason
   (`cli/wuwei/guards/outward.py:133-135`) names neither the unknown destination nor how to
   learn it, so the only fix is a hand edit of `work_channels` and `people`.
5. **The config refusal coaches a config line.** `cli/wuwei/guards/protect_state.py:79-80`:
   a seat running `config set` is refused (in every posture, the records floor) with "propose
   the line, and the owner runs bin/wuwei config set <key> <value>", which invites the seat
   to propose guard config.

The owner's "even a plain search" refusal was 0.15.0 behaviour: #469 (commit 88359c8,
after the 0.15.0 release commit 963a839) made noun-first and brand-first reads pass. On main
every read in the table passes; this feature keeps that (FR-002).

## User Scenarios & Testing

### User Story 1 - Any connector name resolves its channel (Priority: P1)

A seat calls a write tool of a connector whose server segment is opaque (a UUID). The guard
finds the channel from an owner alias, a built-in rule with the brand anywhere in the name,
or the tool vocabulary, and applies today's approval tier for that channel. Reads pass.

**Why this priority**: it is the owner's outage; without a channel every write of the
connector is refused with a config line.

**Independent Test**: `python -m pytest -q tests/test_outward.py -k "opaque or vocabulary or alias or recorded"`.

**Acceptance Scenarios**:

1. **Given** a guarded workspace, **When** the hook runs for
   `mcp__<uuid>__conversations_search_messages`, **Then** it exits 0 and no event is recorded.
2. **Given** no alias, **When** the guard runs for `mcp__<uuid>__slack_send_message`,
   **Then** the channel resolves to `slack` by the built-in rule (the reason of a draft names
   `channel slack`).
3. **Given** no alias, **When** the guard runs for `mcp__<uuid>__conversations_add_message`,
   **Then** the channel resolves to `slack` by vocabulary.
4. **Given** `[outward] servers = {"<uuid>" = "slack"}`, **When** the guard runs for
   `mcp__<uuid>__send_message`, **Then** the channel resolves to `slack` by the alias, and
   `mcp__<uuid>__conversations_history` still passes as a read.
5. **Given** `mcp__<uuid>__frobnicate_widget`, **Then** the reason (the strict refusal, or
   the `outward.unknown_tool` nudge under observe and guarded) names the connector `<uuid>`
   and `bin/wuwei outbound learn`, and no reason text contains `config set`.
6. **Given** an unknown write such as `mcp__<uuid>__send_message` with no alias, **Then** it
   is refused in every posture and the reason names the connector and `bin/wuwei outbound
   learn`, never `config set`.
7. **Given** recorded tool-name lists for a Slack connector, a mail connector, Linear and
   GitHub, each under a fixture UUID server, **Then** every read passes, and every write
   resolves to its expected channel or is refused naming `outbound learn`.

### User Story 2 - Config lists keep their defaults (Priority: P1)

The owner adds one item to a list key with `bin/wuwei config set` and the built-in items
stay in force.

**Why this priority**: today one `config set` silently removes the built-in Slack, Linear,
GitHub, Notion and Atlassian rules, or every built-in sensitive keyword.

**Independent Test**: `python -m pytest -q tests/test_setup.py -k "append or replace or show"`.

**Acceptance Scenarios**:

1. **Given** `config set outbound.work_channels '["C1"]'` by the owner, **Then** the
   effective list holds the defaults plus `C1`; with `--replace`, only `C1`.
2. **Given** `config set outward.tool_patterns '[{pattern = "mcp__acme__send", channel = "slack"}]'`,
   **Then** the effective list holds the five built-in rules and the new rule.
3. **Given** `config set outbound.people '{"slack:U01" = {email = "ada@example.com"}}'`,
   **Then** the entry is added and existing people stay.
4. **Given** `config show outward.tool_patterns`, **Then** each effective row is printed with
   a `default` or `owner` tag.
5. **Given** `--replace` on a key that is neither a list nor a named-entry table, **Then**
   the command exits 1 and writes nothing.

### User Story 3 - Unknown connector, destination or people are learned and confirmed once (Priority: P1)

A send is held back because the connector, the destination channel or the mentioned people
are unknown. The reason names one command. The planner session calls the connector's
listing tools, saves the results, and runs `bin/wuwei outbound learn`, which writes one
decision record and prints one card. The owner's answer writes the alias, the work channels
and the people into config, and the same send goes out.

**Why this priority**: it is the owner's principle for this report: nothing is typed by hand.

**Independent Test**: `python -m pytest -q tests/test_outbound_learn.py`.

**Acceptance Scenarios**:

1. **Given** a send through `mcp__<uuid>__send_message` to an unknown channel `C01` with two
   unknown mentions `<@U01>` and `<@U02>` who are the day's reviewers, **Then** it is held
   back and the reason names `bin/wuwei outbound learn`.
2. **Given** the planner's listing files (`--channels`, `--people`), **When** the planner runs
   `bin/wuwei outbound learn --tool mcp__<uuid>__send_message --as slack --channels <file>
   --people <file>`, **Then** exactly one decision record and one card are produced; the
   card asks "Connector <uuid> is Slack; add 1 work channel and 2 people?" with the options
   `Approve`, `Approve channels only` and `Defer: keep as drafts`.
3. **Given** `Approve` is recorded (`wuwei decide D-n approve`), **Then** `outward.servers`
   maps `<uuid>` to `slack`, `outbound.work_channels` holds `C01`, `outbound.people` holds
   `slack:U01` and `slack:U02`, one `outbound.learned` event is recorded, and the same send
   now passes the guard.
4. **Given** `Approve channels only`, **Then** the alias and the channel are written and the
   people are not; the same send still drafts.
5. **Given** `Defer: keep as drafts`, **Then** nothing is written, the send is a draft as
   today, and a second `outbound learn` for the same connector today refuses to propose it
   again.
6. **Given** `outbound.learn = "auto"` under guarded (or observe), **Then** no record or card
   is produced, the config entries are written at once and one `outbound.learned` event is
   recorded; under strict a card is asked as for `"card"`.
7. **Given** `outbound.learn = "off"`, **Then** the guard reasons name the draft and not
   `outbound learn`, and `outbound learn` refuses with exit 1.
8. **Given** a listed person who is not a reviewer of any of today's pull requests and is not
   named in today's plan or decision records, **Then** that person is not proposed; under
   `"auto"` only reviewers are learned.

### User Story 4 - No reason tells a seat to edit the guard's config (Priority: P2)

A seat tries `bin/wuwei config set outward.tool_patterns ...`, or reads a refusal in this
area.

**Why this priority**: the session planned to register the tool in `outward.tool_patterns`
because the reason told it to.

**Independent Test**: `python -m pytest -q tests/test_protect_state.py -k guard_config tests/test_outward.py -k config_set`.

**Acceptance Scenarios**:

1. **Given** a seat running `bin/wuwei config set outward.tool_patterns '[]'`, **Then** it is
   refused in observe, guarded and strict, and the reason names the owner and `outbound
   learn`, not a config line to propose. The same holds for `security.*`, `outbound.*` and
   `grants`.
2. **Given** a seat running `bin/wuwei outbound learn ...`, **Then** it is refused with a
   reason naming the planner; the registered planner session runs it.
3. **Given** every reason produced by channel resolution, the unknown-tool nudge and the
   destination and people draft, **Then** none contains `config set`.

### Edge Cases

- A read stays a read whatever the alias or vocabulary says: the alias and vocabulary steps
  run only for tools `tool_kind` does not call a read, so a Slack alias never sends
  `conversations_history` to the approval tier.
- A tool name matching two vocabularies (`create_issue_label` is tracker and mail) is
  ambiguous and falls to the learn path.
- A built-in rule now matches the brand anywhere in the full name; a verb inside a read name
  (`pin` in `mapping`) would route a read to the tier. The recorded Slack list guards this.
- A listing row whose name holds a newline, `|`, a backtick, `$` or a backslash is refused
  (exit 1): names go into a decision record and a card.
- A listing channel marked `shared`, a direct message id (`D...`) or a channel in
  `outbound.external_channels` is never proposed as a work channel.
- A person whose email domain is not in `outbound.company_domains` is proposed with the
  organisation of a reviewed pull request (`org`) when that organisation is in
  `outbound.code_host_orgs`; otherwise the person is not proposed, since the outbound tier
  would not treat them as internal.
- A second `outbound learn` while a learn card is open today prints that card again instead of
  writing a second record (one card per day batch).
- A config file whose `[outbound] people` or `[outward] servers` is written as an inline
  table cannot take a new entry by section; the write fails with today's layout reason and
  nothing is written.

## Requirements

### Functional Requirements

- **FR-001**: The guard resolves an MCP tool's channel in this order, stopping at the first
  hit: the owner alias `outward.servers["<server id>"]`; the effective `outward.tool_patterns`
  rules; the tool vocabulary when exactly one channel matches. Otherwise the connector is
  unknown.
- **FR-002**: Reads pass as in #469 whatever the server id: the alias and vocabulary steps
  are skipped for a tool `tool_kind` calls a read.
- **FR-003**: The built-in rules match the brand word anywhere in the full tool name.
- **FR-004**: The vocabulary (extended by FR-016) covers: Slack (`conversations_*`, `channels_*`, `chat_post*`,
  `add_message`, `add_reaction`), tracker (an `issue` word), mail (a `draft`, `label`,
  `thread`, `spam`, `trash`, `forward`, `inbox`, `mail` or `email` word) and docs (a `page`,
  `block` or `database` word).
- **FR-005**: An unknown write is refused in every posture; an unknown tool follows the
  outward area as in #469. Both reasons name the connector and `bin/wuwei outbound learn
  --tool <tool>`, or, under `outbound.learn = "off"`, the draft only.
- **FR-006**: The draft reason for a Slack send whose destination is not a work channel or
  whose mentions are not in `outbound.people` names the unknown destination and the number of
  unknown mentions and `bin/wuwei outbound learn --tool <tool>` (not under `"off"`). The
  approval policy (`outward.classify`) is unchanged.
- **FR-007**: `config set` on a list key appends the given items to the effective value; on a
  named-entry table (`outbound.people`, `outward.servers` and every `*` table) it adds or
  replaces the given entries. `--replace` writes the value as given. `config show <key>` prints
  the effective value, one row per item or entry, tagged `default` or `owner`.
- **FR-008**: `bin/wuwei outbound learn --tool <tool> [--as <channel>] [--channels <file>]
  [--people <file>]` proposes the alias (when the server has none), the work channels and the
  people (contract in `contracts/outbound-learn.md`). Without listing files for a Slack
  connector it prints which listing tools to call and the full command, and exits 1.
- **FR-009**: People are proposed only when they are reviewers of today's pull requests
  (`pr_reviewers`, matched by `shepherd.authors` or `author_logins` email or mention) or named
  in today's `plan.md` or decision records; the latter only on the card. The guard never adds
  a person from a free-text mention.
- **FR-010**: Under `outbound.learn = "card"` (default), or `"auto"` under strict, learn
  writes one decision record (class `other`, three options), routes it to the owner, stores
  the proposal under the reserved state key `outbound_learn`, and prints the #359 widget.
  Under `"auto"` in observe or guarded it writes the config at once. Under `"off"` it refuses.
- **FR-011**: The owner's recorded answer (`wuwei decide D-n <option>`, from the planner's
  gate question or a host terminal) writes `outward.servers`, `outbound.work_channels` and
  `outbound.people` for `approve`, the alias and channels for `channels`, nothing for `keep`,
  and records one `outbound.learned` event for a write.
- **FR-012**: `outbound.learned` is a reserved event kind; `outbound_learn` is a reserved
  state key; seats cannot forge either.
- **FR-013**: The hook refuses `config set` on `outward.*`, `security.*`, `outbound.*` and
  `grants*` from any agent tool in every posture with a reason naming the owner and `outbound
  learn`. `outbound learn` runs only in the registered planner session.
- **FR-014**: No new import on the hook path (#346); `CONFIG_CACHE_VERSION` is bumped.
- **FR-016** (scope addition): a sixth class `other` joins `outward.servers` and `--as`.
  The vocabulary splits camelCase (`addCommentToJiraIssue` is tracker, `getJiraIssue` a
  read), resolves `pull_request` plus `comment` to `code_host`, and resolves resolving,
  muting or triggering an issue, alert or incident, and alert rules, to `other`; those names
  are not tracker. `mute` and `trigger` join the write words.
- **FR-017** (scope addition): `outward.modes["<server id>"]` is `send` (security, the
  sensitive, commitment and disagreement patterns and the lint; no audience rules; a write
  without text passes), `draft` (every write drafts) or `refuse` (every write refused). Reads
  ignore it. Without an owner mode, `other` is `send` and every other class keeps its tier
  (slack and mail draft unless a work channel with known people; tracker, docs and code_host
  as today).
- **FR-018** (scope addition): the learn card states the class and mode in its question
  (`Connector <id> is Slack, mode draft; ...`) and offers `Approve, mode <mode>` for each
  other mode; that answer records the alias, the channels, the people and the mode.
  `Approve channels only` appears only when channels are proposed.
- **FR-015**: `docs/site/configuration.md`, `docs/site/security.md`,
  `docs/site/reference.md`, the workspace template and the plan skill document the above.

### Key Entities

- `outward.servers`: table, server id to channel (`slack`, `tracker`, `code_host`, `docs`,
  `mail`, `other`).
- `outward.modes`: table, server id to `send`, `draft` or `refuse`.
- `outbound.learn`: `"card"` (default), `"auto"` or `"off"`.
- `outbound_learn` state key: `{D-n: proposal}`; proposal is `{server, channel, alias,
  channels: [{id, name, members}], people: [{id, name, entry}], answered}`.
- `outbound.learned` event: `{decision or null, option, server, channel, channels: [ids],
  people: [ids]}`; ids only, no names or emails.

## Success Criteria

- **SC-001**: The owner's scenario (an opaque Slack connector, an unknown work channel, two
  reviewers mentioned) goes from held back to sent with one card answer and no config typed.
- **SC-002**: No reason in the outward area contains `config set`; a test scans them.
- **SC-003**: The full suite passes, including the #346 import tests and the #362 reasons
  test.

## Assumptions

- A1 Append happens in `config set`, not in `load_config`: a list written in `config.toml`
  still means the whole list. Merging defaults at load time would silently change existing
  owner files, for example `tracker.auto = []` (no automatic tracker writes) would turn the
  three built-in automatic kinds back on. `config set` without `--replace` writes the
  effective list plus the new items, so the defaults stay in force.
- A2 The third option is titled `Defer: keep as drafts` (option id `keep`) because every
  decision record needs a Do nothing or Defer option (`decision._scored`); the owner's
  "Keep as drafts" is the text after the colon.
- A3 "This item's reviewers" is read as the reviewers of every pull request in today's
  `pr_reviewers`: a send is not tied to one item in the hook, and `pr_reviewers` is written
  only by `wuwei pr raise` or `ping`.
- A4 "Named in a record" is today's `plan.md` and `decisions/*.md`. Seats can write decision
  records, so record-named people are only proposed on the card the owner answers, never
  under `"auto"`.
- A5 The listing files use a small JSON shape defined in `contracts/outbound-learn.md`; the
  planner writes them from whatever the connector returns. The hook never calls MCP.
- A6 `--as` names the channel when the refused tool does not resolve by rule or vocabulary;
  the planner knows the connector, the CLI does not.
- A7 Which channels to learn is the planner's selection in the listing file (the channels the
  message goes to); learn filters out shared, external and direct-message channels.
- A8 People entries carry `email` when its domain is in `outbound.company_domains`, else
  `org` of a reviewed pull request's organisation when that organisation is in
  `outbound.code_host_orgs`; the outbound tier needs one of those to treat a person as
  internal. Learning a company domain is out of scope.
- A9 `config set` refusals already block every agent tool in every posture (records floor);
  only the reason for guard keys changes. The planner session is refused too, as today.
- A10 `grants` (#478) does not exist yet; the guard-key prefix list names it so #478 needs no
  change here.
- A11 The `mail` channel has no humanize kind and no auto-send path in `outward.classify`, so
  every mail write drafts.
- A12 The existing #469 tests that pin the `config set outward.tool_patterns` line or exit 2
  for names the vocabulary now resolves are updated: that line was the defect.
- A13 (scope addition) The mode lives in a sibling table `outward.modes`, not inside
  `outward.servers`, so existing `servers` entries stay plain strings.
- A14 `resolve` is not a write word: `resolve-library-id` style read tools would become
  refused writes. A Sentry `resolve_issue` still resolves to `other` by the vocabulary, which
  does not depend on the word lists. `assign` and `archive` were write words already and stay
  with their object's class (`assign_copilot_to_issue` is tracker).
- A15 The workspace template shows `outward.servers`, `outward.modes` and `outbound.people`
  as sections: an inline table cannot take a learned entry (the edge case above).
