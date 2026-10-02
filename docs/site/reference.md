---
layout: default
---

# Operator data reference

Use `bin/wuwei` from the installed checkout, or `python3 -P -m wuwei` with the package on `PYTHONPATH`. The `-P` option keeps a local `wuwei/` directory from shadowing the CLI.

## Commands

Every command `bin/wuwei --help` prints; `bin/wuwei <command> --help` shows its options. Commands marked plumbing are called by hooks, seats or the plugin, not by the owner.

| Command | What it does | More |
| --- | --- | --- |
| `bin/wuwei agents` | Builds or checks the generated role agents. | [Concepts](concepts.html#roles) |
| `bin/wuwei board` | Plumbing: serves the day board to Claude Code over MCP stdio. | [Cockpit and board](concepts.html#cockpit-and-board) |
| `bin/wuwei brief` | Writes and logs a seat brief. | [Seat briefs](#seat-briefs-and-the-build-loop) |
| `bin/wuwei build` | Selects the next builder action. | [Seat briefs](#seat-briefs-and-the-build-loop) |
| `bin/wuwei calibrate` | Profiles the repositories and proposes config; `--interview` asks the owner. | [Calibration](configuration.html#calibration) |
| `bin/wuwei close` | Refuses day close until every obligation lands. | [Day close](concepts.html#day-close) |
| `bin/wuwei config` | Inspects workspace configuration (`check`, `promote`). | [Configuration](configuration.html) |
| `bin/wuwei consolidate` | Reviews and archives workspace memory. | [Configuration](configuration.html#host-build-and-memory) |
| `bin/wuwei dashboard` | Serves the read-only day board on loopback. | [Cockpit and board](concepts.html#cockpit-and-board) |
| `bin/wuwei decision` | Checks and routes decision records; `outcome` records the owner's answer. | [Decision record](#decision-record) |
| `bin/wuwei discover` | Discovers candidate work. | [Goals and discovery](configuration.html#goals-and-discovery) |
| `bin/wuwei dispatch` | Decides planner gate and discovery work. | [Review tiers](concepts.html#review-tiers) |
| `bin/wuwei drafts` | Lists outward drafts awaiting owner approval. | [Outward draft queue](#outward-draft-queue) |
| `bin/wuwei event` | Plumbing: appends a timestamped day event. | |
| `bin/wuwei fast-checks` | Runs and records the configured fast checks. | [Seat briefs](#seat-briefs-and-the-build-loop) |
| `bin/wuwei git-hook` | Plumbing: runs a native Git identity or push guard. | [Item worktrees](#item-worktrees) |
| `bin/wuwei goals` | Shows or edits the owner goals. | [Goals and discovery](configuration.html#goals-and-discovery) |
| `bin/wuwei heartbeat` | Probes that hooks refuse, allow and answer in budget. | [Heartbeat](#heartbeat) |
| `bin/wuwei hook` | Plumbing: runs the guards for a Claude Code hook. | [Hook latency budget](#hook-latency-budget) |
| `bin/wuwei index` | Generates the memory index. | [Concepts](concepts.html#memory) |
| `bin/wuwei init` | Creates or upgrades a workspace; `--shadow` starts the guards in [shadow mode](#shadow-mode). | [Daily path](daily.html) |
| `bin/wuwei integrity` | Checks signed plugin integrity; `reconfirm` pins a development checkout. | [Recovery](recovery.html#integrity-reconfirm) |
| `bin/wuwei listen` | Polls the inbound source into the workspace inbox and probes raised and claimed PRs. | [Remote](remote.html) |
| `bin/wuwei mcp` | Checks the attached MCP servers; `decide` records the owner's answer. | [MCP registry checks](configuration.html#mcp-registry-checks-s3) |
| `bin/wuwei memory` | Checks workspace memory. | [Concepts](concepts.html#memory) |
| `bin/wuwei merge` | Checks or merges an eligible PR. | [Retro and merge](#retro-and-merge-configuration) |
| `bin/wuwei metrics` | Shows the recorded process metrics. | [Long sessions](daily.html#long-sessions) |
| `bin/wuwei note` | Manages workspace notes. | [Concepts](concepts.html#memory) |
| `bin/wuwei nudges` | Lists open nudges and pages. | [Watch state](#watch-state) |
| `bin/wuwei outbound` | Inspects the outbound approval policy. | [Outbound tiers](configuration.html#outward-text-and-outbound-tiers) |
| `bin/wuwei payload` | Plumbing: prints the session memory payload. | |
| `bin/wuwei plan` | Proposes or approves the morning plan; `session` names the planner. | [Lead plan JSON](#lead-plan-json) |
| `bin/wuwei pr` | Measures owned PRs, raises one, or records a verified disposition. | [Raising a PR](#raising-a-pr) |
| `bin/wuwei promote` | Promotes memory and charter proposals. | [Charter overrides](charter-overrides.html) |
| `bin/wuwei rank` | Ranks candidate JSON using the workspace goals. | [Lead plan JSON](#lead-plan-json) |
| `bin/wuwei remote` | Owner actions for the remote control plane. | [Remote](remote.html) |
| `bin/wuwei reply` | Replies to one unthreaded human obligation. | [Outward draft queue](#outward-draft-queue) |
| `bin/wuwei report` | Shows the owner report. | [Day close](concepts.html#day-close) |
| `bin/wuwei shadow` | `report` lists what the guards would have refused since `guards.shadow_since`, grouped by guard, and names likely false positives. | [Shadow mode](concepts.html#shadow-mode) |
| `bin/wuwei retro` | Compiles the steward retro. | [Retro and merge](#retro-and-merge-configuration) |
| `bin/wuwei runtime` | Dispatches and inspects runtime jobs. | [Recovery](recovery.html#runtime-dispatch) |
| `bin/wuwei sessions` | Lists registered sessions, roles and claims. | [Sessions](#sessions) |
| `bin/wuwei signal` | Classifies attention. | |
| `bin/wuwei state` | Reads or updates day state; `recover` restores it. | [State recovery](#state-recovery) |
| `bin/wuwei status` | Shows day status; `--line` is the status line. | [Watch state](#watch-state) |
| `bin/wuwei steward` | Runs a steward review or acknowledges steering. | [Steward](#steward) |
| `bin/wuwei sweep` | Checks day obligations. | [Concepts](concepts.html#day-flow) |
| `bin/wuwei verdict` | Checks a gate verdict. | [Gate verdict layout](#gate-verdict-layout) |
| `bin/wuwei voice` | Shows or edits the owner voice profile. | [Owner voice](configuration.html#owner-voice) |
| `bin/wuwei watch` | Supervises workspace activity and owned PRs. | [Running the watch](configuration.html#running-the-watch) |
| `bin/wuwei worktree` | Creates an anchored item worktree. | [Item worktrees](#item-worktrees) |

## Lead plan JSON

Run `bin/wuwei plan template` in a workspace for a complete lead JSON skeleton. `bin/wuwei plan template | bin/wuwei plan propose -` creates today's proposal. Replace sample evidence before approval. The top-level keys are:

| Key | Content |
| --- | --- |
| `goals` | Nonempty list of `G-n` identifiers in `.wuwei/memory/goals.md`. |
| `candidates` | List of candidate objects described below. |
| `seat_policy` | Role to `{ "runtime": "claude", "model": "sonnet" }` mapping. |
| `envelope` | `start`, `end`, and nonnegative `net_build_hours`. |
| `sweep` | Source to measured or unmeasured status string. |
| `cap` | Positive running build seat count, within `host.seats`. |

Each candidate needs a unique `id`, a confirmed `goal` or `unplanned`, `evidence`, `scope`, `overlap`, `track`, `flags`, `score`, and `evidence_lines`. `track` is `SLICE` for a small change with one pre-PR gate set, or `FULL` when a spec-done gate is needed. `flags` has exactly three booleans: `trust_surface`, `boundary_relevant`, and `agent_surface`. These affect owner routing and security gates. An optional `tier` (`light`, `standard` or `full`) raises the review tier `wuwei dispatch next` computes from the diff; a lower one is refused and recorded as a reason. `evidence_lines` has a nonempty one-line citation for every score component.

`bin/wuwei rank template` prints a candidate list for the configured framework. Pass it to `bin/wuwei rank -` to inspect the order. Ties use goal priority, then candidate id.

`bin/wuwei rank FILE` (or `-` for stdin) also accepts a whole lead JSON, such as `bin/wuwei plan template` output or today's `.wuwei/days/<date>/proposal.json`, and ranks its `candidates`. An object without a `candidates` list exits 2 with `candidates must be a list`.

### WSJF and RICE

For `prioritisation.framework = "wsjf"`, `score` contains `value`, `time_criticality`, `risk_reduction`, and `job_size`. Each uses the Fibonacci scale 1, 2, 3, 5, 8, 13, 20. WSJF is `(value + time_criticality + risk_reduction) / job_size`.

For `prioritisation.framework = "rice"`, use `reach` (positive people or systems), `impact` (0.25, 0.5, 1, 2, 3), `confidence` (0.5, 0.8, 1), and `effort` (positive seat-days). RICE is `reach * impact * confidence / effort`.

## Decision record

`bin/wuwei decision template` prints a record that passes `bin/wuwei decision lint FILE`. Save it as `.wuwei/days/<date>/decisions/D-<n>.md`. Include `Question:`, `Context:` with evidence paths, and an `Options:` table with at least two choices including deferral. A `Musts:` table marks pass/fail for each option. A `Wants:` table gives each criterion a weight from 1 to 10 and each option a score from 0 to 10. `Recommendation:` names the highest scoring option that passes every must. Complete `Confidence: high|medium|low`, `Reversibility: one-way|two-way`, `Blast radius:`, `Pre-mortem:`, `Revisit:`, `Decided-by: seat|owner`, and `Outcome:`. `bin/wuwei decision show D-<n>` prints a valid record at the `owner.verbosity.decisions` level (exit 1 for an invalid record, 2 for one it cannot read), and `--full` prints every field. A valid record whose text carries tells from the writing checklist lints with an extra `style:` line and still exits 0. Route an existing record with `bin/wuwei decision route D-<n>`. For a confirmation from a person outside the loop, run `bin/wuwei decision route D-n --external <item>`: the record goes to the owner whatever its reversibility, the item records `assumption: {kind: external, decision, day, since, status: waiting}` and its reversible work continues. After `decisions.wait_hours` weekday hours in `owner.timezone` without an owner answer, the watch sweep confirms the recommendation on a two-way door (`status: confirmed`; the record stays pending) or parks the item with the record as its decision (`status: parked`); either writes a `decision.waited` event, and your `decision outcome` resumes a parked item. `bin/wuwei pr act` routes the decisions it creates, and a routed decision without an owner outcome shows in `bin/wuwei nudges` and the status line.

## Retro and merge configuration

Every seat ends with three retro note keys on separate lines: `Blocked:`, `Gap:`, and `Change:`. Use `none` if a line has no finding. In `.wuwei/config.toml`, `[retro]` sets `repo` (default `"."`), `charter_paths` (default `[".wuwei/charters"]`), and `changelog` (default `".wuwei/memory/CHANGELOG.md"`).

In a `[[repos]]` entry, `[repos.merge]` sets `merge.auto` (default `false`). Automatic merge remains subject to measured policy, review, checks, soak and path rules. Set `repos.merge_deploys` correctly; WUWEI never deploys.

## Steward

`bin/wuwei steward run --trigger sweep|close|tool-calls` writes a steward brief, launches the steward seat through the runtime adapter, records a `steward.run` event and prints `steward_launch`; launch that agent exactly as returned. `bin/wuwei close` runs the close review once a day. A second `--trigger close` run the same day writes no brief, launches nothing and prints `steward: close review already ran today (brief <path>)`.

`bin/wuwei steward ack <id>` acknowledges a steward steering note. The id has the form `<item>-fix-3` (a third fix round) or `<item>-question-<agent>` (a seat stopped on a question to the owner without a decision record, written by the SubagentStop guard) and is named, with the note text, by the refusal `steward note <id> requires planner acknowledgement: <text>` from `dispatch next`. A `steward.due` nudge is not a note and takes no ack: it clears when `steward run` records a run.

Every steward review (on the sweep, at close and on each `dispatch next`) also counts, per item over the last `steward.loop_window_hours`, the decision and clarification records naming it on their `Question:` or `Context:` line, `gate.received` verdicts, repeated briefs for the same role and `build.fix_opened` fix requests. Above `steward.loop_threshold`, or on a second fix round today, it writes one `negotiation.loop` event per item per day with the counts and the last two exchanges: a nudge, or a page when the item's goal date has passed. The listener sends its summary to the owner DM once and records `negotiation.notified`; the status line shows `loops N`. The signal reports; it never parks or blocks.

## Codex companion protocol

Configure `codex.command` as an argv list and `codex.timeout_seconds` in `.wuwei/config.toml`. The adapter invokes `task`, `status`, `result`, and `cancel` with `--json` in the worktree. `task --fresh --background` starts a job and returns `jobId`; continuation uses `task --resume-last --background --write`. `status JOB_ID` returns `workspaceRoot` and a `job` with its own `workspaceRoot` and status. Both roots must resolve to the requested worktree. `result JOB_ID` supplies text in `storedJob.result.rawOutput`, with companion stdout or rendered text as fallback. A root mismatch triggers `cancel JOB_ID`. Missing fields, an error body or a timeout is unmeasured and fails closed.

## Outward draft queue

Approve-tier replies through the chat, code-host comment and tracker-create adapters are stored in today's producer-owned `drafts` state. The call returns exit 1 with the draft ID and sends nothing. Policy or security errors still fail closed. Ordinary adapter calls never treat a saved owner decision as permission to send.

| Command | Effect |
| --- | --- |
| `bin/wuwei drafts` | List today's pending drafts with text, destination, audience and tier reason. |
| `bin/wuwei drafts approve <id>` | Run security, outward and voice lint, then send the stored text once through its original adapter operation. |
| `bin/wuwei drafts approve <id> --edit` | Edit with `EDITOR` (default `vi`), lint the final text, then send it. |
| `bin/wuwei drafts drop <id>` | Close the draft without sending. |

Approval and drop are owner actions on the host terminal. Approval shows the destination and final text and asks you to type a digest of them before it sends. Agent tool hooks refuse both, including registered seats. The cockpit displays pending drafts and the approval command read-only; it accepts no POST actions. Host-only enforcement follows the existing cooperative hook threat model in spec 9.1, not an operating-system identity boundary.

Single-field replies edit as plain text. Multi-field tracker drafts edit as a JSON object of text fields such as `draft.title` and `draft.description`; field names and destination metadata cannot be changed through the editor. The stored record preserves original and final inputs and text. Events contain IDs and outcome metadata, not message bodies. Reply bodies remain in local day state for owner review.

A successful send closes the draft. Repeated or competing approvals cannot send it again. Lint or editor failure leaves it pending. A send attempt with a failed or interrupted outcome remains `failed` or `sending` and cannot be retried through approval; inspect the destination before taking further action. Changing the configured adapter or DM destination also refuses replay. Cross-day browsing and transport reconciliation are deferred.

`bin/wuwei metrics` includes `voice_drafts`, grouped by the draft's voice audience: `sent`, `share_sent_unedited`, and `edit_sizes` for edited successful sends. Edit size counts changed characters using matched spans, with a replacement counted as the larger removed or inserted span. Dropped, pending, failed and interrupted drafts are excluded. No successful sends reports `unmeasured`. No new configuration keys are needed.

## Item worktrees

After the morning gate, create each code item's worktree with `bin/wuwei worktree add <item>`. Pass `--repo <name>` when `.wuwei/config.toml` configures more than one `[[repos]]` entry. The command creates `worktrees/<item>` in the workspace on a new branch named after the item in lower case, starting from the repository's current HEAD. It installs the managed pre-commit and pre-push hooks and the workspace anchor, then prints JSON with `branch` and `path`. Pass that `path` to `bin/wuwei brief ... --worktree`. Without gate approval it exits 1 and creates nothing.

A worktree made with raw `git worktree add` has no anchor. Its commits and pushes outside the Claude Bash hook skip the WUWEI guards.

## Raising a PR

`bin/wuwei pr raise OWNER/REPO --base BRANCH --title TEXT --body-file PATH --item ITEM` raises a prepared, pushed branch. All four options are required. The body file must be a regular file, not a symlink. The item must be in the approved plan with a worktree recorded by `bin/wuwei brief ... --worktree`, and it must not already link a PR. The pre-PR gate runs on the worktree head first; a finding exits 1 and raises nothing.

## Watch state

`bin/wuwei status --line` and `status --json` report the watch from today's `watch: clock` events and from whether `bin/wuwei watch install` has installed its unit for this workspace:

- Installed, and no clock line today or today's latest is older than `watch.dead_seconds`: `watch dead`, one `watch: health` page. This includes the morning after the watch died overnight. The page clears at the next clock line, or after `watch uninstall` when no clock line was written today.
- Not installed, and no clock line today: `watch off`. It is not a page or a nudge.
- Not installed, and today's clock line went stale (a watch started by hand died): `watch dead`, one page that clears at the next clock line.

Before the morning gate is approved, including before today's `state.json` exists, the line starts `WUWEI no plan yet` and exits 0, for example `WUWEI no plan yet | pages 0 | nudges 0 | watch off | meeting unmeasured`. Pages and nudges stay visible. `status --json` carries the same fact as `gate_approved`. A lost state (no `state.json` next to a snapshot) still reads `WUWEI ? unmeasured` with exit 2.

`watch unmeasured`: the clock cannot be read or is in the future; one nudge. The same health appears in `bin/wuwei nudges`, at session start and in sweeps. A running watch adds nothing to the line.

When one or more registered sessions are live, the line adds `sessions N` before the reply and meeting parts, and `status --json` carries `sessions`.

When raised or claimed PRs changed since the planner last saw a wake, the line adds `prs N changed`, cleared by the next `session: wake-seen`, and `status --json` carries `prs_changed`.

## Heartbeat

A clock line proves the watch runs, not that the system behaves. On every watch loop iteration the watch also runs a fixed table of synthetic probes and writes one `heartbeat: clock` event. `bin/wuwei heartbeat` runs the same probes on demand and prints one `<probe>: <result> <value>` line each. It exits 0 when every probe is ok, 1 when one failed, and 2 when one is unmeasured or the probes could not run. The on-demand command writes no state, appends no event and sends no ping.

| Probe | ok when | Value |
| --- | --- | --- |
| `refused` | `hook PreToolUse` with Bash `git push --force origin main` exits 2 | `exit N`, plus the first stderr line when not ok |
| `allowed` | `hook PreToolUse` with Bash `ls -la` exits 0 | `exit N`, plus the first stderr line when not ok |
| `state_write` | `hook PreToolUse` with a Write to today's `.wuwei/days/<day>/state.json` exits 2 | `exit N` |
| `state` | `state.lock` is taken within 1 s and today's state reads | milliseconds waited, or the error |
| `integrity` | the cached verdict is clean and no installed plugin file is newer than it | the integrity reason |
| `config` | `config.toml` loads and every selected adapter has its credential variables (the offline part of `config check`) | the missing names |
| `clocks` | the watch and listener clocks are alive or off | the dead or unmeasured message |
| `status_line` | `status --line` exits 0 within 200 ms wall | milliseconds |
| `planner` | today has no planner, or the planner session is registered and not stale | idle seconds |
| `memory` | free memory is at or above `host.free_memory_mb` (unmeasured with `adapters.host = "none"`) | MiB free |

The hook probes run through the real `bin/wuwei hook PreToolUse` with session id `wuwei-heartbeat` and cwd `.wuwei`, started together with `status --line`. Their refusals are not recorded as `hook.refusal` events. Probes never write outside `.wuwei/`, never touch a configured repository, make no code-host or model call and spend no tokens.

Each probe is `ok`, `failed` or `unmeasured` with its value. The `heartbeat: clock` record, also kept under `watch.heartbeat` in day state, carries `health`, every probe's `result` and `value`, `drift`, `page` and `ping`. Health is `degraded` when any probe failed, else `unmeasured` when any probe is unmeasured, else `ok`.

- `status --line` adds `health ok`, `health degraded` or `health unmeasured` after the watch and listen parts once today has a heartbeat line. With no heartbeat line today there is no `health` part; with a heartbeat line while the watch is not alive, health is `unmeasured`.
- While health is degraded there is exactly one `heartbeat` page naming the first failed probe and its value, for example `heartbeat integrity failed: ...`. The next heartbeat with every probe ok clears it.
- A probe that was ok in the previous heartbeat and failed now is `behaviour drift`: the record lists it under `drift`, the watch log prints `heartbeat: behaviour drift: <probe>`, and the page reason starts `behaviour drift: `.

Dead-man ping: set `watch.ping_url` to the https check URL of a hosted cron monitor such as Healthchecks.io or Cronitor. Each heartbeat whose health is ok sends one GET to it (5 s timeout); any failed or unmeasured probe withholds it, so the monitor alerts your phone when the host stops or stops behaving. The record says `sent`, `withheld`, `failed` or `off`. A failed ping is logged as `heartbeat ping failed: <host>: <error>` and never stops the watch. Keep the URL private: it is never written to logs, events or state.

## Sessions

Several Claude Code sessions can work in one workspace. Once today's `state.json` exists, the SessionStart, Stop and SubagentStop hooks record each session in the `sessions` registry of day state (role, start, last hook, working directory). No hook creates day state. SessionStart also exports `WUWEI_SESSION_ID` through Claude Code's `CLAUDE_ENV_FILE`, so CLI calls from that session know which session called them. A session with no hook activity for `sessions.stale_seconds` is stale. The registry and claims are written only by these hooks, `plan session`, `brief builder` and `worktree add`.

- `bin/wuwei sessions` prints the registry as JSON: id, role (`planner`, `adhoc`, `seat-host` or `remote`), age, idle seconds, stale, last hook and claimed items. `planner`, `adhoc` and `remote` (a session the control plane started for a Slack command) are set today; nothing sets `seat-host` yet.
- `bin/wuwei plan session <id>` still names exactly one planner. A second session is refused with exit 2 naming the current planner; `bin/wuwei plan session <id> --take-over` hands the role over and records `previous` on the `plan.session` event. Wakes then go to the new planner. When the planner is stale, `nudges` names the take-over command.
- `bin/wuwei brief builder <item> ...` and `bin/wuwei worktree add <item>` claim the item for the calling session. The same commands from another session, or from a host terminal without `WUWEI_SESSION_ID`, exit 2 naming the claimant while it is live. Once the claimant is stale, the next session takes the claim. Gate, sentinel and other briefs are never refused by a claim.

## Seat briefs and the build loop

| Behaviour | Rule |
| --- | --- |
| Brief body | `wuwei brief ROLE ITEM NAME --body TEXT` or `--file PATH`; `--file -` reads stdin. With neither, the command exits 2 and never reads stdin. |
| Gate role names | `arch`, `quality` and `security`, as returned by `wuwei dispatch next`, write briefs against the `sentinel-<role>` charter. |
| Automatic phases | The first `build next` launch moves `planned` to `implement`. When checks pass, `implement` moves to `gate` and `fix` moves to `delta`. `dispatch next` moves `gate` to `fix` when it returns `fix`, and opens the builder's fix round. `bin/wuwei pr raise` moves `gate` or `delta` to `raised`; an observed merge (`pr state`, `pr act`, the watch) moves `raised`, `fix` or `delta` to `merged`. |
| Delta continuation | SubagentStop records the sentinel's agent ID on its seat. `dispatch next` returns a `continue` action in `seats` with that ID as `resume`. Agent `resume` with that ID continues the same brief at the current HEAD; any other reuse of the brief is refused. The continued seat rewrites its own verdict file. |
| Push evidence | `wuwei build check ITEM` records fast checks through the same producer as `wuwei fast-checks`, so a passing check satisfies the push guard. |
| Charter names | `lead`, `builder`, `shepherd`, `sentinel-arch`, `sentinel-quality`, `sentinel-security`, `sentinel-goal` or `steward`. Each seat name gets one brief. `runtime dispatch` accepts `arch`, `quality` and `security` for the sentinel roles, as `brief` does. |
| Gate body | A gate body must not ask for an inline verdict or restate the verdict path; the brief adds it. A `Paths:` line lists extra paths for the SLICE protected-path check. |

## Item phase order

Phases move by themselves on the daily path. `bin/wuwei state transition` is a [recovery](recovery.html) command and accepts only these moves. `parked` and `escalated` resume only to the recorded prior phase.

| Phase | Legal next phases |
| --- | --- |
| `planned` | spec, implement, parked, escalated |
| `spec` | implement, parked, escalated |
| `implement` | gate, parked, escalated |
| `gate` | raised, fix, parked, escalated |
| `fix` | delta, merged, parked, escalated |
| `delta` | raised, fix, merged, parked, escalated |
| `raised` | fix, merged, parked, escalated |
| `parked` | planned, spec, implement, gate, raised, fix, delta |
| `escalated` | planned, spec, implement, gate, raised, fix, delta |
| `merged` | none |

## Gate verdict layout

A quality verdict with one finding that `bin/wuwei verdict lint FILE --role sentinel-quality` accepts:

```text
# Quality verdict ITEM-1

Verdict: FIX
Head: 3f1c2ab9e0d4

- Q1 medium src/calc.py:19: the test accepts any ValueError, so a regression that raises one from a different cause would still pass. blocks: yes
Probe: mutation changed the guard message; the test still passed.

Simplicity: none, one guard and one division.
Design: none, a single pure function.

VAL: FINDING Q1
TEST: FINDING Q1
BUD: N.A. no external calls

Blocked: none
Gap: none
Change: none
```

The lint rules:

- Exactly one `Verdict: PASS|FIX|PARK|ESCALATE` line and one `Head: <7 to 40 hex>` row.
- A `Probe:` or `Mutation:` line; write `not run` when the seat could not run one.
- `Blocked:`, `Gap:` and `Change:` once each.
- Quality adds exactly one `Simplicity:` and one `Design:` row.
- Arch, quality and security add class-sweep lines such as `VAL: PASS`, `TEST: N.A.` or `AUTH: FINDING <id>`.
- A non-PASS verdict needs at least one finding. A PASS verdict carries no `blocks: yes` finding.
- A finding starts on a bullet or table row, a line beginning with its severity, a `Severity:` line, an `Assumption:` line, or a numbered or `F1` line. An `Assumption:` finding reviews an assumption recorded under `Assumptions:` in the item's spec or PR body and needs the same four fields.
- Each finding carries a severity (P0 to P3, critical, high, medium, low or info), a `file:line` (or `Lnn` for docs), `blocks: yes|no`, and a failure scenario (for example "fails when", "would" or "impact").
- Fenced blocks, quoted lines and HTML comments are ignored.

## State recovery

Every state write also writes a read-only copy of the written state to `.wuwei/days/<date>/state.snapshot.json`. When today's `state.json` is truncated or otherwise unreadable, every hook and command that reads state fails closed and names `wuwei state recover`. A missing `state.json` next to a snapshot fails the same way, so no write can replace the snapshot first.

Run `bin/wuwei state recover` in a host terminal. It prints a short snapshot digest and asks you to type it, then restores `state.json` from the snapshot under the state lock and appends a `state.recovered` event. The day continues from the last state WUWEI wrote.

| Exit | Meaning |
| --- | --- |
| `0` | State restored from the snapshot. |
| `1` | `state.json` is readable (nothing to recover), or you declined. |
| `2` | No usable snapshot, the snapshot changed during confirmation, or no terminal could ask you. |

Recovery is an owner action. Agent tool hooks refuse `wuwei state recover` inside a workspace and refuse writes to the snapshot. As with other host-only actions, this follows the cooperative hook threat model in spec 9.1.

## Shadow mode

`bin/wuwei init --shadow` writes `guards.mode = "shadow"` and today's date as `guards.shadow_since` into a new workspace; with `--upgrade` it exits 2. In shadow mode a refusal from any guard module except `protect_state`, `integrity`, `deploy`, `outward` and `pr` is recorded as a `guard.would_refuse` event and the hook exits 0. The event payload is `{guard, reason, target, session, item}`: `target` is the normalised Bash command, else the file path, else the tool name, with credentials, the canary and the honeytoken redacted; `item` is the item the session claims, or null. Only the hook writes it; `bin/wuwei event` refuses the kind. If the event cannot be written, or the config cannot be read, the refusal is enforced. Refusals in the heartbeat session `wuwei-heartbeat` are always enforced.

`status --line` adds a `shadow` part after the nudges while the mode is on, and `status --json` carries `shadow`. Once `guards.shadow_days` calendar days have passed since `guards.shadow_since`, `bin/wuwei nudges` and the status line count one `guards.shadow` nudge asking you to switch to enforce or raise `guards.shadow_days`. With an empty `shadow_since` there is no nudge.

## Host terminal actions

These are owner actions. Agent tool hooks refuse them inside a workspace, so run them yourself in a host terminal:

| Command | Asks you to type a digest |
| --- | --- |
| `bin/wuwei decision outcome D-<n> <option>` | yes |
| `bin/wuwei state recover` | yes |
| `bin/wuwei integrity reconfirm` | yes |
| `bin/wuwei mcp decide` | yes |
| `bin/wuwei drafts approve <id>` | yes |
| `bin/wuwei drafts drop <id>` | no |
| `bin/wuwei goals edit` and `voice edit` | no |
| `bin/wuwei watch uninstall` | no |
| `bin/wuwei listen uninstall` | no |
| `bin/wuwei remote ack` | yes |
| `bin/wuwei config promote` | yes |

A command that asks for a digest reads it from `/dev/tty`. Without a terminal it changes nothing and exits 2 with `this is an owner action: run it in a host terminal`. `drafts approve --edit`, `goals edit` and `voice edit` open `EDITOR`. As with other host-only actions, this follows the cooperative hook threat model in spec 9.1.

## Hook latency budget

Every tool call waits for `bin/wuwei hook <event>`, so the hook path carries a budget (spec 10.6). The budget is 50 ms CPU p95 on developer hardware (M-series class); about 2x on 2-CPU CI runners. It applies to PreToolUse, PostToolUse and `bin/wuwei status --line`. Inside a workspace, Stop, SubagentStop, SessionStart and the PreToolUse `git commit` and `git push` checks are held to 100 ms wall p95.

The hardware class matters because every hook first pays for an interpreter start. `python3 -I -c pass` takes about 20 ms on an M-series Mac and about twice that on a GitHub-hosted 2-CPU runner. PreToolUse, PostToolUse and `status --line` measure 40 to 50 ms CPU p95 on an M-series Mac.

CPU p95 on a 2-CPU runner, three `main` runs of 2026-09-30:

| Path | CPU p95 |
| --- | --- |
| PreToolUse | about 100 ms |
| PostToolUse | 90 ms |
| `status --line` | 110 ms |
| Stop | 90 ms |
| SubagentStop | 85 to 106 ms |
| SessionStart | 140 to 157 ms |
| `git commit` check | 115 ms |
| `git push` check | 135 to 148 ms |

### Where hook time goes

A hook process starts an interpreter, imports the CLI core, discovers the guards, then runs the ones that match its event and tool. Each hook imports only the guard modules its event and tool can run (`MODULES` in `cli/wuwei/guards/__init__.py`); a guard module missing from that map is imported for every event. Stop and PostToolUse never import the Bash guards, and a PreToolUse call for a file tool imports only the file guards.

Guard discovery on an M-series Mac, before and after the import map (2026-09-30, three runs each):

| Event and tool | Before | After | Modules imported after |
| --- | --- | --- | --- |
| Stop | 9.2 to 11 ms | 5.3 to 7 ms | lifecycle, stop |
| PostToolUse | 7.9 to 9 ms | 3.6 to 4.2 ms | decision, traces, verdict |
| PreToolUse Bash | 7.5 to 8.4 ms | 5.6 to 5.9 ms | commit_push, deploy, integrity, outward, pr, protect_state |
| PreToolUse Write | 7.3 to 8.3 ms | 4.7 to 5.2 ms | integrity, outward, protect_state |
| SubagentStop | 7.6 to 7.9 ms | 2.7 to 3 ms | agent_launch, verdict |
| SessionStart | 8.3 to 10 ms | 4.6 to 5 ms | integrity, lifecycle |
| PreCompact | 9.2 to 9.8 ms | 4.5 to 5 ms | lifecycle |

Whole hook, same host, before and after run interleaved, 100 runs each, p95 of two runs (the `python3 -I -c pass` startup floor is 13 to 15 ms CPU on this host):

| Path | CPU p95 before | CPU p95 after | Wall p95 before | Wall p95 after |
| --- | --- | --- | --- | --- |
| PreToolUse `npm test` | 42.5 to 43.9 ms | 39 to 41.8 ms | 46.8 to 47.5 ms | 42.1 to 45.1 ms |
| PreToolUse `ls -la` | 41.6 to 45.9 ms | 37.9 to 41.5 ms | 45.5 to 48.7 ms | 42.2 to 44.7 ms |
| PreToolUse Write | 40.7 to 44.1 ms | 37.3 to 39.2 ms | 43.3 to 46.8 ms | 40.8 to 41.6 ms |
| PostToolUse | 41.3 to 48.7 ms | 39 to 42.8 ms | 43.8 to 52.7 ms | 42.9 to 46.4 ms |
| Stop | 39.2 to 42.7 ms | 37.1 to 39.4 ms | 42.1 to 45.5 ms | 39.7 to 43.1 ms |

The `git commit` and `git push` checks spend most of their time in `git` subprocesses, so the 2 ms they save on guard imports is inside their run-to-run spread.

### The latency CI job

The `latency` job in `.github/workflows/tests.yml` runs `python -m pytest -q tests/test_hooks.py -k latency` with `WUWEI_BENCH=1` on every push and pull request. It is `continue-on-error`: a trend line, not a gate. On a 2-CPU runner it is red on every push, because the runner is about 2x slower than the hardware the budget is set for. A red job never blocks a merge.

Each benchmark prints one report line:

```text
<path> p95 over <runs> runs: CPU <ms> ms, wall <ms> ms, python3 -I startup floor CPU <ms> ms, wall <ms> ms, load <load> on <n> CPUs
```

Read the hook figure against the startup floor on the same line. A hook that keeps its usual distance above the floor is the runner; a hook whose distance above the floor grows from one run to the next got slower.

In a source checkout, `WUWEI_BENCH=1 python -m pytest -q tests/test_hooks.py -k latency` asserts the budgets. Without `WUWEI_BENCH=1` the benchmarks print the same lines and skip, because wall time on a busy host is load-bound.
