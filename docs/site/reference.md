# Operator data reference

Use `bin/wuwei` from the installed checkout, or `python3 -P -m wuwei` with the package on `PYTHONPATH`. The `-P` option keeps a local `wuwei/` directory from shadowing the CLI.

## Commands

Every command `bin/wuwei --help --all` prints; `bin/wuwei --help` groups them and leaves out the plumbing, and `bin/wuwei <command> --help` shows its options. Commands marked plumbing are called by hooks, seats or the plugin, not by you.

| Command | What it does | More |
| --- | --- | --- |
| `bin/wuwei agents` | Plumbing: builds or checks the generated role agents. | [Concepts](concepts.md#roles) |
| `bin/wuwei board` | Plumbing: serves the day board to Claude Code over MCP stdio. | [Cockpit and board](concepts.md#cockpit-and-board) |
| `bin/wuwei brief` | Writes and logs a seat brief. | [Seat briefs](#seat-briefs-and-the-build-loop) |
| `bin/wuwei build` | Selects the next builder action. | [Seat briefs](#seat-briefs-and-the-build-loop) |
| `bin/wuwei calibrate` | Profiles the repositories and proposes config; `--measure` times each test runner once to decide whether it is a fast check; `--interview` asks you; `export` and `import` share a profile. | [Calibration](configuration.md#calibration) |
| `bin/wuwei close` | Refuses day close until every obligation lands; `--widget` asks about each open item. | [Day close](concepts.md#day-close) |
| `bin/wuwei config` | Inspects and changes workspace configuration: `check`; `promote`, `set <key> <value>` and `add-repo` apply after a digest. | [Configuration](configuration.md#calibration) |
| `bin/wuwei consolidate` | Reviews memory, packs old days into tarballs, rebuilds digests and proposes forgetting; `consolidate --widget` asks each pending proposal. | [Configuration](configuration.md#host-build-and-memory) |
| `bin/wuwei dashboard` | Serves the read-only day board on loopback. | [Cockpit and board](concepts.md#cockpit-and-board) |
| `bin/wuwei decide` | Owner: `decide D-<n> <option> [--note <text>]` records the answer to today's decision, the MCP registry one included. | [Host terminal actions](#host-terminal-actions) |
| `bin/wuwei decision` | Checks and routes decision records; `outcome` records your answer. | [Decision record](#decision-record) |
| `bin/wuwei discover` | Discovers candidate work. | [Goals and discovery](configuration.md#goals-and-discovery) |
| `bin/wuwei dispatch` | Decides planner gate and discovery work; `dispatch opinion <item>` runs the second-opinion gate. | [Review tiers](concepts.md#review-tiers) |
| `bin/wuwei docs` | Writes an item's docs page or publishes the day's page under the [docs system](concepts.md#docs-system). | [Docs](configuration.md#docs) |
| `bin/wuwei docs page <item>` | Renders the item's page from its records (scope, PR, goal, evidence, links) and refuses absolute paths, `.wuwei/` records and credentials. Under markdown it writes `<docs.root>/<item>.md` in the item's worktree; under notion or confluence it stores a draft, or writes when `page` is in `docs.auto`, and records `docs.written`. | [Docs](configuration.md#docs) |
| `bin/wuwei docs publish report\|retro` | Publishes today's report or retro page once per day under notion or confluence; `wuwei report` and `wuwei retro` call it when `docs.publish` lists the kind. | [Docs](configuration.md#docs) |
| `bin/wuwei doctor` | Finds install, host, workspace, gate, day and guard problems and prints each fix; `--fix` applies the allow-listed ones after one host confirmation. | [Doctor](#doctor) |
| `bin/wuwei drafts` | Lists outward drafts awaiting owner approval. | [Outward draft queue](#outward-draft-queue) |
| `bin/wuwei grants` | Lists your standing grants and today's grants for owner-only actions; `grants revoke <n>` removes a standing one. | [Host terminal actions](#host-terminal-actions) |
| `bin/wuwei event` | Plumbing: appends a timestamped day event. | |
| `bin/wuwei fast-checks` | Plumbing: runs and records the configured fast checks. | [Seat briefs](#seat-briefs-and-the-build-loop) |
| `bin/wuwei git-hook` | Plumbing: runs a native Git identity or push guard. | [Item worktrees](#item-worktrees) |
| `bin/wuwei goals` | Shows or edits your goals. | [Goals and discovery](configuration.md#goals-and-discovery) |
| `bin/wuwei heartbeat` | Probes that hooks refuse, allow and answer in budget. | [Heartbeat](#heartbeat) |
| `bin/wuwei hook` | Plumbing: runs the guards for a Claude Code hook. | [Hook latency budget](#hook-latency-budget) |
| `bin/wuwei index` | Plumbing: generates the memory index. | [Concepts](concepts.md#memory) |
| `bin/wuwei init` | Creates or upgrades a workspace; `--posture observe|guarded|strict` sets the [security posture](#security-posture) (`--shadow` is `--posture observe`). | [Daily path](daily.md) |
| `bin/wuwei integrity` | Checks signed plugin integrity; `reconfirm` pins a development checkout. | [Recovery](recovery.md#integrity-reconfirm) |
| `bin/wuwei listen` | Polls the inbound source into the workspace inbox and probes raised and claimed PRs. | [Remote](remote.md) |
| `bin/wuwei mcp` | Checks the attached MCP servers; `decide D-<n> <option>` records your answer. | [MCP registry checks](configuration.md#mcp-registry-checks-s3) |
| `bin/wuwei mcp` | Checks the attached MCP servers; `decide [D-<n>] <option>` records your answer. | [MCP registry checks](configuration.md#mcp-registry-checks-s3) |
| `bin/wuwei memory` | `lint` checks workspace memory; `memory show <date>` prints a raw or archived day; `memory status` sizes every tier; `memory export --claude` writes the rules block into `memory.export_to`; `memory forget F-n apply` or `keep` is your answer to a forgetting proposal. | [Concepts](concepts.md#memory) |
| `bin/wuwei merge` | Checks or merges an eligible PR. | [Retro and merge](#retro-and-merge-configuration) |
| `bin/wuwei metrics` | Shows the recorded process metrics; `metrics --week [<week>]` prints a week's telemetry aggregate, computing it when absent. | [Telemetry](configuration.md#telemetry) |
| `bin/wuwei guide` | Prints the plugin reference a session reads at start: every command, the accepted command forms, the rules, the guard areas by posture and where records live. `init` and `init --upgrade` write the same text into `memory.export_to`. | [What the session knows](agent.md) |
| `bin/wuwei next` | Prints where the day stands and the one next step with its command; `--json` prints `{state, step, command}`. | [What the session knows](agent.md) |
| `bin/wuwei note` | Manages workspace notes. | [Concepts](concepts.md#memory) |
| `bin/wuwei nudges` | Lists open nudges and pages. | [Watch state](#watch-state) |
| `bin/wuwei outbound` | Inspects the outbound approval policy; `bin/wuwei outbound tiers` prints the effective tier table, `bin/wuwei outbound explain <draft id>` the rows a draft passed and the row that held it (both read-only), and `learn --tool <tool>` proposes an unknown connector, its channels with their class and its people on one card (planner session). | [Outbound tiers](configuration.md#outward-text-and-outbound-tiers) |
| `bin/wuwei payload` | Plumbing: prints the session memory payload. | |
| `bin/wuwei plan` | Proposes or approves the morning plan; `session` names the planner; `carry` and `park` record an open item's disposition at close; `set <item> ticket=<id>` records an existing ticket once the tracker confirms it, and `set <item> spec=skipped --reason <why>` skips the spec for one item. | [Lead plan JSON](#lead-plan-json) |
| `bin/wuwei plan set <item> docs=<page>\|new\|none --reason "<why>"` | Records the item's [docs obligation](concepts.md#docs-obligation) value; a page is read through the docs adapter first, and `none` needs a reason. Under markdown, `new` is refused: write the page with `bin/wuwei docs page <item>`. | [Docs](configuration.md#docs) |
| `bin/wuwei pr` | Measures owned PRs, raises one, shows its reviewers, or records a verified disposition. | [Raising a PR](#raising-a-pr) |
| `bin/wuwei promote` | Promotes memory and charter proposals. | [Charter overrides](charter-overrides.md) |
| `bin/wuwei rank` | Plumbing: ranks candidate JSON using the workspace goals. | [Lead plan JSON](#lead-plan-json) |
| `bin/wuwei remote` | Owner actions for the remote control plane. | [Remote](remote.md) |
| `bin/wuwei reply` | Replies to one unthreaded human obligation. | [Outward draft queue](#outward-draft-queue) |
| `bin/wuwei report` | Shows your report. | [Day close](concepts.md#day-close) |
| `bin/wuwei setup` | Owner, host terminal: runs `init` if needed, discovers the repositories and the host, calibrates and interviews, applies one proposal after a digest, then checks and prints what is still owed; `--shadow`, `--posture <profile>`, `--repos <dir>...`. | [Daily path](daily.md) |
| `bin/wuwei shadow` | `report` lists what the guards would have refused since `guards.shadow_since`, grouped by guard, and names likely false positives. | [Security posture](concepts.md#security-posture) |
| `bin/wuwei retro` | Compiles the steward retro. | [Retro and merge](#retro-and-merge-configuration) |
| `bin/wuwei runtime` | Dispatches and inspects runtime jobs. | [Recovery](recovery.md#runtime-dispatch) |
| `bin/wuwei seat` | Recovers a stuck seat: records its report from a file, or stops it as unmeasured. | [Stuck seats](#stuck-seats) |
| `bin/wuwei sessions` | Lists registered sessions, roles and claims. | [Sessions](#sessions) |
| `bin/wuwei signal` | Plumbing: classifies attention. | |
| `bin/wuwei state` | Reads or updates day state; `recover` restores it. | [State recovery](#state-recovery) |
| `bin/wuwei status` | Shows day status; `--line` is the status line. | [Watch state](#watch-state) |
| `bin/wuwei steward` | Runs a steward review or acknowledges steering. | [Steward](#steward) |
| `bin/wuwei telemetry` | `preview [<week>]` prints exactly what each sharing mode would send; `off` stops sharing; `send [<week>]` opens the attributed issue (owner, host terminal); `proposals [--widget]` lists or presents a final week's proposals once. | [Telemetry](configuration.md#telemetry) |
| `bin/wuwei sweep` | Plumbing: checks day obligations. | [Concepts](concepts.md#day-flow) |
| `bin/wuwei tracker` | `create <item>` opens the item's ticket from its record; `create --bug, --triage or --follow-up <subject> "<title>" --evidence "<file:line>"` opens a linked ticket; `log` writes today's decisions, progress, verdicts, pull request and close as ticket comments; `done <item>` moves the ticket to done. | [Tickets and comments](concepts.md#tickets-and-comments) |
| `bin/wuwei verdict` | Plumbing: checks a gate verdict. | [Gate verdict layout](#gate-verdict-layout) |
| `bin/wuwei voice` | Shows or edits your voice profile. | [Owner voice](configuration.md#owner-voice) |
| `bin/wuwei watch` | Supervises workspace activity and owned PRs. | [Running the watch](configuration.md#running-the-watch) |
| `bin/wuwei why` | Explains from recorded events why an item, a decision or a refusal is where it is. | [Why](#why) |
| `bin/wuwei worktree` | Creates or adopts an anchored item worktree. | [Item worktrees](#item-worktrees) |

## Lead plan JSON

Run `bin/wuwei plan template` in a workspace for a complete lead JSON skeleton. `bin/wuwei plan template | bin/wuwei plan propose -` creates today's proposal. Replace sample evidence before approval. The top-level keys are:

| Key | Content |
| --- | --- |
| `goals` | Nonempty list of `G-n` identifiers in `.wuwei/memory/goals.md`; while it has no goals, a list of goal objects with `id`, `outcome`, `measure`, `target`, `date` and `priority`. |
| `candidates` | List of candidate objects described below. |
| `seat_policy` | Role to `{ "runtime": "claude", "model": "sonnet" }` mapping. |
| `envelope` | `start`, `end`, and nonnegative `net_build_hours`. |
| `sweep` | Source to measured or unmeasured status string. |
| `cap` | Running build seat count; `0` derives it from the host and `budget.tokens_per_day`, a positive number is your override. |

Each candidate needs a unique `id`, a confirmed `goal` or `unplanned`, `evidence`, `scope`, `overlap`, `track`, `flags`, `score`, and `evidence_lines`. `track` is `SLICE` for a small change with one pre-PR gate set, or `FULL` when a spec-done gate is needed. `flags` has exactly three booleans: `trust_surface`, `boundary_relevant`, and `agent_surface`. These affect owner routing and security gates. An optional `tier` (`light`, `standard` or `full`) raises the review tier `wuwei dispatch next` computes from the diff; a lower one is refused and recorded as a reason. `evidence_lines` has a nonempty one-line citation for every score component.

`bin/wuwei rank template` prints a candidate list for the configured framework. Pass it to `bin/wuwei rank -` to inspect the order. Ties use goal priority, then candidate id.

`bin/wuwei rank FILE` (or `-` for stdin) also accepts a whole lead JSON, such as `bin/wuwei plan template` output or today's `.wuwei/days/<date>/proposal.json`, and ranks its `candidates`. An object without a `candidates` list exits 2 with `candidates must be a list`.

### WSJF and RICE

For `prioritisation.framework = "wsjf"`, `score` contains `value`, `time_criticality`, `risk_reduction`, and `job_size`. Each uses the Fibonacci scale 1, 2, 3, 5, 8, 13, 20. WSJF is `(value + time_criticality + risk_reduction) / job_size`.

For `prioritisation.framework = "rice"`, use `reach` (positive people or systems), `impact` (0.25, 0.5, 1, 2, 3), `confidence` (0.5, 0.8, 1), and `effort` (positive seat-days). RICE is `reach * impact * confidence / effort`.

## Decision record

`bin/wuwei decision template` prints a record that passes `bin/wuwei decision lint FILE`. Save it as `.wuwei/days/<date>/decisions/D-<n>.md`. Include `Question:`, `Context:` with evidence paths, and an `Options:` table with at least two choices including deferral. A `Musts:` table marks pass/fail for each option. A `Wants:` table gives each criterion a weight from 1 to 10 and each option a score from 0 to 10. `Recommendation:` names the highest scoring option that passes every must. Complete `Confidence: high|medium|low`, `Reversibility: one-way|two-way`, `Blast radius:`, `Pre-mortem:`, `Revisit:`, `Decided-by: seat|owner|mandate`, and `Outcome:`. The lint OK line names the derived class, for example `OK: A (80), Routine`; a record without a recommendation or a reasoning is refused with `add the recommendation and the reasoning`. `bin/wuwei decision show D-<n>` prints a valid record at the `owner.verbosity.decisions` level (exit 1 for an invalid record, 2 for one it cannot read), and `--full` prints every field. `--widget` instead prints a JSON list with one AskUserQuestion question (`question` `D-<n>: <Question>`, `header` `D-<n>`, the recommended option first with its description prefixed `Recommended. `, at most four options, `multiSelect`) plus `record`, `wuwei decide D-<n> <label>`, the command that records the answer. A valid record whose text carries tells from the writing checklist lints with an extra `style:` line and still exits 0. Route an existing record with `bin/wuwei decision route D-<n>`: under `autonomy.mode = "autonomous"` it prints `mandate` for a record it takes as recommended (the record then reads `Decided-by: mandate`, `--widget` prints `[]` and `bin/wuwei decide D-<n> <option>` reverses it), otherwise `seat` or `owner`. For a confirmation from a person outside the loop, run `bin/wuwei decision route D-n --external <item>`: the record comes to you whatever its reversibility, the item records `assumption: {kind: external, decision, day, since, status: waiting}` and its reversible work continues. After `decisions.wait_hours` weekday hours in `owner.timezone` without an owner answer, the watch sweep confirms the recommendation on a two-way door (`status: confirmed`; the record stays pending) or parks the item with the record as its decision (`status: parked`); either writes a `decision.waited` event, and your `decision outcome` resumes a parked item. `bin/wuwei pr act` routes the decisions it creates, and a routed decision without an owner outcome shows in `bin/wuwei nudges` and the status line.

## Retro and merge configuration

Every seat ends with three retro note keys on separate lines: `Blocked:`, `Gap:`, and `Change:`. Use `none` if a line has no finding. In `.wuwei/config.toml`, `[retro]` sets `repo` (default `"."`), `charter_paths` (default `[".wuwei/charters"]`), and `changelog` (default `".wuwei/memory/CHANGELOG.md"`).

In a `[[repos]]` entry, `[repos.merge]` sets `merge.auto` (default `false`). Automatic merge remains subject to measured policy, review, checks, soak and path rules. Set `repos.merge_deploys` correctly; WUWEI never deploys.

## Steward

`bin/wuwei steward run --trigger sweep|close|tool-calls` writes a steward brief, launches the steward seat through the runtime adapter, records a `steward.run` event and prints `steward_launch`; launch that agent exactly as returned. `bin/wuwei close` runs the close review once a day. A second `--trigger close` run the same day writes no brief, launches nothing and prints `steward: close review already ran today (brief <path>)`.

`bin/wuwei steward ack <id>` acknowledges a steward steering note. The id has the form `<item>-fix-3` (a third fix round) or `<item>-question-<agent>` (a seat stopped on a question to you without a decision record, written by the SubagentStop guard) and is named, with the note text, by the refusal `steward note <id> requires planner acknowledgement: <text>` from `dispatch next`. A `steward.due` nudge is not a note and takes no ack: it clears when `steward run` records a run.

Every steward review (on the sweep, at close and on each `dispatch next`) also counts, per item over the last `steward.loop_window_hours`, the decision and clarification records naming it on their `Question:` or `Context:` line, `gate.received` verdicts, repeated briefs for the same role and `build.fix_opened` fix requests. Above `steward.loop_threshold`, or on a second fix round today, it writes one `negotiation.loop` event per item per day with the counts and the last two exchanges: a nudge, or a page when the item's goal date has passed. The listener sends its summary to your owner DM once and records `negotiation.notified`; the status line shows `loops N`. The signal reports; it never parks or blocks.

## Codex companion protocol

Configure `codex.command` as an argv list and `codex.timeout_seconds` in `.wuwei/config.toml`. The adapter invokes `task`, `status`, `result`, and `cancel` with `--json` in the worktree. `task --fresh --background` starts a job and returns `jobId`; continuation uses `task --resume-last --background --write`. `status JOB_ID` returns `workspaceRoot` and a `job` with its own `workspaceRoot` and status. Both roots must resolve to the requested worktree. `result JOB_ID` supplies text in `storedJob.result.rawOutput`, with companion stdout or rendered text as fallback. A brief header line `Model: <model>` adds `--model <model>` to `task`. A job's result lints only its own verdict file, `gate-<brief name>.md`. A root mismatch triggers `cancel JOB_ID`. Missing fields, an error body or a timeout is unmeasured and fails closed.

## Outward draft queue

Approve-tier replies through the chat, code-host comment and tracker-create adapters are stored in today's producer-owned `drafts` state. The call returns exit 1 with the draft ID and sends nothing. Policy or security errors still fail closed. Ordinary adapter calls never treat a saved owner decision as permission to send.

| Command | Effect |
| --- | --- |
| `bin/wuwei drafts` | List today's pending drafts with text, destination, audience and tier reason. |
| `bin/wuwei drafts approve <id>` | Run security, outward, voice and humanize lint (the tells show in the prompt), then send the stored text once through its original adapter operation. |
| `bin/wuwei drafts approve <id> --always` | Send as above and add the card's tier row to `outbound.tiers`: `send` for the person a row asked about, or `ask` for the destination channel. |
| `bin/wuwei drafts approve <id> --edit` | Edit with `EDITOR` (default `vi`), lint the final text, then send it. |
| `bin/wuwei drafts drop <id>` | Close the draft without sending. |

Approval and drop are owner actions on the host terminal. Approval shows the destination and final text and asks y/N before it sends. Agent tool hooks refuse both, including registered seats. The cockpit displays pending drafts and the approval command read-only; it accepts no POST actions. Host-only enforcement follows the existing cooperative hook threat model in spec 9.1, not an operating-system identity boundary.

Single-field replies edit as plain text. Multi-field tracker drafts edit as a JSON object of text fields such as `draft.title` and `draft.description`; field names and destination metadata cannot be changed through the editor. The stored record preserves original and final inputs and text. Events contain IDs and outcome metadata, not message bodies. Reply bodies remain in local day state for owner review.

A successful send closes the draft. Repeated or competing approvals cannot send it again. Lint or editor failure leaves it pending. A send attempt with a failed or interrupted outcome remains `failed` or `sending` and cannot be retried through approval; inspect the destination before taking further action. Changing the configured adapter or DM destination also refuses replay. Cross-day browsing and transport reconciliation are deferred.

`bin/wuwei metrics` includes `voice_drafts`, grouped by the draft's voice audience: `sent`, `share_sent_unedited`, and `edit_sizes` for edited successful sends. Edit size counts changed characters using matched spans, with a replacement counted as the larger removed or inserted span. Dropped, pending, failed and interrupted drafts are excluded. No successful sends reports `unmeasured`. No new configuration keys are needed.

## Item worktrees

After the morning gate, create each code item's worktree with `bin/wuwei worktree add <item>`. Pass `--repo <name>` when `.wuwei/config.toml` configures more than one `[[repos]]` entry. The command creates `worktrees/<item>` in the workspace on a new branch named after the item in lower case, starting from the repository's current HEAD. It installs the managed pre-commit and pre-push hooks, chained with the repository's own hooks (see [`worktree.git_hooks`](configuration.md#workspace-and-repositories)), and the workspace anchor, then prints JSON with `branch` and `path`. Pass that `path` to `bin/wuwei brief ... --worktree`. Without gate approval it exits 1 and creates nothing.

`bin/wuwei worktree add <item> --branch <name>` checks an existing branch out in `worktrees/<item>` instead of creating one, and records the path as the item's worktree (event `worktree.adopted`). The item must be in the approved plan.

`bin/wuwei worktree adopt <path> --item <item>` registers an existing worktree: it chains the hooks, writes the anchor and the configured identity, records the path and the current HEAD (`worktree.adopted`) and prints JSON with `item`, `path` and `head`. It exits 1 and changes nothing when the path is not a linked worktree of a configured repository (for the main checkout it names `worktree add <item> --branch`), when the tree has uncommitted or untracked files (it names them and the `git stash push --include-untracked` command), when the item is not in the approved plan or already records another worktree, and before gate approval. `bin/wuwei pr claim` runs it for a clean worktree on the PR branch, and `bin/wuwei pr act` returns it as an `adopt` action when a fix round finds no worktree.

A worktree made with raw `git worktree add` and never adopted has no anchor. Its commits and pushes outside the Claude Bash hook skip the WUWEI guards.

## Raising a PR

`bin/wuwei pr raise OWNER/REPO --base BRANCH --title TEXT --body-file PATH --item ITEM` raises a prepared, pushed branch. All four options are required. The body file must be a regular file, not a symlink. The item must be in the approved plan with a worktree recorded by `bin/wuwei brief ... --worktree`, and it must not already link a PR. The pre-PR gate runs on the worktree head first; a finding exits 1 and raises nothing.

Reviewers are the people who committed most to the changed source paths (top two, three on a tie within `shepherd.tie_commits`), plus `shepherd.lead_login`. Their emails resolve through `shepherd.authors`, then the code host, cached for the day; an email the code host cannot resolve is skipped with a `reviewer.unresolved` event. `shepherd.reviewers`, or `reviewers` under the repository's `[repos.shepherd]`, replaces the ranking and the lead; `shepherd.reviewers_exclude` removes logins from both. When nobody but the author is left, the PR is raised with no reviewer and the command prints `reviewers: none (solo)`; `pr ping` then requests and posts nothing, and the reviewer and channel-post obligations are not owed. `bin/wuwei pr reviewers REF [--explain]` prints the selection `pr ping` would use; `--explain` adds the deciding window, each ranked login with its commits per changed path, the lead and the unresolved authors. It exits 0 selected, 1 refused, 2 could not measure.

## Watch state

`bin/wuwei status --line` and `status --json` report the watch from today's `watch: clock` events and from whether `bin/wuwei watch install` has installed its unit for this workspace:

- Installed, and no clock line today or today's latest is older than `watch.dead_seconds`: `watch dead`, one `watch: health` page. This includes the morning after the watch died overnight. The page clears at the next clock line, or after `watch uninstall` when no clock line was written today.
- Not installed, and no clock line today: `watch off`. It is not a page or a nudge.
- Not installed, and today's clock line went stale (a watch started by hand died): `watch dead`, one page that clears at the next clock line.

Before the morning gate is approved, including before today's `state.json` exists, the line starts `WUWEI no plan yet` and exits 0, for example `WUWEI no plan yet | pages 0 | nudges 0 | watch off | meeting unmeasured`. Pages and nudges stay visible. `status --json` carries the same fact as `gate_approved`. A lost state (no `state.json` next to a snapshot) still reads `WUWEI ? unmeasured` with exit 2.

`watch unmeasured`: the clock cannot be read or is in the future; one nudge. The same health appears in `bin/wuwei nudges`, at session start and in sweeps. A running watch adds nothing to the line.

When one or more registered sessions are live, the line adds `sessions N` before the reply and meeting parts, and `status --json` carries `sessions`.

When raised or claimed PRs changed since the planner last saw a wake, the line adds `prs N changed`, cleared by the next `session: wake-seen`, and `status --json` carries `prs_changed`. When any PR today was raised with no reviewer, the line adds `reviewers: none (solo)` and `status --json` carries `solo`.

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
| `read_loop` | `hook PreToolUse` with Bash `for r in a b; do echo "### $r"; cat .wuwei/$r/report.json; done` exits 0 | `exit N`, plus the first stderr line when not ok |
| `git_read` | `hook PreToolUse` with Bash `git grep -n probe` exits 0 | `exit N`, plus the first stderr line when not ok |
| `planner` | today has no planner, or the planner session is registered and not stale | idle seconds |
| `memory` | free memory is at or above `host.free_memory_mb` (unmeasured with `adapters.host = "none"`) | MiB free |
| `seats` | no seat handed back without a stop, and none was stopped unmeasured by the hook ([Stuck seats](#stuck-seats)) | `none stuck`, or `dead: <names>` with the `bin/wuwei seat stop` command |

The hook probes run through the real `bin/wuwei hook PreToolUse` with session id `wuwei-heartbeat` and cwd `.wuwei`, started together with `status --line`. Their refusals are not recorded as `hook.refusal` events. The `refused`, `allowed`, `state_write` and `read_loop` rows also carry `ms`, the call's wall milliseconds including interpreter start, which the weekly telemetry reads as hook latency; a timed-out call has no `ms`. Probes never write outside `.wuwei/`, never touch a configured repository, make no code-host or model call and spend no tokens.

Each probe is `ok`, `failed` or `unmeasured` with its value. The `heartbeat: clock` record, also kept under `watch.heartbeat` in day state, carries `health`, every probe's `result` and `value`, `drift`, `page` and `ping`. Health is `degraded` when any probe failed, else `unmeasured` when any probe is unmeasured, else `ok`.

- `status --line` adds `health ok`, `health degraded` or `health unmeasured` after the watch and listen parts once today has a heartbeat line. With no heartbeat line today there is no `health` part; with a heartbeat line while the watch is not alive, health is `unmeasured`.
- `status --line` adds `traces: N gaps` after the health part when today has N `traces.gap` events: a tool span the trace recorder could not write records one `traces.gap` event with its `reason`, `span` (the tool name) and `session`, and the hook exit stays as before. Only the hook writes the kind. The trace recorder redacts credential-shaped values only: the tool, its subcommand and the text before the first credential stay, and message bodies keep their command words and lose their text.
- `status --line` adds `running <role> <item> <HH:MM>, ...` while seats or fast checks run (`checks` for a `build check` in flight), oldest first; `status --json` carries the rows as `running`, and `bin/wuwei next` names them on its `wait` rows.
- While health is degraded there is exactly one `heartbeat` page naming the first failed probe and its value, for example `heartbeat integrity failed: ...`. The next heartbeat with every probe ok clears it.
- A probe that was ok in the previous heartbeat and failed now is `behaviour drift`: the record lists it under `drift`, the watch log prints `heartbeat: behaviour drift: <probe>`, and the page reason starts `behaviour drift: `.

Dead-man ping: set `watch.ping_url` to the https check URL of a hosted cron monitor such as Healthchecks.io or Cronitor. Each heartbeat whose health is ok sends one GET to it (5 s timeout); any failed or unmeasured probe withholds it, so the monitor alerts your phone when the host stops or stops behaving. The record says `sent`, `withheld`, `failed` or `off`. A failed ping is logged as `heartbeat ping failed: <host>: <error>` and never stops the watch. Keep the URL private: it is never written to logs, events or state.

## Doctor

`bin/wuwei doctor` runs the checks WUWEI already has in one pass and prints a row per check
in seven sections: Install (plugin, integrity, `.in_use` markers, hooks, launcher, Python),
Host (`gh`, git identity, ZIRAN, Claude Code, Codex, free memory, service manager),
Workspace (config, template drift, each repository's path, branch, identity and
`fast_checks`, calibration, interview, profiles, posture and its observe days, and `memory tiers`, which warns when raw days are older than `consolidation.archive_after_days`), Gates and adapters
(`config check`, the MCP gate and each server in today's registry record), PR flow (the
settings the shepherd reads: `owner.handles`, `shepherd.lead_login`, `shepherd.authors`,
`shepherd.review_channel` when chat is set, and the tracker, chat and review-bot adapters; an
empty one warns with `will block: <what> at <phase>` and the `config set` line, a `none`
adapter is ok with what discovery and the shepherd skip, and with `shepherd.min_reviewers = 0`
the reviewer rows are not applicable), Day and sessions
(state, planner, watch, listener, heartbeat, stuck seats, open pages, nudges, traces gaps, pre-#352 trace decisions) and Guards (the heartbeat
hook probes, plus `hook PreToolUse` from a directory outside any workspace, which must
allow). It works before there is a workspace: the Workspace section then names where to run
`bin/wuwei init --shadow`.

The config row warns, naming each unknown key, its line and the nearest documented key, when
`config.toml` loads with keys this plugin does not know. The `.in_use` row warns with
`plugin <old> running against template <new>: restart Claude Code` when another cached
plugin version has a process marker, or when `template_version` is newer than this plugin;
the status line shows the same text after the posture. A hook whose plugin is older than
`template_version` treats keys it does not know as unknown to it, never refuses over them, and
records one `config.newer_template` event `{plugin, template, session}` per session and day;
only the PreToolUse hook writes it and `bin/wuwei event` refuses the kind. `bin/wuwei setup` and
`bin/wuwei init --upgrade` end with `Restart Claude Code so only this version's hooks run` when
another version's marker is present.

Each row is `ok`, `warn`, `fail` or `unmeasured` with its value; every row that is not ok
prints `fix:` with the exact command or edit and `docs:` with the page. A row that does not
apply (the listener with `adapters.inbound = "none"`) is ok with the reason. Exit 1 when any
row is warn or fail, else 2 when any is unmeasured, else 0. Without `--fix` it writes nothing
and makes no network call beyond the `gh` reads `config check` makes. `--json` prints
`{"exit", "rows"}` with one object per row (`section`, `name`, `status`, `value`, and `fix`,
`apply`, `docs`, `detail` when set). `--section pr-flow` prints only the PR flow rows,
computed from `config.toml` alone; the planner runs it once at the start of the day.

`bin/wuwei doctor --fix` applies only this allow list:

| Fix | Command | When |
| --- | --- | --- |
| `integrity-reconfirm` | `wuwei integrity reconfirm` | a development checkout asks for reconfirmation |
| `init-upgrade` | `wuwei init --upgrade` | template drift, or `repos = []` above `[[repos]]` tables |
| `config-promote` | `wuwei config promote` | a repository has an empty `fast_checks` (held when it would also apply interview answers or a profile) |
| `calibrate` | `wuwei calibrate` | calibration drift was flagged today |
| `watch-install` | `wuwei watch install` | the watch is not installed |
| `listen-install` | `wuwei listen install` | an inbound source is set and the listener is not installed |
| `trace-decisions` | `supersede pre-#352 tool-sequence decisions` | today has pending tool-sequence decisions the pre-#352 sweep wrote for a session with no item |
| `mcp-reports` | move legacy MCP reports | `.wuwei/ziran/report-*` directories from v0.12.0 (moves readable ones to `<server>/<digest>.json`, removes empty and clean ones, keeps those a pending decision lists) |

It previews every fix first (the command's own dry run, or the digest its own confirmation
would ask for), prints them as one batch, and asks y/N once on `/dev/tty`. Without a
terminal it exits 2 and applies nothing; any answer but y applies nothing and exits 1. Each fix
is then applied bound to what its preview showed: a plan or digest that changed since the
preview is refused and reported, and the other fixes still run. Every applied fix appends one
`doctor.fixed` event `{fix, exit}`, then doctor diagnoses again and exits with that result.
Decisions stay printed under `Not applied`: `mcp decide`, `security.posture`, `state recover`,
repository identity and anything that touches the code host. `--fix` and `--json` together
are a usage error.

`bin/wuwei doctor --fix --widget` previews the same batch and prints it as a JSON list of
multi-select AskUserQuestion widgets of at most four fixes each (one fix gets a `Skip` option),
each with `record` set to `wuwei doctor --fix --apply <labels>`. It applies nothing. The
question cites today's `plan.md`; without one it exits 1 and tells you to run
`wuwei doctor --fix` in a host terminal. `--fix --apply <ids>` narrows the batch to those
comma-separated fix ids, with the same preview and digest; an unknown id exits 2.
`--widget` or `--apply` without `--fix`, or both together, exit 2.

## Sessions

Several Claude Code sessions can work in one workspace. Once today's `state.json` exists, the SessionStart, Stop and SubagentStop hooks record each session in the `sessions` registry of day state (role, start, last hook, working directory). No hook creates day state. SessionStart also exports `WUWEI_SESSION_ID` through Claude Code's `CLAUDE_ENV_FILE`, so CLI calls from that session know which session called them. A session with no hook activity for `sessions.stale_seconds` is stale. The registry and claims are written only by these hooks, `plan session`, `brief builder` and `worktree add`.

- `bin/wuwei sessions` prints the registry as JSON: id, role (`planner`, `adhoc`, `seat-host` or `remote`), age, idle seconds, stale, last hook and claimed items. `planner`, `adhoc` and `remote` (a session the control plane started for a Slack command) are set today; nothing sets `seat-host` yet.
- `bin/wuwei plan session <id>` still names exactly one planner. A second session is refused with exit 2 naming the current planner; `bin/wuwei plan session <id> --take-over` hands the role over and records `previous` on the `plan.session` event. Wakes then go to the new planner. When the planner is stale, `nudges` names the take-over command.
- `bin/wuwei brief builder <item> ...` and `bin/wuwei worktree add <item>` claim the item for the calling session. The same commands from another session, or from a host terminal without `WUWEI_SESSION_ID`, exit 2 naming the claimant while it is live. Once the claimant is stale, the next session takes the claim. Gate, sentinel and other briefs are never refused by a claim.

## Seat briefs and the build loop

| Behaviour | Rule |
| --- | --- |
| Brief body | `wuwei brief ROLE ITEM NAME --body TEXT` or `--file PATH`; `--file -` reads stdin. With neither, the command exits 2 and never reads stdin. |
| Gate role names | `arch`, `quality` and `security`, as returned by `wuwei dispatch next`, write briefs against the `sentinel-<role>` charter. A second opinion is named `<role>@<runtime>`; `wuwei dispatch opinion` writes its brief from the first-model brief and receives it as one more gate. |
| Automatic phases | The first `build next` launch moves `planned` to `implement`. When checks pass, `implement` moves to `gate` and `fix` moves to `delta`. `dispatch next` moves `gate` to `fix` when it returns `fix`, and opens the builder's fix round. `bin/wuwei pr raise` moves `gate` or `delta` to `raised`, and `bin/wuwei pr claim` moves `planned` to `raised`; an observed merge (`pr state`, `pr act`, the watch) moves `raised`, `fix` or `delta` to `merged`. |
| Delta continuation | SubagentStop records the sentinel's agent ID on its seat. `dispatch next` returns a `continue` action in `seats` with that ID as `resume`. Agent `resume` with that ID continues the same brief at the current HEAD; any other reuse of the brief is refused. The continued seat rewrites its own verdict file. |
| Push evidence | `wuwei build check ITEM` records fast checks through the same producer as `wuwei fast-checks`, so a passing check satisfies the push guard. |
| Charter names | `lead`, `builder`, `shepherd`, `sentinel-arch`, `sentinel-quality`, `sentinel-security`, `sentinel-goal` or `steward`. Each seat name gets one brief. `runtime dispatch` accepts `arch`, `quality` and `security` for the sentinel roles, as `brief` does. |
| Gate body | A gate body must not ask for an inline verdict or restate the verdict path; the brief adds it. A `Paths:` line lists extra paths for the SLICE protected-path check. |

## Stuck seats

A seat launched in the background ends with the harness's structured hand-back, and its SubagentStop carries no `last_assistant_message`. The hook reads the report from the seat's own transcript (the hand-back's message, or the last assistant turn's text) and every SubagentStop guard sees it, as for a foreground seat. When the report cannot be read, the hook stops the seat with status `unmeasured` and a `reason`, records `seat stopped` with both, and exits 2 naming the recovery command; the seat never stays `running`.

`bin/wuwei seat stop <name> --verdict <file>` records the seat's report from the file through the same SubagentStop guards (a sentinel's file must pass the verdict lint first). `bin/wuwei seat stop <name> --unmeasured "<reason>"` stops it as unmeasured so the day can move; a builder's running build parks with that reason. Under `strict` it is an owner action: answer y at the host terminal. Under `observe` and `guarded` it runs from a host terminal or today's planner session. `bin/wuwei next`, the doctor `stuck seats` row and the heartbeat `seats` probe name it for a running seat whose transcript ends in the hand-back with no stop, and for a seat the hook stopped as unmeasured.

## Item phase order

Phases move by themselves on the daily path. `bin/wuwei state transition` is a [recovery](recovery.md) command and accepts only these moves. `parked` and `escalated` resume only to the recorded prior phase.

| Phase | Legal next phases |
| --- | --- |
| `planned` | spec, implement, raised, parked, escalated |
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

Run `bin/wuwei state recover` in a host terminal. It prints a short snapshot digest and asks y/N, then restores `state.json` from the snapshot under the state lock and appends a `state.recovered` event. The day continues from the last state WUWEI wrote.

| Exit | Meaning |
| --- | --- |
| `0` | State restored from the snapshot. |
| `1` | `state.json` is readable (nothing to recover), or you declined. |
| `2` | No usable snapshot, the snapshot changed during confirmation, or no terminal could ask you. |

Recovery is an owner action. Agent tool hooks refuse `wuwei state recover` inside a workspace and refuse writes to the snapshot. As with other host-only actions, this follows the cooperative hook threat model in spec 9.1.

## Security posture

`bin/wuwei init --posture <name>` writes `security.posture` into a new workspace; `observe` also writes today's date as `guards.shadow_since`, and `--shadow` is `--posture observe`. With `--upgrade` either exits 2. The hook reads the posture only when a guard refused, and per refusal: an `off` area drops it; a `warn` area records a `guard.would_refuse` event and the hook exits 0; a `block` area enforces it and the reason shown gains a line `posture: <area> = block (set security.areas.<area>)`, or `(floor; no setting lowers it)` for `records`, or `(owner-only action; no setting lowers it)` for `deploy`, `pr` and the outward approval tier. A held outward draft reads `posture: outward = block; a draft is one card away` instead: the card sends it, and a tier row lowers it. The `gh pr create` refusal for a missing `--reviewer` names its own ways out (`shepherd.min_reviewers 0`, or `shepherd.reviewers` raised with `bin/wuwei pr raise`, since this guard never reads `shepherd.reviewers`) and carries no posture line; it still blocks. Every other `gh pr create` refusal starts with `pr raise:` and follows `publish`, not owner-only; `-R <org>/<name> --head <branch>` of a recorded item branch, or `cd <recorded worktree> && gh pr create`, runs from any directory. Below `strict`, a call the guards could not read (a script, a substitution, inline interpreter code) warns once with `opaque: <what>` unless its text names a publish target. `hook.refusal` keeps the guard's own reason in `refusals`. A refusal from a guard module with no area (a test stub) blocks with no posture line. The event payload is `{guard, area, level, posture, reason, target, session, item}`: `target` is the normalised Bash command, else the file path, else the tool name, with credentials, the canary and the honeytoken redacted; `item` is the item the session claims, or null. Only the hook and `wuwei pr raise` write it; `bin/wuwei event` refuses the kind. If the event cannot be written, or the config cannot be read, the refusal is enforced. Refusals in the heartbeat session `wuwei-heartbeat` are always enforced.

`status --line` adds the posture name after the nudges when it is not `guarded`, and `status --json` carries `posture`. Under `observe`, once `guards.shadow_days` calendar days have passed since `guards.shadow_since`, `bin/wuwei nudges` and the status line count one `guards.shadow` nudge asking you to set `security.posture = "guarded"` or raise `guards.shadow_days`. With an empty `shadow_since` there is no nudge. Under `guarded` or `strict` a `guard.would_refuse` event is a nudge, one row per guard per day, naming the guard, its reason and `security.areas.<area>`; under `observe` it is silent.

With `security.areas.mcp = "off"`, `bin/wuwei mcp check` exits 0 with `MCP registry: not checked (security.areas.mcp = "off")`, runs no scanner and writes no event, and the launch gate passes. A non-zero launch gate reason names the mcp level and either `floor: scanner.mcp.block` or `security.areas.mcp`.

`bin/wuwei mcp check --widget` runs the check, then prints today's pending registry decision as a JSON list with one AskUserQuestion widget. The `proceed` description adds one line per server with today's finding counts by severity since the last `proceed` (server names and severities only, never scanner text). `record` is `wuwei mcp decide D-<n> <label>`, the command that records the answer. With nothing pending, or a pending record from an earlier day, it prints `[]`. `mcp decide --widget` is a usage error.

## Why

`bin/wuwei why <target>` reads the day records and prints why something is where it is. It writes nothing. The target is, in this order: `last refusal`, an event id, a decision id `D-<n>`, a PR ref `owner/repo#<n>`, or an item name.

An event id is `<YYYY-MM-DD>:<line>`: the day directory and the 1-based line of that day's append-only `events.jsonl`.

For an item, `why` reads every day whose `state.json` holds it, oldest first, and prints one line per step in this order: how it entered the queue (goal and score), its gate tier and the rules that set it, each gate verdict with its blocking findings, each decision with who decided it, each phase change with the command that made it, the merge with the policy evidence that cleared it, and what it waits on now. A PR ref reads the item that links it. A step with no record prints `not recorded`, never a guess. The queue entry, the tier and the gate verdicts are always listed; the merge is listed for a merged item.

For a refusal, `why` prints the guard, the rule, the normalised command and the fix. The `hook.refusal` payload is `{reason, refusals, target}`: `refusals` holds one `{guard, reason}` per enforced guard, and `target` is redacted as for a warning. The rule is the message before its first `; ` and the fix is the text after it. Refusals recorded before this field existed print `not recorded` for the guard and the command. A `guard.would_refuse` event is explained the same way, from its `guard`, `reason` and `target`, under `would have refused (shadow) at <ts>`, followed by `posture: <area> = <level> (<posture>)` when it names an area; `last refusal` is the newest of either kind.

For a decision, `why D-<n>` reads today's record and prints the options with their scores, the recommendation, the weights, the margin (the recommended score minus the best other score, over 10 times the sum of the weights), the class, the cruise level and who decided. Cruise mode is not built yet, so the class and level print `not recorded` unless the record or its event names them. An owner answer records `decided_by: owner` in its `decision.decided` or `decision.reversed` event.

Lines follow `owner.verbosity.report`. At `full`, or with `--full`, each line ends with its event id and evidence paths. Every line is redacted as refusal targets are, so a credential in a record never reaches the output. The `wuwei_board` tool returns the same item chains in `./why.json`, or `{"unmeasured": <reason>}` when a record cannot be read.

Exit 0 prints the view, 1 means the target has no record, 2 means a record could not be read or there is no workspace.

## Host terminal actions

These are owner actions. Agent tool hooks refuse them inside a workspace, so run them yourself in a host terminal:

| Command | Asks y/N |
| --- | --- |
| `bin/wuwei decide D-<n> <option> [--note <text>]` (the planner records a decision it asked in the session, outside strict) | yes |
| `bin/wuwei decision outcome D-<n> <option>` | yes |
| `bin/wuwei state recover` | yes |
| `bin/wuwei integrity reconfirm` | yes |
| `bin/wuwei mcp decide D-<n> <option>` and `mcp decide proceed-unmeasured <server>...` | yes |
| `bin/wuwei drafts approve <id>` | yes |
| `bin/wuwei drafts drop <id>` | no |
| `bin/wuwei grants revoke <n>` | yes |
| `bin/wuwei goals edit` and `voice edit` (the planner may record what the morning gate approved with `--file`, outside strict) | no |
| `bin/wuwei watch uninstall` | no |
| `bin/wuwei listen uninstall` | no |
| `bin/wuwei remote ack` | yes |
| `bin/wuwei config promote` | yes |
| `bin/wuwei config set <key> <value>` | yes |
| `bin/wuwei config add-repo --name --path --branch` | yes |
| `bin/wuwei setup` | yes |
| `bin/wuwei memory forget F-<n> apply` and `memory forget F-<n> keep` (apply asks) | yes |
| `bin/wuwei telemetry send [<week>]` | yes |

A command that asks y/N shows what it confirms and reads the answer from `/dev/tty`; anything but y or yes declines. Without a terminal it changes nothing and exits 2 with `this is an owner action: run it in a host terminal`. From outside the workspace, set `WUWEI_WORKSPACE=<path>` or put `--workspace <path>` first, as in `bin/wuwei --workspace <path> decide D-1 A`. `drafts approve --edit`, `goals edit` and `voice edit` open `EDITOR`. As with other host-only actions, this follows the cooperative hook threat model in spec 9.1.

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

A hook process starts an interpreter, imports the CLI core, discovers the guards, then runs the ones that match its event and tool. `bin/wuwei` starts it with `python3 -I -P -S`: `-S` skips the `site` import, which a stdlib-only CLI with its own import paths does not need. Hook and `status --line` processes also run without the cyclic garbage collector and leave through `os._exit` once their output is flushed and any `atexit` handlers ran, which skips the interpreter teardown. Each hook imports only the guard modules its event and tool can run (`MODULES` in `cli/wuwei/guards/__init__.py`); a guard module missing from that map is imported for every event. Stop and PostToolUse never import the Bash guards, and a PreToolUse call for a file tool imports only the file guards.

The CLI keeps the validated `config.toml` as JSON in `.wuwei/generated/config.cache.json`, with its unknown-key warnings. A copy is used only when it was made from the exact text of `config.toml`, by the same plugin version and cache layout; then a hook or the status line never imports `tomllib`. Any other text is parsed as before; a hook or the status line then rewrites the copy, so the first such call after an edit or a plugin update writes it and later calls only read it. Other commands read a current copy and never write one. Deleting the file changes nothing but the time of the next call, and seats cannot write it (it is under `generated/`). At SessionStart the integrity guard and the session guard run together, so the Git and `ssh-keygen` children and the record writes of one overlap the work of the other; a day without decision routes reads its events once.

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
