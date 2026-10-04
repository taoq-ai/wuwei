# Contract: outbound tier table (#496)

## Config

```toml
[outbound]
work_channels = ["C1"]          # class team
external_channels = ["C2"]      # class client
tiers = [                       # owner rows, before the defaults; first match wins
  { person = "U07", tier = "send" },
  { channel = "C3", topic = "commitment", tier = "block" },
]

[outbound.channel_classes]      # any class for a channel id; overrides the lists
C4 = "public"

[outbound.people]
"slack:U07" = { email = "dev@example.test", class = "team" }

[outward.classes]               # a connector's default class for what it has not seen
"<server id>" = "company"
```

Row keys: `tool`, `person`, `channel`, `audience`, `topic` (each optional, empty is unset) and
`tier` (required). Classes: `owner`, `team`, `company`, `client`, `public`. Topics:
`sensitive`, `commitment`, `disagreement`. Tiers: `send`, `ask`, `block`.

## Effective table

1. One row per `outward.modes` entry, in config order: `{ tool = "mcp__<escaped server>__.*",
   tier = <send|ask|block> }` (`draft` is `ask`, `refuse` is `block`), source `owner`, note
   `outward.modes`.
2. `outbound.tiers` rows, source `owner`.
3. The defaults, source `default`:

| n (no owner rows) | Row |
| --- | --- |
| 1 | `{ audience = "owner", tier = "send" }` |
| 2 | `{ audience = "public", tier = "block" }` |
| 3 | `{ audience = "client", topic = "commitment", tier = "block" }` |
| 4 | `{ audience = "client", topic = "disagreement", tier = "block" }` |
| 5 | `{ audience = "client", tier = "ask" }` |
| 6 | `{ topic = "sensitive", tier = "ask" }` |
| 7 | `{ topic = "commitment", tier = "ask" }` |
| 8 | `{ topic = "disagreement", tier = "ask" }` |
| 9 | `{ audience = "company", tier = "ask" }` |
| 10 | `{ tool = "other", tier = "send" }` |

Rule numbers count from 1 over the whole effective table.

## Matching (per party)

- `tool`: `re.fullmatch(row.tool, name, re.IGNORECASE)` for the tool name (MCP calls) or the
  channel kind (`slack`, `chat`, `tracker`, `code_host`, `docs`, `mail`, `other`).
- `person`: the party is a person and the value equals its id or `<namespace>:<id>`
  (casefolded).
- `channel`: the party is a channel and the value equals its id or its class (casefolded).
- `audience`: equals the party's class.
- `topic`: the text has that topic.
- Strict: a `send` row is skipped for a `client` or `public` party.

Combination over parties: any `block` decides (the lowest rule number among them), else any
`ask`, else, when every party matched a `send` row, `send`; otherwise the kind rules decide.

## Party evidence (`why`), no `; `

| Party | Evidence |
| --- | --- |
| owner identity | `<id> is the owner in outbound.owner` |
| `is_external`, `is_shared`, `is_connected` or `is_client` | `<id> is shared, connected, external or client` (class client) |
| channel in `channel_classes` | `<id> in outbound.channel_classes as <class>` |
| channel in `work_channels` | `<id> in outbound.work_channels as team` |
| channel in `external_channels` | `<id> in outbound.external_channels as client` |
| DM destination not learned (`D...`, or `is_dm`, `im`, `mpim`) | `unknown DM recipient <id>, not the owner's DM or user id in outbound.owner.slack, connector default class <c>` |
| other channel not learned | `unknown destination <id>, not in outbound.work_channels, connector default class <c>` |
| person with `class` | `<label> in outbound.people as <class>` |
| internal person | `<label> internal by outbound.company_domains or outbound.code_host_orgs as team` |
| user id destination not learned (`U...`, `W...`) | `unknown DM recipient <id>, not the owner's DM or user id in outbound.owner.slack, connector default class <c>` |
| mention, recipient or email not learned | `unknown mention <label>, not an internal person in outbound.people, connector default class <c>` |
| `recipient_org` outside `code_host_orgs` | `recipient_org <org> not in outbound.code_host_orgs as client` |
| tracker board outside `code_host_orgs` | `the board is outside outbound.code_host_orgs as client` |
| measured team pull request | `<ref> is a measured team pull request as team` |
| other pull request | `<ref> is not a measured team pull request, connector default class <c>` |
| no destination and no person | party id is the server (MCP) or the kind: `connector default class <c>` |

`<label>` is `@<id>` for a Slack or GitHub id and the address for an email, as today. `<c>`
names `outward.classes` when the class came from there: `connector default class company
(outward.classes)`.

## Reasons

Fragment: `<tier> by rule <n> (<match>) for <party id>: <evidence>`, where `<match>` is the
row's set keys other than `tier` as `key=value` joined by one space (`any` when none), and
`<evidence>` is the party's `why`, then `, outbound.<topic key>` when the row has a topic
(the config key that matched), then `, outward.modes` for a mode row.

- ask, through the guard (#493 shape, unchanged):
  `outward: draft <id>: ask by rule 7 (topic=commitment) for C1: C1 in outbound.work_channels as team, outbound.commitment_patterns; the owner decides: bin/wuwei drafts show <id> --widget`
- ask, `check_tier` and the ports: `outward: deliver as a draft for the owner to send: <fragment>`
- block (`outward.blocked`):
  `outward: block by rule 3 (audience=client topic=commitment) for C2: C2 in outbound.external_channels as client, outbound.commitment_patterns; the owner decides: bin/wuwei outbound tiers`

Kind-rule drafts keep their texts (`approval tier direct message for <audience>: every direct
message drafts`, `approval tier tracker ...`, `approval tier thread ...`, the review ping and
`approval tier unclassified ...`).

## `bin/wuwei outbound tiers`

```
rule  source   row
1     owner    { tool = "mcp__srv__.*", tier = "block" } (outward.modes)
2     owner    { person = "U07", tier = "send" }
3     default  { audience = "owner", tier = "send" }
...
12    default  { tool = "other", tier = "send" }
-     default  no row: the kind rules decide (direct messages draft, tracker.auto, docs.auto, chat threads, a measured team pull request, routine replies in a team channel)
```

Under strict an owner `send` row whose `audience` or `channel` is `client` or `public` ends with
` (ignored under strict)`. Exit 0; 2 when the config does not load. Rows render as TOML inline
tables with `json.dumps` strings, set keys only, in the order tool, person, channel, audience,
topic, tier.

## `bin/wuwei outbound explain <draft id>`

```
draft-<hex>: <stored tier_reason without the "outward: deliver as a draft for the owner to send: " prefix>
party C1: team, C1 in outbound.work_channels as team
  rule 1 owner { person = "U07", tier = "send" }: passed
  rule 2 default { audience = "owner", tier = "send" }: passed
  ...
  rule 8 default { topic = "commitment", tier = "ask" }: matched
party @u09: company, unknown mention @u09, not an internal person in outbound.people, connector default class company
  ...
now: ask by rule 8 (topic=commitment) for C1: ...
```

A skipped strict row prints `ignored under strict`. With no row deciding, the last line is
`now: no row decides; the kind rules decide`. Exit 0; 1 for an unknown id; 2 when the config
or state cannot be read.

## `doctor` (workspace section)

- `outbound classes`, `warn`: `<n> people without a class`; fix `nothing changes until you
  choose: the bin/wuwei outbound learn card asks the class of each person it adds`; one detail line per key: `<key>: team while internal by
  outbound.company_domains or outbound.code_host_orgs, else the connector default class`.
- `outbound tiers`, `warn`: one detail line per owner `send` row that can reach a `client` or
  `public` party (review F3: by audience, by a channel listed or classed client or public, by a
  person classed client or public, or with no audience, channel or person key, as tool-only and
  mode rows): `rule <n> is ignored under strict` (strict) or `rule <n> can send to a client or
  public audience` (observe, guarded). `outbound tiers` tags the same rows under strict; fix `make the row ask, or remove it`.
- Nothing to report: `ok` rows.
