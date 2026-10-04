# Contract: `bin/wuwei outbound learn`

Planner command. Refused for seats by the protect-state guard; the registered planner session
runs it, and the owner can run it in a host terminal. The hook never calls it and never calls
MCP.

## Arguments

```
bin/wuwei outbound learn --tool <mcp tool> [--as <channel>] [--channels <file>] [--people <file>]
```

- `--tool`: the tool the refusal named. Must fullmatch `mcp__[A-Za-z0-9_-]+` and contain
  `__` after the prefix. The server id is `tool[5:].rpartition('__')[0]`, compared casefolded.
- `--as`: one of `slack`, `tracker`, `code_host`, `docs`, `mail` (the
  `outward.servers` constraint). Needed only when `guards.outward.resolve(tool, config)` does
  not give exactly one channel.
- `--channels`, `--people`: listing files, Slack connectors only.

## Flow (top to bottom, first exit wins)

1. `outbound.learn = "off"`: exit 1, `outbound learn: outbound.learn is off; write the
   message as a draft for the owner to send`.
2. Invalid `--tool`: exit 1 naming the expected shape.
3. Channel = `--as`, else the single channel `resolve` gives; none: exit 1, `outbound learn:
   connector <server> has no channel; pass --as slack, tracker, code_host, docs or mail`.
4. An unanswered `outbound_learn` entry today: print that entry's widget again, exit 0 (one
   card per day batch).
5. A `keep` answer today for this server: exit 1, `outbound learn: connector <server> was
   kept as drafts today (D-n); write the message as a draft for the owner to send`.
6. Listing files with a channel other than `slack`: exit 1, `outbound learn: listings apply
   to a slack connector; run it without --channels and --people`.
7. Channel `slack` and no listing file: exit 1 and print the listing step: `outbound learn:
   connector <server> needs its listings; call its channel listing tool (channels_list,
   conversations_list or slack_search_channels) and its user listing tool (users_list or
   slack_search_users), write the channels the message goes to as [{"id", "name",
   "members", "shared"}] and the people it mentions as [{"id", "name", "email"}] in JSON
   files under today's day directory, then run bin/wuwei outbound learn --tool <tool>
   --channels <file> --people <file>`.
8. Read and validate the files (Listing files); unreadable: exit 2; invalid: exit 1 naming
   the file and the shape.
9. `card = learn == "card" or posture == "strict"`. Build the proposal (Proposal). Nothing
   new: exit 1, `outbound learn: nothing new to learn for connector <server>; write the
   message as a draft for the owner to send`.
10. `card`: write the record, route it, store the proposal, print the widget; exit 0.
    Otherwise (`"auto"` under observe or guarded): `apply(root, proposal, 'approve')`; its
    exit.

## Listing files

JSON arrays of objects with exactly these keys:

- channels: `{"id": str, "name": str, "members": int >= 0, "shared": bool}`
- people: `{"id": str, "name": str, "email": str}`

`id` fullmatches `[A-Z0-9]+`. `name` is 1 to 80 characters with no control character, `|`,
backtick, `$` or backslash. `email` is `""` or fullmatches `[^@\s]+@[^@\s]+`. Duplicate ids
are invalid.

## Proposal

From today's state `data` and `config`:

- `alias`: true when the server has no `outward.servers` entry.
- `channels`: listing rows that are not `shared`, whose id does not start with `D`, is not in
  `outbound.external_channels` and is not already in `outbound.work_channels`.
- Reviewers: the logins in today's `pr_reviewers` values, each with the organisation of its
  pull request reference (`<org>/<repo>#n`). A listed person is a reviewer when its id is the
  `mention` of a reviewer login in `shepherd.authors`, or its email (casefolded) is a
  `shepherd.authors` key or an `author_logins` key whose login is a reviewer.
- Named in a record (card only): the person's id (word-bounded) or non-empty email appears
  in today's `plan.md` or a `decisions/D-*.md` record (symlinks skipped).
- A person is proposed only when it is a reviewer, or named in a record and `card`, and has
  no `outbound.people` entry `slack:<id>` (casefolded). Its `entry` is `{"email": email}`
  when the email's domain is in `outbound.company_domains`, else `{"org": org}` when it is a
  reviewer whose pull request organisation is in `outbound.code_host_orgs`; otherwise it is
  not proposed and the command prints `not proposed: <n> people not internal by
  outbound.company_domains or outbound.code_host_orgs`.
- Nothing new: `alias` false, no channels, no people.

Shape: `{"server", "channel", "tool", "alias": bool, "channels": [{"id", "name",
"members"}], "people": [{"id", "name", "entry"}]}`.

## Decision record (written with `decision.write`, then `decision.route_owner`)

`<Label>` is `Slack` for `slack`, else the channel name. The question names only the
non-empty parts: `Connector <server> is <Label>; add <n> work channel(s) and <m> people?`
(`1 work channel`, `2 work channels`, `1 person`, `2 people`); with neither, `Connector
<server> is <Label>?`.

```
Question: <question>
Class: other
Context: Proposed by bin/wuwei outbound learn from the planner's listing of connector <server> for tool <tool>.
- channel #<name> (<id>, <members> members)
- person <name> (<id>, <why>)
Options:
| Option | Title | Rationale | Consequence |
| --- | --- | --- | --- |
| approve | Approve | Records the alias, <n> work channels and <m> people. | Routine sends to these channels that mention these people go out under the outbound tier; the rest stay drafts. |
| channels | Approve channels only | Records the alias and <n> work channels. | Mentions of these people still draft. |
| keep | Defer: keep as drafts | Records nothing. | Every send through this connector stays a draft today. |
Musts:
| Criterion | approve | channels | keep |
| --- | --- | --- | --- |
| Only listed channels and reviewed or recorded people | pass | pass | pass |
Wants:
| Criterion | Weight | approve | channels | keep |
| --- | --- | --- | --- | --- |
| Sends without typing config | 10 | 9 | 5 | 1 |
Recommendation: approve
Reasoning: The listing names these channels and the people are the day's reviewers or named in its records; keep drafts if a channel is shared outside the company.
Confidence: medium
Reversibility: two-way
Blast radius: Outbound policy for connector <server>.
Pre-mortem: A listed channel is shared with another company and a routine send reaches it.
Revisit: Reopen if a send reaches the wrong audience.
Decided-by: owner
Outcome: pending
```

`<why>` is `reviewer` or `named in today's records`. One `- channel` line per proposed
channel and one `- person` line per proposed person.

The widget is `decision.record_widget(D-n, fields, level=workspace.verbosity(config,
'decisions'))`, printed as `json.dumps([widget], indent=2)` like `decision show --widget`.
Its `record` is `wuwei decide D-n "<label>"`.

## State

`outbound_learn` (reserved; producers `wuwei outbound learn` and `wuwei decide`):
`{"D-n": {<proposal>, "answered": null | "approve" | "channels" | "keep"}}`, written with
event kind `outbound.proposed` (`{"id", "server", "channel"}`).

## Apply

| option | `outward.servers.<server>` | `outbound.work_channels` | `outbound.people."slack:<id>"` |
|---|---|---|---|
| `approve` | when `alias` | effective list plus the channel ids | each person's `entry` |
| `channels` | when `alias` | effective list plus the channel ids | none |
| `keep` | none | none | none |

Written through `setup._edit` with an always-yes confirm (the answer is the confirmation),
settings built in its change callback from `load_config(root, raw=raw)` with
`setup.merged`. After a write, one event:

`outbound.learned` (reserved): `{"decision": "D-n" | null, "option", "mode": "card" |
"auto", "server", "channel", "alias": bool, "channels": [ids], "people": [ids]}`. Ids only;
no names or emails.
