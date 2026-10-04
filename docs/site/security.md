# Security integration

## Current controls

Hooks invoke the CLI for relevant actions. Guard scope is a WUWEI workspace, its configured repositories and worktrees. Outside that scope, every hook returns 0 before any guard reads or parses the call; a command that names a workspace path literally is in scope. Relevance is checked before parsing; malformed input blocks a relevant call with exit 2 and a reason. CLI state and events use dedicated writers, and the outward policy limits text-bearing adapter calls. With `adapters.scanner = "none"` the MCP registry gate is off and says `not measured`, never clean; trace and agent-surface checks report unmeasured.

## ZIRAN integration

The ZIRAN scanner adapter provides runtime trace analysis, MCP registry checks and agent-surface gates. Init and upgrade register attached MCP configurations; morning planning checks for drift before any seat launches. The check starts only servers Claude Code would attach, approved and pinned, one at a time through ZIRAN; it never starts an unapproved project server or a `uvx`, `npx` or `pipx run` launcher without an exact version, and reports those by name. High/critical findings require your decision on the host. The security posture decides what blocks. Under `observe` and `guarded` (the default) every finding warns: it is recorded, shown in the plan sweep, on the board and in what the planner relays, with `bin/wuwei mcp decide D-<n> proceed`, and launches proceed. `strict` blocks critical, high and unmeasured until `bin/wuwei mcp decide D-<n> proceed`. A check that could not run blocks under `guarded` and `strict`. `scanner.mcp.block` overrides the posture default. Snapshots and accepted decisions are protected producer records, and raw descriptions stay in report files; the decision carries only a redacted snippet of at most 60 plain characters per finding. See [configuration](configuration.md) for discovery paths and the decision flow. Do not treat an unavailable scanner as a clean audit. With `adapters.scanner = "none"`, the default, the registry gate is off: `init`, `setup`, `mcp check`, `plan propose` and the launch gate exit 0, and the first check of the day with attached servers prints `mcp: not measured (no scanner configured; set adapters.scanner = "ziran" to measure)`. That gives up drift and tool-poisoning detection on every attached server. A configured scanner that cannot start (not on PATH, wrong version) is a check that could not run and blocks launches under `guarded` and `strict`. WUWEI's own board MCP server is declared in the signed `.claude-plugin/plugin.json`, so plugin integrity covers it and the registry gate (`bin/wuwei mcp check`) reports it as covered rather than scanning it; every other server, including one declared inline in another plugin's `plugin.json`, is measured.

## S1: Reviewed role grants in CI

Pull requests and pushes to main run `taoq-ai/ziran@v0.41.0` in audit mode with
`ziran==0.41.0`, high severity and `agents/ziran-baseline.json`. ZIRAN reads the
Claude Code agents directly. The recorded baseline is the reviewed proposal of
tool grants and dangerous chains; no WUWEI converter or runtime dependency is
needed. Existing grants pass, while widened tools/chains and new critical
findings fail. For example, adding WebFetch to the builder fails with a finding
naming the chain it creates. Both findings (exit 1) and an audit that could not
run (exit 2) fail CI. The action uploads SARIF to code scanning when
permissions allow; an upload failure does not change the audit result.

After a reviewed charter or allowlist change, use ZIRAN 0.41.0 in a disposable
dev environment. From the plugin repository root, outside an initialized WUWEI
workspace, run:

```sh
bin/wuwei agents build
ziran audit agents/ --write-baseline agents/ziran-baseline.json
ziran audit agents/ --baseline agents/ziran-baseline.json --format json
```

Review and commit the generated agents and baseline together with their source
changes. Do not re-record an unreviewed widening just to make CI green. Default
pytest checks baseline/allowlist consistency offline; real clean and widened
audits run when ZIRAN is on PATH, including in the audit job. See the
[agent maintenance instructions](https://github.com/taoq-ai/wuwei/blob/main/agents/README.md)
for installation and regeneration details.

## Security posture

`security.posture` says what warns and what blocks, by where the plugin runs and for what purpose. Each area has a level: `off` (not checked; a refusal is dropped and not recorded), `warn` (recorded as `guard.would_refuse` and let through) or `block` (refused, as before). `[security.areas]` overrides one area, for example `mcp = "off"`. `bin/wuwei config check` prints the effective table and the key it comes from.

| Area | What it covers | observe | guarded (default) | strict |
| --- | --- | --- | --- | --- |
| `records` | State, events, config, generated instructions, verdicts, decisions, traces, session records (`protect_state`, `decision`, `verdict`, `traces`, `lifecycle`) | block | block | block |
| `publish` | Commit and push rules, the owned-PR anchor and day close (`commit_push`, `stop`); deploys and PR actions (`deploy`, `pr`) | warn | block | block |
| `integrity` | The plugin integrity gate (`integrity`) | warn | block | block |
| `mcp` | The MCP registry launch gate | warn | warn | block |
| `outward` | The outward text lint (`outward`) and the question citation check (`decision.check_question`) | warn | warn | block |
| `seats` | The seat launch contract: logged brief, capacity, memory, clean worktree (`agent_launch`) | warn | warn | block |

Floors no posture and no override lowers:

- `records` always blocks. An override below `block` is a `config check` finding (exit 1), and every hook then fails closed as for any broken config.
- Owner-only actions always block: the deployment ban (`deploy`), the merge policy, approvals and owner markers (`pr`), and approve-tier messages and canary or honeytoken egress (the outward approval tier). Under `observe`, `publish` relaxes only the commit and push rules and the PR anchor.
- MCP: under `guarded` and `strict` a registry check that could not run blocks launches whatever `security.areas.mcp` says, unless it is `off` or `adapters.scanner = "none"`. A finding blocks only at a severity in `scanner.mcp.block`, which is unset by default: no severity under `guarded`; `critical`, `high` and `unmeasured` under `strict`. Under `observe`, and with `mcp = "off"`, the list has no effect and `config check` says so.

Runtime trace chains (S2) page and ask you only for seats. The planner, its subagents and other registered sessions (shepherd, remote, seat-host) get one silent `traces.noted` event per session per day. A session the registry does not know gets one `traces.unmatched` event per day, and under `strict` one owner decision per session per day. `setup --shadow` and `init --shadow` write `observe`.

A command a Bash guard finds relevant but cannot parse (a loop, a command substitution, inline interpreter code) that names no publishing tool and writes no record is `unparsed`: it warns under `observe` and `guarded` and blocks only under `strict`, and the reason gives the one accepted form, `write the commands to a file with the Write tool and run bash <file>`. A command whose words are all read-only (`ls`, `cat`, `echo`, `grep`, `head`, `tail`, `sed -n`, `wc`, `jq`, `diff`, `find`) passes. A git subcommand that is neither a known read (`status`, `log`, `diff`, `show`, `grep`, `blame` and the rest) nor a known write (`push`, `commit`, `merge`, `add` and the rest) is an unknown git subcommand: it warns under `observe` and `guarded`, naming the subcommand, and blocks only under `strict`. With a `-c`, `--git-dir`, `--work-tree` or `GIT_*` override it stays refused, because the override can define an alias. The plugin's own read-only subcommands (`status`, `why`, `doctor`, `config check`, `mcp check`, `integrity check`, `shadow report`, `board`, `sessions`, `heartbeat`, `calibrate --questions`) and any `--help` pass too, through the recorded executable, the plugin's `bin/wuwei` or `wuwei` on PATH. A command that names a publishing tool keeps the floors above. A top-level `cd`, `pushd` or `popd` that may leave the workspace warns in every posture; run it in a subshell, `(cd <dir> && <command>)`, or use `git -C <dir>`.

An MCP tool's channel comes from, in order: your alias for its server (`outward.servers`), the `outward.tool_patterns` rules (the built-in ones match the brand anywhere in the name), then a small tool vocabulary when exactly one channel fits (`conversations_*`, `chat_post*`, `add_message` and `add_reaction` are Slack; an `issue` word is the tracker; `draft`, `label`, `thread`, `spam`, `trash`, `forward`, `inbox` or `mail` is mail; `page`, `block` or `database` is docs; a `pull_request` with a `comment` is the code host; resolving, muting or triggering an issue, alert or incident, or an alert rule, is `other`). Words split on camelCase too, so `addCommentToJiraIssue` is the tracker. A write through a server with a mode in `outward.modes` follows it (`send`, `draft` or `refuse`); an `other` write without one sends after the lint and the sensitive, commitment and disagreement patterns. The alias and the vocabulary are skipped for reads. A tool nothing resolves is sorted by the words of its name. It is a read when its name starts with get, list, search, read, find, fetch, query, describe, view or lookup, or when it has a read word (such as `history`, `replies`, `info` or `channels`) and no write verb; it is a write when it has a write verb (such as `send`, `add`, `create` or `message`); otherwise it is unknown. Reads pass. A write is refused in every posture, and an unknown tool passes under `observe` and `guarded` with one `outward.unknown_tool` nudge per tool per day and is refused under `strict` (the `outward` area); both reasons name the connector, ask for a draft and name `bin/wuwei outbound learn --tool <tool>` (only the draft under `outbound.learn = "off"`). A resolved write the approval tier holds back is stored as a draft, and the refusal names its id and the rule that held it. You decide, on the card `bin/wuwei drafts show <id> --widget`; an approved draft from a connector lets the seat's same tool call through once. When the rule is an unknown destination or mention, the card also names `bin/wuwei outbound learn --tool <tool>` (not under `outbound.learn = "off"`). A message only you receive (your DM or user id in `outbound.owner`, or a mail whose only recipient is you) passes the lint and goes under every posture with a silent `outward.to_owner` event; a DM to anyone else is held with `unknown DM recipient <id>`.

`bin/wuwei outbound learn` runs in the registered planner session (seats are refused). The planner calls the connector's channel and user listing tools, saves the channels the message goes to and the people it mentions as JSON files under today's day directory, and runs it with `--channels` and `--people`. It proposes the server alias, the listed channels that are not shared, external or direct messages, and the listed people who review today's pull requests (or, on the card only, are named in today's plan or decision records) and are internal by `outbound.company_domains` or `outbound.code_host_orgs`. Under `outbound.learn = "card"` it writes one decision record and prints its card; the card states the connector's class and mode, and your answer (`Approve`, `Approve channels only`, `Defer: keep as drafts`, or `Approve, mode <mode>` to change the mode) writes the config and records `outbound.learned`. Guard settings (`outward`, `outbound`, `security`, `grants`) never change from an agent tool: `config set` on them is refused with a reason that names `outbound learn`. While your own Slack identity is not recorded, the listing step also names the connector's identity tool (`auth_test`, `users_me` or `whoami`); with `--owner <file>` holding `{"user", "dm"}` the card also proposes `outbound.owner.slack`, and an identity always goes through the card, also under `outbound.learn = "auto"`. The draft card of a DM held as `unknown DM recipient` names that command while the identity is missing. A message to your own DM sends under every posture and even when the connector's mode is `draft` or `refuse`.

Where to run each:

- `observe`: a first week on a project, or a personal sandbox. You see what the guards would stop in your own habits before they stop anything; the records stay trustworthy. `setup --shadow` starts here; after `guards.shadow_days` days one nudge asks you to switch to `guarded`.
- `guarded`: a real project. Records, publishing and integrity block; seat launches, outward text and MCP findings warn, and each warning is a status nudge.
- `strict`: a repository that deploys, or a workspace that holds shared credentials. Everything blocks.

The posture changes only what the cooperative guards refuse. The hard boundaries below (host rules, the credential layout, owner-sent messages) hold in every posture. `config.toml` is a record, so a seat cannot lower its own posture.

## Telemetry: what leaves

Nothing leaves the machine unless `telemetry.share` is `"anonymous"` or `"attributed"`; empty (not asked yet) and `"off"` send nothing. Then only a final week's payload leaves: the schema, the ISO week, the plugin, Python and OS versions, the posture, profile, adapter names and the number of repositories, and the weekly counts. Every key and value is checked against a fixed vocabulary before it is sent, so no repository, item, ticket, pull request, person, handle, path, branch, command, reason text or time finer than the week can leave; a payload that breaks a rule is not sent. `bin/wuwei telemetry preview` prints exactly what each mode would send.

- Anonymous: the watch posts the payload over HTTPS with a random workspace id kept in `.wuwei/metrics/token`, the only identifier. No account and no secret are involved. The collector, like any web server, sees your IP address and does not store it.
- Attributed: you run `bin/wuwei telemetry send` in a host terminal; it shows the issue, asks y/N, runs the canary and honeytoken check, and opens it from your gh account, so it shows your login. The token is never in it.

`bin/wuwei telemetry off` stops sharing at once without a confirmation. The aggregate, `.wuwei/metrics/`, is a protected record only the CLI writes. Your own OpenTelemetry export (`[telemetry.otlp]`) goes only to the endpoint you set and never to the project.

## Threat model 9.1

The guards address agent mistakes, corner cutting and prompt injections sent through normal tools. They are cooperative mistake prevention, not an isolation boundary: no hook, Claude Code or git, is a hard boundary against a process running as you. Such a process can edit local files, including state, events and approval records. Hard boundaries are code host server-side rules (protected refs, required checks, required reviews), publication credentials kept out of seat environments, owner-sent approve-tier messages, and, when built, an external control plane. For push, merge, deploy and PR approval the guards refuse what they recognise; push and merge are guaranteed by the host rules (protected refs, and a merge lands only through required checks and reviews), and approval and deploy by the credential layout. WUWEI must never bypass branch protection, approve its own pull requests or deploy. Codex seats can be isolated in a write sandbox limited to their worktree. More hardening for Claude seats is **planned**.

The signed manifest, workspace integrity checks, the prompt canary and the honeytoken are current controls. They make tampering evident (spec 7.1); they do not make it impossible, because a process running as you can still edit local files (9.1). See [integrity](integrity.md) for how they are checked and the [design spec](https://github.com/taoq-ai/wuwei/blob/main/docs/specs/2026-09-24-wuwei-design.md) for the full model.
