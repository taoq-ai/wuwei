# Security integration

## Current controls

Hooks invoke the CLI for relevant actions. Guard scope is a WUWEI workspace, its configured repositories and their worktrees. Outside that scope, every hook returns 0 before any guard reads the call. A command that names a workspace path literally is in scope. Malformed input to a relevant call blocks it with exit 2 and a reason. CLI state and events have dedicated writers, and the outward policy limits text-bearing adapter calls.

One switch sets how the guards act: `guards.enforce`. It is true by default. With it false, a guard logs `guard.would_refuse` and lets the call through. `init --shadow` starts a new workspace that way for a first week. The records and the irreversible edges below hold either way.

## ZIRAN integration

The ZIRAN scanner adapter provides runtime trace analysis (S2) and agent-surface gates (S4). An item whose diff changes prompts, tool definitions, agent tool permissions or MCP config is flagged `agent_surface`. Its security gate reads the scanner findings in the files the item changed. The morning discovery audits each configured repository once per HEAD per day and lists its findings as candidates, with paths relative to the repository: at or above `scanner.discovery_threshold`, most severe first, at most `scanner.discovery_rows` per repository. Do not treat an unavailable scanner as a clean audit. With `adapters.scanner = "none"`, the default, trace and agent-surface checks report unmeasured, never clean. WUWEI does not watch attached MCP servers for tool drift, and it declares no MCP server of its own.

`dispatch receive` and `close` run the trace sweep. It gives `ziran analyze-traces` only the spans recorded since the last measured sweep (`trace-sweep.json` in the day directory), at most 20 spans of one session per call, each call starting with the last earlier span of every tool its sessions used, so a chain split by a sweep still forms. A critical chain of an item seat parks its items and pages; a seat the owner resumed parks again on that chain only when its first and last tools both ran again. When ZIRAN fails or times out, the sweep keeps its offset, retries at the next receive or close, appends one `scanner.unmeasured` event per reason, and `bin/wuwei doctor` shows an unmeasured `trace sweep` row until a sweep is measured again.

To switch the scanner off, run `bin/wuwei config set adapters.scanner '"none"'`. From a registered planner session it asks one Owner step card; the next run applies it. Discovery then lists no scanner candidates, and trace and agent-surface checks report unmeasured. Set it back to `"ziran"` the same way.

## S1: Reviewed role grants in CI

Pull requests and pushes to main run `taoq-ai/ziran@v0.41.0` in audit mode with
`ziran==0.41.0`, high severity and `agents/ziran-baseline.json`. ZIRAN reads the
Claude Code agents directly. The recorded baseline is the reviewed proposal of
tool grants and dangerous chains. Existing grants pass. Widened tools or chains and
new critical findings fail. For example, adding WebFetch to the builder fails with a
finding naming the chain it creates. Both findings (exit 1) and an audit that could
not run (exit 2) fail CI. The action uploads SARIF to code scanning when permissions
allow; an upload failure does not change the audit result.

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
pytest checks baseline and allowlist consistency offline. Real clean and widened
audits run when ZIRAN is on PATH, including in the audit job. See the
[agent maintenance instructions](https://github.com/taoq-ai/wuwei/blob/main/docs/charters.md)
for installation and regeneration details.

## The irreversible edges

The Bash guards match exact argv on the irreversible edges only:

- a merge (`gh pr merge` or a merge API write), an approval, `--admin` and branch protection writes;
- a force push (`--force`, `-f`, `--mirror` or a `+` refspec) and a push to a default branch;
- a deploy;
- a `gh pr create` for a recorded item.

Each refusal names the way through. That is `bin/wuwei merge <pr>`, a new commit pushed with `git push origin HEAD:refs/heads/<branch>`, `bin/wuwei pr raise ... --item <item>`, or the deploy's Owner step card. On your Yes the same command runs again.

The guards split a call with `shlex` at `;`, `&&`, `||`, `|`, parentheses and newlines. They unwrap leading assignments, `env` and `sh -c`, and skip here-doc bodies, so text written to a file is never a command. A call they cannot split is recorded as `unparsed` and runs. Scripts, interpreter code, aliases and names built at run time are not read. The code host's protected branches and the credential layout hold those.

Records are the one floor. State, events, config, verdicts and traces are written by the CLI, and a state write the guards can read stays refused. A top-level `cd`, `pushd` or `popd` that may leave the workspace is recorded. Run it in a subshell, `(cd <dir> && <command>)`, or use `git -C <dir>`.

## Outward sends

An MCP write to other people goes out only when that exact tool is on `outward.allow`. Any other write is refused, naming `bin/wuwei config set outward.allow '["<tool>"]' --add`, which asks your Owner step card. A tool whose name starts with a read verb (get, list, search, read, find, fetch, query, describe, view, lookup) is a read and passes.

Your own surfaces are local. A call whose every destination is [your own surface](configuration.md) passes without the third-person rules and records a silent `outward.to_owner` event. Local servers act only on your machine: `terminal`, `Claude_Preview`, `Claude_Code_iOS_Simulator`, `computer-use` and the `Claude_Browser` preview tools. Their calls pass the outward guard. A `run_in_terminal` command is judged by the Bash guards as the same command through Bash. The canary and honeytoken egress check runs on every outward send.

## Telemetry: what leaves

Nothing leaves the machine unless `telemetry.share` is `"anonymous"` or `"attributed"`. Empty (not asked yet) and `"off"` send nothing. Then only a final week's payload leaves: the schema, the ISO week, the plugin, Python and OS versions, the guard mode, profile, adapter names, the number of repositories and the weekly counts. Every key and value is checked against a fixed vocabulary before it is sent. No repository, item, ticket, pull request, person, handle, path, branch, command, reason text or time finer than the week can leave. A payload that breaks a rule is not sent. `bin/wuwei telemetry preview` prints exactly what each mode would send.

- Anonymous: `wuwei report` posts the payload over HTTPS with a random workspace id kept in `.wuwei/metrics/token`, the only identifier. No account and no secret are involved. The collector, like any web server, sees your IP address and does not store it.
- Attributed: `bin/wuwei telemetry send` asks your Owner step card, runs the canary and honeytoken check, and opens the issue from your gh account, so it shows your login. The token is never in it.

`bin/wuwei telemetry off` stops sharing at once. The aggregate, `.wuwei/metrics/`, is a protected record only the CLI writes. Your own OpenTelemetry export (`[telemetry.otlp]`) goes only to the endpoint you set.

## Threat model 9.1

The guards address agent mistakes, corner cutting and prompt injections sent through normal tools. They are cooperative mistake prevention, not an isolation boundary. No hook, Claude Code or git, is a hard boundary against a process running as you. Such a process can edit local files, including state, events and approval records.

The hard boundaries are elsewhere. Code host rules (protected refs, required checks, required reviews) guarantee push and merge. Publication credentials kept out of seat environments guard approval and deploy. The exact `outward.allow` list you approve bounds outward sends. WUWEI must never bypass branch protection, approve its own pull requests or deploy without your answer. Codex seats can be isolated in a write sandbox limited to their worktree. More hardening for Claude seats is **planned**.

The signed manifest, workspace integrity checks, the prompt canary and the honeytoken are current controls. They make tampering evident (spec 7.1). They do not make it impossible, because a process running as you can still edit local files (9.1). See [integrity](integrity.md) for how they are checked and the [design spec](https://github.com/taoq-ai/wuwei/blob/main/docs/specs/2026-09-24-wuwei-design.md) for the full model.
