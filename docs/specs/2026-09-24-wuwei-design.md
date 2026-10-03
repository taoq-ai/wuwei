# WUWEI 无为: design

- Status: PROPOSED, owner questions resolved 2026-09-24
- Date: 2026-09-24
- Owner: TaoQ AI Labs
- License: Apache 2.0
- Scope: v1 of a Claude Code plugin

无为 (wuwei) means "effortless action": the work gets done without forcing it. WUWEI is a
Claude Code plugin that runs a chartered team of agents through a solo engineer's or
architect's day, with guards that make the safe path the default one. It is distilled from a
harness run in production for a month on a multi-repository delivery; nothing specific to
that engagement ships in this repository.

## 1. Goals and non-goals

### Goals

- G1. One person runs a team of agents that plans, builds, reviews and shepherds work across
  several repositories, finds new work against the owner's goals throughout the day, and
  asks the owner only for decisions cruise mode does not answer (5.8.1), work outside the
  goals, and merges the merge policy does not clear (4.6).
- G2. Guards enforce the rules at the moment of action. A rule that can be broken without a
  refusal is not a rule.
- G3. Security first: agent tool permissions are least-privilege and audited, live sessions
  are checked for dangerous tool sequences, and items that build agents are gated by an
  agent security scanner (ZIRAN by default).
- G4. Memory that outlives the session: episodes, procedure and settled facts, each with one
  home, one writer and a consolidation cadence.
- G5. Works with only `git`, `gh` and `python3`. Every other integration is an optional
  adapter.

### Non-goals

- Deploying. No profile, routine or command deploys, releases or promotes anything to an
  environment (section 4.7). Owner decision 2026-09-28; supersedes the earlier non-goal that
  merging was always a human act.
- Approving pull requests, or bypassing branch protection to merge. WUWEI never approves a
  review and never merges with admin override; a merge happens only when the repository's
  own rules already allow it (section 4.6).
- A hosted service or database. A long-running process is out of scope for v1; M5 adds
  exactly one, the listener (section 15).
- Multi-user team coordination (v1 is one person's workspace).
- Replacing the tracker, chat tool or CI. Adapters talk to them; WUWEI does not own them.
- Runtime guardrails for production agents (use a guardrail product) or LLM evaluation.

## 2. Context and constraints

- Runs inside Claude Code. Roles ship as plugin agent types; hooks fire on their tool calls.
- A second runtime (Codex) is supported through an adapter that dispatches the same charter
  by file path. Codex sandboxes have no network and cannot reach an MCP server, so every
  guard and state change is a CLI, not an MCP tool.
- Stdlib Python only at runtime. No package install beyond the plugin itself. Language
  decision (owner, 2026-09-28): Python stays. Measured on the owner's machine, the
  interpreter starts in about 17 ms and Node in about 18 ms, so TypeScript buys no speed; a
  Rust binary would save about 35 ms per tool call at the cost of per-platform binaries and
  a rewrite. The hook path carries a latency budget instead: `wuwei hook` p95 under 50 ms
  (10.6). If the budget is broken, only the hook dispatcher is a candidate for a compiled
  rewrite.
- The CLI is invoked only through `bin/wuwei`, which unsets PYTHONEXECUTABLE and runs
  `python3 -I -P` with explicit plugin import paths (owner decision, 2026-09-28).
  Isolated mode ignores PYTHON* settings except PYTHONEXECUTABLE on macOS, excludes user
  site-packages and the working directory from import paths. Explicit -P enforces Python
  3.11+. PATH remains trusted for interpreter selection.
- Writing style for everything the plugin authors: no emojis, no em-dashes.

## 3. Architecture

### 3.1 Repository layout (EXISTING: none; everything below is PROPOSED)

```
wuwei/
  .claude-plugin/plugin.json
  .claude-plugin/marketplace.json
  agents/            9 role agents, generated from charters/, each with a tool allowlist
  skills/            wuwei-init, wuwei-plan, wuwei-report, wuwei-retro, wuwei-consolidate
  hooks/hooks.json   shims that call the CLI and nothing else
  charters/          _common.md, _common-authoring.md, one file per role
  cli/wuwei/         stdlib Python package, entry point `wuwei`
  adapters/
    tracker/         none (default), linear
    chat/            none (default), slack
    review_bot/      none (default), greptile
    runtime/         claude (default), codex
    scanner/         none (default), ziran
    code_host/       github (default, through `gh`), none
    vcs/             git (default)
  templates/         workspace skeleton, dashboard.html
  tests/
  docs/
  .github/workflows/ tests, ziran agent audit, release
```

### 3.2 Components and responsibilities

| Component | Does | Depends on |
|---|---|---|
| Charters | Define each role's conduct as ordered checklists. Source of truth for agents. | nothing |
| Agents | Charter as system prompt plus a tool allowlist. Generated at build time. | charters, allowlist file |
| Skills | Entry points the user types. Orchestrate; never write state directly. | CLI |
| Hooks | Map Claude Code lifecycle events to CLI guard calls. | CLI |
| CLI | The only writer of workspace state and the only home of guards, sweeps, index and metrics. | stdlib, ports |
| Adapters | Fixed interfaces to external systems, each with a `none` default. | the external tool |

Rule: a behaviour lives in exactly one CLI function with one test. Hooks, skills and seats
call it; none reimplement it.

### 3.3 Workspace

Created by `/wuwei init`. One workspace per body of work, spanning any number of repos.
Code repos receive only worktrees, branches and pull requests.

```
.wuwei/
  config.toml          repos, adapters, CAP, host floors, gate profile, boundary and
                       environment register, outward-text rules
  charters/            local overrides layered over the plugin charters
  memory/
    spine.md           the structural model, loaded in full every session
    goals.md           the owner's goals (5.7); edited only by the owner
    voice.md           the owner's voice per audience (4.8); edited only by the owner
    index.md           generated; one line per note and per past day
    notes/*.md         settled facts with frontmatter
    archive/           retired notes; moving one back revives it
    ledger.jsonl       append-only: every promoted or rejected change, with evidence
    CHANGELOG.md       every dated rule change, verbatim; never loaded by seats
  days/YYYY-MM-DD/
    plan.md  state.json  events.jsonl  traces.jsonl
    briefs/  decisions/  deliverables/  retro/  proposals/  report.md
  archive/             days older than 30, summary lines kept in the index
```

### 3.4 Three-state exits

Every guard, sweep and adapter call returns one of: `0` clean, `1` findings, `2` could not
run. Exit 2 blocks exactly like exit 1 and prints why. An absent adapter or scanner reports
"unmeasured", which the report shows as such and never counts as clean.

### 3.5 Ports and adapters (owner, 2026-09-28)

WUWEI is built as ports and adapters (hexagonal).

- Core: `cli/wuwei/`. Guards, sweeps, the state writer, policies (merge, deployment,
  decisions, ranking), memory, metrics. The core never runs an external tool and never
  parses a vendor's output format; it calls ports and receives plain data (dicts, lists,
  the shared `(exit, data, reason)` result).
- Driven ports, one per external concern, listed in section 8. A port is a named set of
  functions with fixed parameters, declared once in the registry; there is no abstract base
  class. Every port has a `none` adapter (or a fake for ports that must answer, such as
  `vcs`) and a contract test that every adapter under `adapters/<port>/` satisfies.
- Driven adapters: `adapters/<port>/<name>.py`. The only code that runs `gh`, `git`,
  `ziran`, `claude`, `codex`, `signal-cli` or talks HTTP. An adapter turns an error body
  into exit 2 (section 9) before anything reaches the core.
- Driving adapters: `hooks/hooks.json` with `wuwei hook <event>` (Claude Code lifecycle),
  the `wuwei` command line, `skills/` (typed entry points), and in M5 the listener and its
  inbound and control-plane parsing. Each translates its input into one core call and its
  result into the caller's format. None holds a rule.
- Tests: the core is tested against fake adapters and recorded fixtures, never against the
  real tools or the network; adapters get contract tests plus recorded-output tests.

## 4. Guards

### 4.1 Hook table

| Event | Trigger | Refuses when |
|---|---|---|
| PreToolUse | `Agent` launch | no brief logged for it; a gate seat while its item's builder is live or its tree is dirty; running seats at CAP or free memory below the configured floor |
| PreToolUse | `git commit`, `git push` | author or committer differs from repository config; force-push; push to the default branch; push before the fast checks passed |
| PreToolUse | `gh pr create` | the pre-PR gate set has not all passed; no reviewer named in the same action |
| PreToolUse | `gh pr merge` | the merge policy (4.6) does not clear this PR at this head |
| PreToolUse | `gh pr review --approve`, `--admin`, protection changes | always |
| PreToolUse | any deploy action (4.7) | always |
| PreToolUse | chat or tracker adapter call | outward-text lint fails; a technical claim, disagreement or scope statement without an approved draft |
| PreToolUse | Write or Edit on `state.json`, `events.jsonl` | always; state changes go through the CLI |
| PreToolUse | top-level `cd` out of the workspace | always; use `git -C` or a subshell |
| PostToolUse | any tool | never refuses; appends the call to `traces.jsonl` in OTel JSONL shape |
| PostToolUse | write to `decisions/gate-*.md` | verdict lint fails; the verdict is returned to the seat |
| SubagentStop | a seat finishes | its three-line retro note is missing; otherwise records it, flagging a last message that asks the owner a question without a decision id (5.8) |
| SessionStart | new session | never refuses; prints the memory payload and its size, flags a dead watch process and orphans from the last close |
| PreCompact | before summarising | never refuses; flushes pending state and events |
| Stop | every planner turn end (4.2.1), and day close | any owned PR has an overdue action; at day close also reply or visibility obligations owed, or the retro did not land |

### 4.2 Sweeps

Run by the watch process every two hours, written to `events.jsonl` as `watch: sweep`:
reply obligations (every open PR, three comment surfaces, fail-closed acknowledgement
ledger), PR visibility (reviewer requested, channel post logged with reviewer mentions,
verdict recorded), staleness (no commit and no report for 15 minutes), and the scanner over
the day's traces. The watch writes a clock line every 10 minutes; a missing clock line is a
failure signal.

#### 4.2.1 PR ownership loop (owner, 2026-09-28)

The shepherd owns every PR the day raised or claimed until it is merged or the owner parks
it. Ownership is enforced by three mechanisms, none of which depends on the model remembering:

- State from absolute state. `wuwei pr state` computes one current state per owned PR from the
  code host, never from memory: `conflicted` (not mergeable against its base), `ci_red`,
  `changes_requested`, `threads_unanswered` (the reply obligations above), `review_stale`
  (awaiting review past `pr.review_window`), `approved`, `merged`. Each state names its
  required action and a deadline (`pr.action_minutes`, default 30):
  - `conflicted`: rebase in the item's worktree, resolve, run the fast checks, push;
  - `ci_red`: a fix round in the item's worktree;
  - `changes_requested` and `threads_unanswered`: triage each thread: a fix request becomes a
    fix round, a question gets a reply (auto-send tier for team PR threads, 4.9), a
    disagreement or scope change becomes a decision for the owner (5.8);
  - `review_stale`: re-request review, then post in the review channel;
  - `approved`: `wuwei merge` when the policy clears it (4.6), otherwise a merge decision;
  - `merged`: done.
  An overdue action is a `nudge`, then a `page` at twice the deadline (5.9).
- Wake outside the model. The watch process polls owned PRs every `pr.poll_seconds` (default
  120; head, CI, mergeability, reviews, comments, threads) and, on any change, records a
  `pr.changed` event and wakes the planner session (and, in M5, launches a headless shepherd
  run). Nothing needs to be re-armed by a seat.
- Anchor at every turn. The Stop hook refuses to end a planner turn while any owned PR has an
  action past its deadline and no decision record parking it, naming the PR, its state and the
  action. The day close additionally requires every owned PR merged, parked or explicitly
  carried to the next day.

The cockpit shows one row per owned PR: state, last action, what it waits on and time to
deadline, so the owner never checks PRs one by one.

### 4.3 Outward-text lint

Configured in `config.toml`: the owner's name and pronouns (never used in third person in
text sent as the owner), patterns that reveal the routine's internal state (drafts pending,
queues, which agent wrote what), banned characters, and a maximum length per channel. The
lint also applies the mechanical checks of the owner's voice for the message's audience
(4.8).

### 4.4 Profiles

- `strict` (default): every guard above blocks.
- `standard`: the outward-text lint warns instead of blocking. The merge policy, the
  approve refusal and the deployment ban are unchanged.

### 4.5 Matching and bypass resistance (owner, 2026-09-28; amended 2026-09-30, #237)

A guard that matches the literal command string is bypassed by wrapping the command. Every
Bash guard therefore matches after normalising: unwrap `sh -c`, `bash -c`, `zsh -c`, `env`,
`command`, `exec`, `xargs` and subshells; resolve `git -C`, `git -c` and `GIT_*` environment
overrides; treat `gh api` calls against the merge, review, branch-protection and
deployment endpoints as the commands they implement. An interpreter one-liner (`python -c`,
`node -e`, `perl -e`) or a script whose text invokes `git` or `gh` with a guarded verb is
refused as opaque. Each bypass form is a test case in the guard's table.

What the normalisation guarantees depends on what the guard protects (9.1):

- The plugin's own records (state, events, generated instructions, and the owner-only
  commands that write them): the parser is the only local check, so normalisation and the
  bypass table stay the defence here.
- Publishing actions (push, merge, deploy, PR approval): the guard refuses clearly what it
  can recognise, but the guarantee comes from the code host and the credential layout, not
  from the parser: a protected base branch with required checks, and no token in seat
  environments that can approve, release or deploy. `wuwei init` documents that layout and `wuwei config check` verifies
  it for each configured repository. The `pre-push` git hook in WUWEI worktrees and the
  `permissions.deny` rules `wuwei init` writes (approve, `--admin` merges, the deploy
  commands in 4.7) are further local checks, not boundaries.

A narrow argv allowlist may be used for privileged publish actions only (for example the
exact `gh pr merge --squash --match-head-commit <sha>` that `wuwei merge` issues, 4.6). A
positive allowlist for all development commands is rejected: allowing an interpreter or the
test runner allows arbitrary code, so it would add refusals without adding a guarantee.

### 4.6 Merge policy (owner, 2026-09-28)

WUWEI may merge a pull request when the policy clears it; otherwise the merge is a decision
for the owner. The policy is one CLI function, `wuwei merge check <pr>`, used by the merge
guard, the shepherd and the report; `wuwei merge <pr>` runs the check and merges in one step.
In decision terms this policy is the `merge` class of cruise mode (5.8.1) at L2 or L3, with
the conditions below unchanged.

Eligibility, per repository in `config.toml` (default off):

- `merge.auto = true`, and `merge_deploys = false` declared explicitly. A repository whose
  merge to the base branch triggers a deployment, or that does not declare it, is never
  auto-merged: for it, merging is deploying (4.7).
- The item carries none of `trust_surface`, `boundary_relevant`, `agent_surface`, and its
  diff touches none of the configured never-auto paths (defaults: CI and workflow files,
  dependency manifests and lockfiles, migrations and schemas, infrastructure code,
  `CODEOWNERS`, anything under a `deploy` or `infra` directory).
- The diff is at most `merge.max_changed_lines` (default 400) and the item went through at
  most the negotiation budget (5.3).

Preconditions, all read fresh at the current head sha, never from cache or from
`state.json`:

- every pre-PR gate verdict is PASS for this head, and no finding with `blocks: yes` is open;
- every required status check is green (a skipped or neutral required check is not green);
- the repository's own branch protection is satisfied without override: required human
  approvals present from people other than the author, no changes requested outstanding;
- every review thread is resolved or answered, and the reply and visibility obligations
  (4.2) for this PR are clear;
- the review bot, when configured, reports no open blocking finding on this head;
- the branch is up to date with its base, or the repository uses a merge queue;
- a soak window has passed since the last approval or push (`merge.soak_minutes`, default
  30), during which the owner can veto from the control plane.

Mechanics: `gh pr merge --squash --match-head-commit <sha>` (or the repository's merge queue),
so a push between the check and the merge makes it fail rather than merge unreviewed code.
Never `--admin`, never a change to branch protection, never an approval. At most
`merge.max_per_day` auto-merges per repository (default 5); none during quiet hours.

After the merge: the watch follows the base branch's checks for the merge commit. A red check
opens a revert PR at once, pages the owner, and trips the breaker. Every merge is an event
carrying the evidence (head sha, verdicts, checks, approvals) and an undo-log entry whose undo
is the revert PR.

Circuit breaker: auto-merge turns off for a repository, until the owner turns it back on,
when a merged PR is reverted or red on the base branch, or when the rolling 14-day escaped
defect rate for auto-merged PRs (5.6) exceeds the owner's baseline. Any precondition that
cannot be read is exit 2: not cleared, so the merge goes to the owner.

### 4.7 Deployment ban (owner, 2026-09-28)

WUWEI never deploys, in any profile, routine or remote command. Refused always, after the
normalisation in 4.5: dispatching or re-running a workflow the config marks as deploying,
`gh release create` and tag pushes, pushes and merges to branches in the configured
environment register (for example `production`, `release/*`), GitHub deployment and
environment API calls, and the deploy commands of common tools (`kubectl apply`, `helm
upgrade`/`install`, `terraform apply`, `pulumi up`, `vercel`/`netlify` deploy, `fly deploy`,
`gcloud`/`aws`/`az` deploy verbs, `docker push`), extendable by `deploy.deny` in config. A
merge into a repository with `merge_deploys = true` is a deployment and goes to the owner.

### 4.8 Voice (owner, 2026-09-28)

Everything sent as the owner (chat posts, PR comments and replies, tracker comments, digests,
responder drafts) is written in one voice, so the owner reads as one consistent person.

Home. `memory/voice.md`, owned by the owner like `goals.md`: seats and the steward propose
changes (6.8) and the owner approves them at the morning gate. One profile per audience
(`internal`, `external`, `review`, `tracker`, plus any named channel from config), each with
register, length target, structure (for example answer first, one ask per message), phrases
the owner uses, phrases the owner never uses, and 5 to 10 exemplars of the owner's real
messages with personal data redacted. A shared `never` list holds machine tells (stock
openers and closers, hedging preambles, summary sign-offs, filler praise). The profile stays
in the workspace, never in this repository.

Learning. `wuwei voice learn` reads only the owner's own sent messages and PR comments
through the chat and tracker adapters, read-only, and writes a proposal for each audience.
Every draft the owner edits before sending is recorded as a before and after pair; the
steward turns repeated edits into voice proposals, so the profile converges on the owner.

Enforcement. Seats that write outward text (shepherd, planner digests, responder) load the
profile for the audience. The outward-text lint (4.3) checks what is mechanical: length,
`never` phrases, required structure, banned characters. Tone cannot be linted, so under
`strict` every message that is not mechanical stays a draft the owner approves (the
approved-draft rule), and the draft shows which profile it was written against.

Disclosure. `voice.disclosure = "none" | "footer" | "per-channel"` (default `per-channel`:
`none` on internal channels, a short footer marking agent-sent messages on external ones).
Substantive claims, disagreement and scope statements are always the owner's own, through the
approved-draft rule, whatever the disclosure setting.

Metrics (steward): share of drafts sent without edit, and the size of the owner's edits to the
rest, per audience. Both should rise as the voice converges; a fall is a steward finding.

### 4.9 Outbound approval tiers (owner, 2026-09-28)

Every message sent as the owner is either auto-sent or drafted for approval. The tier is
decided by one CLI function (`wuwei outbound tier`) from the channel, the audience and the
message, before the outward-text lint and the voice checks (4.3, 4.8) run.

- Auto-send: channels the owner marks as work channels in config (for example PR and review
  channels, the team engineering channel) and code-host threads on the owner's team's pull
  requests. Covers acknowledgements, status, mechanical answers and technical replies within
  the pull request's own scope. This replaces, for these channels only, the approved-draft
  requirement for technical claims in 4.1 and 4.3.
- Approve: every direct message; every external party (anyone outside the company domains
  and code-host organisations listed in config, shared or connected channels, client
  channels); every sensitive topic in any channel (performance, feedback, compensation,
  hiring, personal or health matters, conflict, legal or HR); and, in any channel,
  disagreement with a person and commitments of scope or time. Drafts go to the control
  plane for approve, edit or drop.
- Precedence: external beats channel; sensitivity is judged per message, and unsure means
  approve. A message that cannot be classified is a draft, never an auto-send.

## 5. The team

### 5.1 Roles

| Role | Seat | Writes |
|---|---|---|
| planner | the user's session | plan, dispatch, receive, sweep, report; state through the CLI |
| lead | per day | ranked discovery with evidence, scope, overlap matrix, track and flags |
| builder | per item | spec and implementation in the item's worktree |
| sentinel-arch | per gate | one verdict file |
| sentinel-quality | per gate | one verdict file, with `Simplicity:` and `Design:` rows (5.3) |
| sentinel-security | per gate | one verdict file; runs the scanner when `agent_surface` is set |
| sentinel-goal | per docs gate | one verdict file |
| shepherd | per PR set | PR raise, reviewer requests, thread replies, obligation ledger |
| steward | at each sweep, at close and every N tool calls, fresh seat | steering notes, the decision queue, the retro and charter proposals |

### 5.2 Flow

```
/wuwei plan -> planner -> lead -> MORNING GATE (user approves or edits)
  -> per item: builder -> pre-PR gates in parallel (arch, quality, security; goal on docs)
  -> shepherd raises, requests reviewers, posts, and owns the PR until merged (4.2.1)
  -> fix round -> arch delta -> ... -> merge policy: auto-merge, or the user merges
/wuwei report -> steward retro -> planner report -> Stop guard
```

Briefs (amended 2026-10-01, #301). Every seat brief carries a mandate block generated from
the item's class levels (5.8.1) and the owner's calibration interview answers: what the
seat decides alone (what the brief, its charter and the engineering standards already
answer), what it decides and records (two-way open questions inside the item, as
assumptions, 5.3; records of classes running at L2 or L3, which cruise mode answers under
5.8.1's conditions or routes to the owner), and what goes to the owner
(one-way doors, the 5.8.1 ceilings, the interview's trust-surface areas and owner-run
commands, records of classes at L0 or L1). It closes with: nothing else is a question. A
seat does not ask what it may decide.

### 5.3 Rules

- Tracks. SLICE (default): no contract, boundary, schema or infrastructure change and under
  about twenty tasks; spec and implementation in one builder session; one gate set at
  pre-PR. FULL: adds a spec-done gate that blocks only on what changes what gets built.
- Flags set by the lead: `trust_surface`, `boundary_relevant`, `agent_surface`.
- Pre-PR gate set: arch, quality and security in parallel on every code item. After the PR is
  open, fix rounds and deltas are arch-only.
- Assume and record (amended 2026-10-01, #301). "When unsure, it is one-way" (5.8) still
  decides reversibility. An open question on a two-way door inside the item (the `approach`
  class while it runs at L2 or L3, 5.8.1; below that, an `approach` record) is not asked:
  the seat takes its recommendation, records it under `Assumptions:` in the item's spec or
  PR body (what was assumed, why, what would overturn it) and continues. Gates review
  assumptions as findings. Only a one-way door, a 5.8.1 ceiling or trust-surface area, or a question outside the item (its agreed
  scope, the queue, a person), becomes a decision record (5.8).
- Negotiation budget (amended 2026-10-01, #301): one fix round plus one delta check per
  gate. Residual non-blocking findings become review notes in the PR body. A trust-boundary
  security finding always blocks. The verdict lint refuses a finding without a failure
  scenario and a verdict without a probe or mutation row. Exceeding the budget is a design
  reconsideration, never another round: the item parks with a decision record stating why
  the approach keeps leaking and what replaces it, agreed with the owner before more code,
  and the reconsideration is recorded in its spec (constitution, Cycle budget).
- A re-gate continues the same sentinel with the delta; a fresh seat only for a lost agent.
- CAP counts running build seats. Host floors (free memory, seat count) come from config.
- Seat policy (model and runtime per role) is set at the morning gate and stored in state.
- Boundary and environment register come from config; the arch sentinel checks against them.
- Verdict shape: a `Verdict: PASS|FIX|PARK|ESCALATE` line; findings with severity,
  `file:line`, failure scenario and `blocks: yes|no`; a probe or mutation line per claim (or
  "not run"); residual risk; the retro note.
- Retro note, every seat: three lines prefixed `Blocked:`, `Gap:`, `Change:`.
- Build loop (owner, 2026-09-28; adapted from ralph-starter). The runtime adapter runs a
  builder seat as a loop rather than a single dispatch: dispatch, run the item's fast checks
  (backpressure), feed failures back into the same seat, repeat until green or until
  `build.max_iterations` (default 8). Each iteration's failing checks are hashed into an
  error signature (check name, failing test ids, normalised error text); the same signature
  in `build.stuck_after` consecutive iterations (default 3) is a stuck loop: the item parks
  with a decision record instead of spending more budget. Progress, not activity, keeps a
  seat running.
- Step loop amendment (owner, 2026-09-29). Claude Code subagents are the primary
  runtime. `wuwei build next <item>` returns one JSON action: `launch` with the shared
  dispatch prompt, `continue` with feedback and the stopped agent identity, `check`
  with the fast-check command, `park` with a reason and valid numbered decision, or
  `done`. The planner executes launch and continue with Agent and check through Bash,
  then asks for the next action. PreToolUse Agent registers the seat; SubagentStop
  records its result and hands the iteration back. Repeated next calls without changed
  state return the same action. The CLI never waits for a Claude seat; the old blocking
  form exits 2 naming `build next`. Codex executes the same actions through its polling
  adapter. Backpressure, signature, stuck and iteration limits, and usage events retain
  their semantics. `host.seats` defaults to four, the default cap plus three gate seats;
  increase it with a custom cap. A ceiling refusal names `host.seats`.
- Cost per iteration (owner, 2026-09-28). Every dispatch records the runtime's reported
  usage (input and output tokens, cost when the runtime reports it, model, duration) as a
  `seat.usage` event per iteration. The steward reports cost per item, per role and per
  day; the M5 budget governor (15.8) enforces caps on the same events.
- Engineering standards (owner, 2026-09-28), carried by the builder charter and checked by
  the quality sentinel: test first (a failing test before the code that passes it); the
  simplest solution that works (build only what the item asks, reuse what the repository
  has, standard library before a dependency, no abstraction with one implementation);
  SOLID where it makes the code smaller or the tests simpler, never as a layer for its own
  sake; clean code (intent-revealing names, small functions with one job, no dead or
  commented-out code, errors handled where they can be acted on); the repository's own
  conventions over general preference. The quality verdict carries a `Simplicity:` row
  (what can be deleted, and what replaces it) and a `Design:` row (SOLID and clean-code
  findings that make the change harder to test or change now); the verdict lint refuses a
  quality verdict missing either row.

### 5.4 When the user is asked

At the morning gate (goals, ranked queue, seat policy); for decisions cruise mode routes to
the owner (5.8.1), one question per decision, recommended option first, pending decisions
batched, pre-triaged by the steward; for work outside the goals or above the auto-start bar
(5.7); for merges the merge policy does not clear. Never for what a seat's mandate lets it
decide (5.2). Otherwise the session is silent, with a
digest at most every two hours that lists the decisions cruise mode answered.

### 5.5 The steward

Outside the dispatch path. Reads `events.jsonl`, verdicts, traces and CLI metrics: fix rounds
per item, hand-backs per PR, time in phase, verdict-lint rejections, decisions reaching the
user per day, build-loop iterations and stuck parks per item, and cost per item, role and day. Writes steering notes the planner must acknowledge, the pre-triaged decision
queue, and the retro. Charter and note changes it only proposes; `wuwei promote` lands them
(section 6.8). Never briefs a seat, never dispatches, never changes item state. A day on
which the steward did not run is a finding in the next plan.

The steward runs at each sweep, at close, and after every `steward.every_tool_calls` tool
calls counted from `traces.jsonl` (default 50), so a busy hour gets a reflection and an idle
one does not.

### 5.6 Outcome metrics (owner, 2026-09-28)

The process metrics above say how the day ran; these say whether the work was good. `wuwei
metrics` computes them from `gh`, `git` and `events.jsonl`, and `/wuwei report` shows each
beside the owner's baseline:

- escaped defects: share of merged PRs followed within 14 days by a revert or a fix
  touching the same lines, counting only PRs with a full 14-day window; the raw count of
  reverts and follow-up fixes is shown beside it
- review rework: human review threads that led to a new commit; mean per PR, median, p90,
  and share of PRs with at least one
- owner intervention: attended minutes per complete weekday, from the owner's Claude Code
  transcripts for the workspace's repositories. Human turns only (no tool results, no
  subagent or system-injected turns); consecutive turns across all sessions less than 10
  minutes apart form one attended stretch, each stretch counted once however many sessions
  overlap it, plus half the cut-off as lead-in. Median, p25 and p75 over the window, with
  the 5 and 15 minute cut-offs shown as the sensitivity band. The same estimator computes
  the baseline, so the comparison is not flattered by a change of method. Optional: an
  input-idle sampler on the owner's machine during the WUWEI period calibrates which
  cut-off matches real keyboard time. Reads timestamps and turn structure only, never
  message text.
- lead time: from the tracker item moving to In Progress (the tracker adapter's `claim`) to
  its first merged PR; median, p75 and p90; creation to merge and PR open to merge as
  secondary figures

The baseline is the owner's hand-run month before WUWEI, recorded once in the workspace at
`memory/notes/baseline.md` (type `reference`), never in this repository. A metric that
cannot be computed reports "unmeasured", never zero.

### 5.7 Goals, discovery and prioritisation (owner, 2026-09-28)

Goals. `memory/goals.md` holds the owner's goals, one block each: id (`G-n`), outcome, measure,
target, date, priority. Only the owner edits it; seats and the steward may propose changes
(6.8) but `wuwei promote` refuses a goal change that the owner has not approved at the
morning gate. The morning gate confirms the day's goals.

Discovery, all day. The lead runs discovery at the morning plan, at each sweep, and whenever
a build seat frees up with the queue below `discovery.min_queue` (default 2). Sources, each
through its adapter and each reporting "unmeasured" when absent: the tracker backlog, red
checks on base branches, review-bot and scanner findings, review threads asking for
follow-up work, regressions in the outcome metrics (5.6), and follow-ups recorded by the
day's own PRs. Every candidate names the goal it serves with evidence, or is marked
`unplanned`; the share of unplanned work is a steward metric. Candidates are deduplicated
against the tracker and the day's items before ranking.

Prioritisation, `prioritisation.framework` in config:

- `wsjf` (default). Each candidate scores, on the Fibonacci scale 1, 2, 3, 5, 8, 13, 20:
  value (to its goal), time criticality (cost of waiting a day), risk reduction or
  unblocking (what it enables or de-risks), and job size. WSJF = (value + time criticality
  + risk reduction) / job size.
- `rice`. Reach (people or systems affected in the goal's period), impact (0.25, 0.5, 1, 2,
  3), confidence (0.5, 0.8, 1.0) and effort (seat-days). RICE = reach x impact x confidence
  / effort.

Either way, ties are broken by goal priority, and every component cites evidence in one
line; the plan lint refuses a candidate with a missing component or citation for the
configured framework. `wuwei rank` computes the order; no seat orders the queue by hand. The
steward calibrates: predicted size or effort against actual cycle time per item, and a
persistent bias becomes a charter proposal.

Intraday starts, `discovery.autostart` in config. In every mode, an item carrying a risk
flag, touching never-auto paths (4.6), or not fitting CAP and the budget goes to the owner.

- `off`: nothing found after the morning gate starts without the owner; every candidate
  joins the next decision batch.
- `strict` (default): a candidate starts when it serves a confirmed goal, is on the SLICE
  track, and ranks above the cut line of the approved queue.
- `goal`: a candidate starts when it serves a confirmed goal and is on the SLICE track.

Anything that does not start joins the next decision batch as a proposed item.

### 5.8 Decision framework (owner, 2026-09-28; amended 2026-10-01, #282 and #301)

Every decision that the owner or cruise mode answers is a record
`days/<date>/decisions/D-<n>.md` in one shape (MADR with a Kepner-Tregoe evaluation); a
two-way open question inside the item is an assumption instead (5.3):

- `Question:` one line; `Context:` what forces the decision, with evidence paths
- `Class:` one of the decision classes in 5.8.1
- `Options:` at least two, one of them doing nothing or deferring
- `Musts:` pass/fail criteria that filter options out
- `Wants:` weighted criteria (weights 1 to 10), each option scored 0 to 10 against each
- `Recommendation:` the option with the highest weighted score among those passing every
  must, with `Confidence: high|medium|low`
- `Reversibility: one-way|two-way`, `Blast radius:` who or what is affected if it is wrong
- `Pre-mortem:` the most likely way the recommendation fails
- `Revisit:` a date or trigger that reopens it
- `Decided-by:` `owner` as written by the seat, or `cruise <class>@L<n>` written by the CLI
  when cruise mode answers it; `Outcome:` once taken

Routing by class. The record's class level and the conditions in 5.8.1 decide whether the
CLI answers it or the owner does; anything cruise mode does not answer goes to the owner.
When unsure, it is one-way.

Enforcement. A PostToolUse decision lint on writes to `decisions/D-*.md` refuses a record
missing any field, with an unknown class, with fewer than two options, or whose
recommendation is not the top passing option by the stated weights (the CLI recomputes the
score). A seat question that is not a decision record is refused, in every runtime: a
PreToolUse guard refuses `AskUserQuestion` and every control-plane escalation that does not
cite a decision id whose record passes the lint, and SubagentStop flags a seat whose last
message asks the owner a question without one (Codex and headless runs). The steward's
metrics add: decisions per day by class and reversibility, share answered by cruise mode,
cruise answers the owner later reversed (each one demotes its class, 5.8.1), owner asks per
item, and unnecessary asks (an owner answer equal to the recommendation: the agreements
5.8.1 promotes from).

#### 5.8.1 Cruise mode (owner, 2026-10-01, #282)

Graduated autonomy per decision class, earned from the ledger and never by imitating the
owner. Each class runs at one level:

- L0 ask: the owner chooses (5.4); the item waits.
- L1 recommend: the recommendation is preselected in the next decision batch and the owner
  confirms or changes it; the item waits.
- L2 notify: the CLI takes the recommendation at once and sends a nudge; the owner can undo
  it with one reply until `undo_minutes` after the nudge reaches them.
- L3 digest: the CLI takes the recommendation at once and lists it in the next digest.

Classes are a fixed list; a new class is an amendment to this section, not config.

| Class | Decides | Default | Ceiling |
|---|---|---|---|
| `approach` | an implementation choice inside the item's agreed scope; an assumption, not a record, at L2 or L3 (5.3) | L2 | L3 |
| `retry` | re-running a failing check | L2 | L3 |
| `park` | parking an item, such as a stuck build loop (5.3) | L2 | L3 |
| `accept-residual` | keeping a non-blocking residual finding as a review note (5.3) | L2 | L3 |
| `defer` | moving an item or a follow-up to a later day | L0 | L3 |
| `scope-cut` | dropping part of an item's agreed scope | L0 | L3 |
| `re-plan` | changing the approved queue | L0 | L3 |
| `dependency-bump` | changing a dependency manifest or lockfile | L0 | L3 |
| `merge` | merging a pull request (4.6) | L3 | L3 |
| `message` | sending or replying to a person; the 4.9 tiers are unchanged; an external confirmation holds no reversible work (5.8.2) | L0 | L1 |
| `other` | anything no class above covers | L0 | L1 |

The L2 defaults are the two-way, inside-the-item decisions seats took on their own before
cruise mode. `[decisions.cruise]` in `config.toml`: `enabled` (default true), `margin`
(default 0.2), `max_per_day` (default 20), `undo_minutes` (default 60), and
`levels.<class>`, which only lowers a class. The config check refuses an unknown class, a
level outside 0 to 3, or a level above the class's ceiling. The running level lives in
`memory/cruise.json`, starts at the default, and is written only by `wuwei promote` (raises
with ledger evidence and morning-gate approval, lowers at once). A class runs at the lowest
of the running level, the config level and the ceiling.

Conditions. The CLI answers a record only when all hold: the class runs at L2 or L3;
`Reversibility: two-way`; `Blast radius:` is `own branch`, `own PR` or `workspace`; the
margin, the recommendation's weighted score minus the best other option's, passing its musts
or not, over the maximum possible score (10 times the sum of the weights), is at least
`margin`, computed with the owner's weights from the calibration interview where they exist; fewer than `max_per_day`
records were answered this way today; and no ceiling applies. Otherwise, a thin margin or
an unreadable field included, the record goes to the owner, at L0 when the class runs at L0
and at L1 above it. The CLI writes `Decided-by: cruise <class>@L<n>` into the record, and
the `decision.decided` event, written only by the CLI, names the same rule.

Ceilings. Whatever the config says, these stay at L0 or L1: messages to people; scope
agreed with other people; deploys (never made, 4.7) and merges to a repository whose base deploys (4.6); trust-boundary
findings (a record whose context cites a security finding); anything one-way; anything
outside the item's goals (an `unplanned` item, or a change to a goal). The Ceiling column
carries the class ones; the rest are checked on every record.

Merge. The `merge` class answers only where `merge.auto = true` and the merge policy clears
the merge; the policy's eligibility, preconditions, soak window, daily cap and breaker
replace the other conditions above, unchanged; the ceilings still apply. Auto-merges do
not count toward `max_per_day`. At L3 (the default, and the behaviour before cruise mode) an auto-merge
appears in the digest; at L2 a nudge also goes out when the soak window opens; at L0 or L1
every merge goes to the owner.

Promotion and demotion. The steward proposes raising a class one level through propose and
promote (6.8) after 10 agreements and no reversal in that class over 14 days; an agreement
is an owner answer equal to the recommendation, or a cruise answer whose undo window closed
without an undo. `wuwei promote` lands a raise only when the owner approved it at the
morning gate, and never above the ceiling. The CLI lowers a class one level at once,
without approval, on a reversal (an undo, or a later owner answer that differs from a
cruise answer), on an escaped defect (5.6) in a PR whose item carries a cruise answer of
that class, or on three thin-margin escalations in a row in that class; it lands the change
through the promote writer and the ledger line records why. Once a week the steward
re-asks the owner one cruise-answered record per class from the past seven days, with the
answer hidden; a different choice counts as a reversal.

Kill switch. `decisions.cruise.enabled = false` runs every class at L0 without changing any
running or configured level, so turning it back on restores them. The status line (5.9) then
shows `cruise off | L<max>`, the highest level a class would run at, and `cruise L<max>`
while it is on.

#### 5.8.2 External waits and negotiation loops (owner, 2026-10-01, #301)

External confirmation. A confirmation from a person outside the loop (anyone but the owner
and the seats: a client, a stakeholder) is never a precondition a seat may impose. The
question becomes a `message` record (a draft the owner sends, 4.9; ceiling L1); the item
carries `assumption: external` with the recommended reading, and reversible work on it
continues. Time box: when `decisions.wait_hours` pass without an answer (default 24,
counting weekday hours in `owner.timezone`, one working day), the watch sweep (4.2) confirms
the item's `assumption: external` reading (the draft stays unsent with the owner, 4.9) only
when that reading is two-way and no other 5.8.1 ceiling applies (scope agreed with other
people, trust boundary, outside the goals); otherwise it parks the item with a decision
record; either way the CLI writes an event.

Negotiation loops. At each steward run (5.5) the CLI counts, per item over the last
`steward.loop_window_hours` (default 4): decision and clarification records naming the
item, gate verdicts on it, re-dispatches of a role already dispatched on it, and fix-round
continuations (gate or PR feedback, not the build loop's fast-check backpressure, which 5.3
bounds). A sum above `steward.loop_threshold` (default 9), or a second fix round at any
gate, is a negotiation loop: one `negotiation.loop` event per item per day, written only by
the CLI, naming the counts and the last two exchanges. It is a nudge, and a page when the
item is past the date of the goal it serves (5.7); the control plane sends the owner's DM
the same summary within `control_plane.content` (15.4); the status line shows `loops N`.
The signal reports; the negotiation budget (5.3) is what stops the rounds.

### 5.9 Cockpit, signals and briefings (owner, 2026-09-28)

The owner should not need to ask for status. State is pushed to three surfaces, and
attention is demanded only for what matters.

Signals. Every event is classified once by `wuwei signal classify` into a delivery tier and
an owner lane. Tiers: `page` (interrupt now, even in quiet hours: the day is blocked, a
security finding fired, a base branch went red after an auto-merge, an owner decision
blocks a running item, a negotiation loop on an item past its goal date, the dead-man switch
or the budget cap hit), `nudge` (shown at the next glance, batched to the phone at most every
two hours: an owner decision not yet blocking, an L2 cruise answer (5.8.1), a negotiation
loop (5.8.2), a merge the policy does not clear, work outside the goals, budget
at 80 percent, a person's ask nearing its reply window), `silent` (visible, never pushed:
normal progress, L3 cruise answers, auto-merges that went well). Lanes: Work (items by phase),
Decisions (waiting on the owner), People (asks owed by the owner, 15.10). An event the
classifier cannot read is a `nudge`, never `silent`.

Surfaces, all reading the same classification:

- Status line. `wuwei status --line` for the Claude Code status line: one line with pages,
  nudges, items per phase against CAP, the next person reply due, the next meeting, the
  cruise level (5.8.1) and the day's negotiation loops (5.8.2). It shares the hook latency
  budget (10.6) and shows `WUWEI ? unmeasured` rather than a false green when it cannot read state.
- Cockpit. The dashboard (#28) grows into the three lanes plus the briefing pack, served on
  127.0.0.1 and opened in the desktop app's browser pane or any browser. Approving a
  decision or a draft from the cockpit calls the CLI, so every guard applies. Passive
  otherwise.
- Menu bar (optional adapter). `wuwei status --json` feeds a SwiftBar plugin script shipped
  in `templates/`: a green, amber or red mark visible when the app is in the background,
  with the pages and nudges in its menu. macOS only; absent when SwiftBar is not installed.
- Phone. Pages at once and nudge digests through the control plane (Remote Control push by
  default, messaging adapters in M5), plus the briefing pack and approvals.

Briefings. A routine produces a pack before each calendar event that has attendees (lead
time in config) and once a day:

- audio brief of five minutes or less with chapters, through the `tts` port;
- one visual of what changed since the last brief, highlighted, plus an optional deep dive
  per topic for when the owner wants to go further;
- a meeting card: three glanceable bullets (key facts, the one thing the owner will likely
  be asked) for use during the meeting;
- a defend drill: three questions the meeting is likely to raise, hardest first, answered
  by voice or text, with immediate feedback and a streak; scores are a steward metric (is
  the owner staying on top of the work).

Every brief has the same fixed shape (headline, what changed, what is decided, what is at
risk, what you will be asked), arrives at predictable times, and leads with the most
interesting or contentious point. `brief.style` in config tunes length, speed, order and
which parts are on. Sources: events, verdicts, decision records, memory, the calendar and
meeting transcripts through their ports.

## 6. Memory

### 6.1 Kinds

| Kind | Home | Loaded | Writer |
|---|---|---|---|
| Working | `days/<date>/state.json`, `events.jsonl` | on demand by the planner | CLI |
| Episodic | `days/<date>/` | by summary line in the index | planner, steward |
| Procedural | charters, `memory/CHANGELOG.md`, `memory/ledger.jsonl`, guards | charter as system prompt; changelog and ledger never | `wuwei promote`, from steward proposals |
| Semantic | `memory/spine.md`, `memory/notes/` | spine in full, notes by index | any seat: `wuwei note` creates, `wuwei promote` changes |

### 6.2 Frontmatter contract

Every note declares `type` (hub, reference, decision, person, question), `summary` (one line,
present tense, current state), `aliases`, `status` (active, archived). The summary is the
only thing loaded by default.

### 6.3 Index and payload

`wuwei index` writes `memory/index.md`: one line per note with summary and estimated token
cost, one line per past day. Session start loads spine, index and today's state, and prints
the payload size.

### 6.4 Memory lint (session start)

- summary older than the newest date in its own body
- note over its line cap
- state note accumulating dated entries (turning into a log)
- raw intake with nothing routed out of it
- a note past probation that was never loaded (archive candidate, section 6.8)

### 6.5 Routing

A decision goes to a decision note only if someone will later ask why the system is shaped
this way. A world fact goes to the spine or a note, never only to a ticket. A lesson about
how to work goes to a charter through a steward proposal and `wuwei promote`, never to a log.

### 6.6 Consolidation

Daily: the steward folds the retro into charter proposals at close, `wuwei promote` lands
them, and the Stop guard verifies they landed. Weekly: `/wuwei consolidate` as a scheduled
task finds contradictions, near-duplicates and stale summaries across notes and local
charter rules, folds duplicates under one survivor, and archives days older than 30. It
snapshots `memory/` and `charters/` before it starts, since a fold is the one change a
rename cannot undo.

### 6.7 Claude's own memory

Holds user preferences and working style only. Workspace facts stay in the workspace, so
nothing mixes across workspaces.

### 6.8 Self-maintaining procedure (owner, 2026-09-28)

Mechanisms adapted from autoharness (tigerless-labs/autoharness, MIT), applied to charters
and notes rather than to Claude skills, so procedure keeps one home.

- Propose, then promote. Seats and the steward never edit a charter override or an
  existing note directly; they write a proposal to `days/<date>/proposals/` (target, action
  `add`, `patch`, `fold` or `archive`, the new text or delta, reason, evidence path).
  `wuwei promote` is the single writer: it lints the proposal and lands it by atomic
  rename, or rejects it with the reason.
- Promote lint: the target is WUWEI-authored (a local override in `.wuwei/charters/`, a
  note, or one class's running level in `memory/cruise.json`, 5.8.1), never a plugin charter or a user file; a rule body
  stays under its line cap; the evidence path exists; an `add` that duplicates an existing
  rule is rejected in favour of a `patch` of that rule; a lesson that contradicts an
  existing rule must rewrite that rule in the same proposal; a `fold` names a live survivor.
- Ledger. Every landed or rejected proposal appends one line to `memory/ledger.jsonl`:
  target, action, reason, evidence, date. `memory/CHANGELOG.md` stays the human-readable
  record; the ledger traces a rule back to the day that taught it.
- Adherence, not age. A note's loads are counted from `traces.jsonl` (a seat read it); a
  guard-backed rule's use is its refusals. A new note or rule is in probation for
  `memory.probation_days` working days (default 10) and cannot be archived. After
  probation, one never loaded and never fired is an archive candidate for the next
  consolidate. The index is bounded by `memory.max_notes` (default 60); past it, the lowest
  load rates are archived first. Archive moves to `memory/archive/`, never deletes.
- Visible outcome. The SessionStart payload carries one line for the last promote run: what
  landed and what was rejected, with the reason, so a lost lesson is never silent.

## 7. Security integration (ZIRAN)

All through the ZIRAN CLI via the `scanner` adapter. ZIRAN exposes no MCP server (verified
2026-09-24 against `main`, branches, issues and PRs; its only entry point is the `ziran` CLI;
MCP appears only as a scan target), so the CLI is the sole integration surface.

- S1. Role audit. ZIRAN's tool-chain analysis over the role and tool matrix proposes each
  agent's allowlist. The repository's CI runs the ZIRAN GitHub Action over `agents/` and
  fails when an agent's tools widen past its allowlist. Prerequisite, decided 2026-09-24:
  ZIRAN ships support for reading Claude Code plugin agent files (name, description, tools,
  system prompt) in a ZIRAN release FIRST; WUWEI pins that release. No WUWEI-side converter.
- S2. Runtime traces. Each sweep runs `ziran analyze-traces --source otel` over the day's
  `traces.jsonl`. A dangerous sequence observed in a live session parks the affected item
  and prompts the user.
- S3. MCP audit and drift. `/wuwei init` runs ZIRAN's MCP metadata analysis over the MCP
  servers attached to the session and registers them with `ziran watch-registry`; each
  morning plan runs the registry check, so a server whose tools changed after approval is
  flagged before any seat uses it. Amendment (owner, 2026-10-03, #325): the check scans only
  servers Claude Code would attach (project servers need approval), one server per scanner
  call, never runs an unpinned `uvx`, `npx` or `pipx run` launcher, and warns by default:
  `scanner.mcp.block` (default `["critical"]`) sets what blocks launches, while a check that
  could not run always blocks.
- S4. Agent-surface gate. When `agent_surface` is set, the security sentinel runs
  `ziran audit` and `ziran ci --severity-threshold <config>` at pre-PR; each finding becomes a
  verdict row.

With the adapter set to `none` or ZIRAN absent, S2 to S4 report "unmeasured" (exit 2).

### 7.1 Integrity and canaries (owner, 2026-09-28)

Tamper evidence, not tamper-proofing (9.1): a process running as the owner can also edit the
verifier, so these catch accidental changes, other plugins or packages writing into WUWEI,
supply-chain drift between sessions and prompt-injected edits, and surface them loudly.

- Signed manifest. Each release ships `MANIFEST.sha256` (every shipped file: cli, adapters,
  hooks, charters, skills, agents, templates) signed in CI with an SSH signing key
  (`ssh-keygen -Y sign`); the public key is pinned in the plugin and in the workspace at
  `wuwei init`. SessionStart and every sweep re-hash the installed plugin and verify the
  signature (`ssh-keygen -Y verify`). A mismatch is a `page`, and every guard fails closed
  until the owner reinstalls or re-confirms on the host.
- Workspace integrity. `.wuwei/` is a git repository; `wuwei promote` commits every change
  it lands with a `Promoted-by: wuwei` trailer. SessionStart flags any change to charters,
  memory, goals or voice that is uncommitted or committed without that trailer: a `nudge`,
  a `page` for charter overrides and the voice.
- Prompt canary. `wuwei init` generates a random canary token per workspace, embedded in
  every charter and skill the seats load. The canary appearing in outbound text, a PR or
  tracker comment, or content fetched from outside means instructions leaked or were echoed
  through an injection: the outward lint refuses the message and the event is a `page`.
- Honeytoken. A decoy credentials file in the workspace that no legitimate process reads.
  A trace of any tool reading it, or its value appearing anywhere outbound, is a `page` and
  a scanner finding.

## 8. Adapters

Each adapter is a module implementing a port (3.5). The `none` implementation records
that it did nothing and returns exit 2 where a measurement was expected.

| Adapter | Interface | Reference implementation |
|---|---|---|
| tracker | `claim(item)`, `transition(item, state)`, `create(draft)`, `history(item)` | Linear |
| chat | `post(channel, text, thread)`, `dm(text)` | Slack |
| review_bot | `score(pr)`, `open_findings(pr)` | Greptile |
| runtime | `dispatch(role, brief_path, worktree, write)`, `status(job)`, `result(job)` (includes usage: tokens, cost, model, duration) | Claude (default), Codex |
| scanner | `audit(path)`, `gate(result, threshold)`, `traces(file)`, `mcp(servers)` | ZIRAN |
| code_host | `pr(ref)`, `checks(ref, sha)`, `reviews(ref)`, `threads(ref)`, `protection(repo, branch)`, `create_pr(draft)`, `request_reviewers(ref, logins)`, `comment(ref, text, thread)`, `merge(ref, sha)`, `revert_pr(ref)` | GitHub through `gh` (default); GitLab possible later |
| vcs | `identity(repo)`, `head(repo)`, `merge_base(repo, ref)`, `status(repo)`, `diff_stat(repo, base, head)`, `log_since(repo, sha)`, `worktree_add(repo, branch, path)` | git |
| inbound (M5) | `poll(since)` or `receive(request)`, `reply(thread, text)` | Slack (poll) |
| control_plane (M5) | `escalate(decision)`, `notify(summary)`, `poll_replies(since)` | Remote Control plus push (default), Signal, WhatsApp |
| redactor (M5) | `redact(text) -> text, findings` | built-in patterns (default); WUMING once it ships a CLI |
| tts | `speak(text, voice, out)` | macOS `say` (default on macOS), none |
| calendar | `events(since, until)` | private ICS feed URL through `urllib`, none |
| transcripts | `recent(since)`, `transcript(meeting)` | none (default); a meeting recorder's API |
| menu_bar | `render(status)` | SwiftBar plugin script (optional, macOS), none |

## 9. Error handling

- Every guard fails closed: an error inside a guard is exit 2, which blocks.
- A read that returns an error body is never parsed as data (the GitHub API returns error
  JSON on stdout).
- State writes are atomic (write to a temp file, then rename). `events.jsonl` is
  append-only.
- A lost seat is relaunched from its persisted brief; recovery reads `git log` since the
  item's recorded head and never redoes committed work.
- A dead watch process is detected by its missing clock line, not by its pid file.

### 9.1 Threat model and guard scope (owner, 2026-09-28; amended 2026-09-30, #237)

What the guards defend against: agent mistakes, corner-cutting, and actions a prompt
injection pushes through the normal tools. The Bash guards are cooperative mistake
prevention: refusing at the moment of action, with the reason, is what turns a rule into a
default. They are never an isolation boundary, and no hook, Claude Code or git, is a hard
boundary against the owner's own user.

What they do not defend against: a determined process running as the owner's user with a
shell. It can forge any local file, including state, events, hook payloads and any
approval record, so no local file is a trust anchor. Hard boundaries therefore sit outside
the owner's user account, and they hold when no hook runs:

- the code host's server-side rules (protected refs, required checks, required reviews),
  which the merge policy never overrides (4.6);
- publication credentials kept out of seat environments: no seat holds a token that can
  approve, release or deploy, and a merge lands only through the protected ref's required
  checks and reviews (4.6, 4.5);
- the owner sending messages that need approval: approve-tier text is delivered as a draft
  the owner sends (a chat draft, a pending review comment, or the text in the cockpit or on
  the phone), never sent by WUWEI (4.9);
- the out-of-process control plane (M5) for anything decided remotely.

Seats on the Codex runtime run in a write sandbox limited to their worktree, so they cannot
touch workspace state; this is a reason to route build seats there. Further hardening for
Claude seats (Claude Code's Bash sandbox, or a separate OS user for seats) is a later option.
Local checks that do not depend on parsing still raise the bar cheaply: pre-commit and
pre-push hooks in WUWEI worktrees, state files at mode 0444 outside the writer, and
`permissions.deny` for unambiguous deploy verbs. They catch mistakes like the guards do;
none of them is a boundary.

Guard scope. The plugin is installed for the owner's whole machine, so:

- a guard acts only when the session cwd or a path it targets (the resolved target decides
  for file guards) is inside a WUWEI workspace, one of its configured repos, or a WUWEI
  worktree; everywhere else it returns 0;
- relevance comes before parsing: a guard first decides from the raw input whether the
  call concerns it, and only relevant calls are parsed; a parse failure blocks only a
  relevant call, so a parser limit never blocks unrelated work;
- guards that concern roles (brief, retro, verdicts) apply to WUWEI role seats only, not to
  other subagents.

## 10. Testing

- Guards: table tests for exits 0, 1 and 2, including every bypass form in section 4.5,
  plus a mutation test per guard that disables it and asserts a test goes red.
- Hooks: recorded Claude Code hook payloads piped through each shim; assert allow or block
  and the message.
- Agents: a golden test regenerates `agents/` from `charters/` and fails on drift; the ZIRAN
  action fails on allowlist widening.
- End to end: a fixture workspace and a demo repository with record-and-replay adapters run
  a scripted day (plan, gate, one item through build, gates, raise, one fix round, close),
  asserting on events and exit codes, never on model prose.
- Triggering: `claude plugin eval` over skill descriptions, including near-miss negatives.
- Test runner: pytest as a development dependency only.
- Ports: every adapter passes its port's contract test; the core's tests use fakes and
  recorded adapter output only.
- 10.6 Latency (owner requirement): `bin/wuwei hook <event>` p95 CPU stays under 50 ms, with
  benchmark p95 measured and printed every run and the 50 ms budget asserted only when
  `WUWEI_BENCH=1` or outside CI with one-minute load below half the CPU count; otherwise
  benchmarks skip with the measurements and load.
- What a real day must prove (owner, 2026-09-30): a passing suite is not a release
  criterion on its own. No release ships without the live rehearsal a later issue defines
  (#239): the signed artifact, real seats, real git and a test repository on the code host
  carry one item from plan to verified close with no operator repair, and the run reports
  owner interventions, elapsed time and unexpected refusals. A rehearsal that could not run
  is unmeasured, never a pass.

## 11. Packaging and release

- The repository is its own marketplace. Install: `/plugin marketplace add taoq-ai/wuwei`,
  then install `wuwei`.
- Semantic versioning for the plugin. Charters carry a version; `wuwei init --upgrade`
  migrates a workspace's `config.toml` and charter overrides.
- Release automation matches ZIRAN's (release-please, conventional commits).

## 12. Brand and documentation

- README in the ZIRAN pattern: light and dark hero SVG of the day flow, accent `#00C9A7`, the
  无为 mark with its meaning, a "What WUWEI is / is not" section, install, quick start.
- Docs site on GitHub Pages: concepts (roles, guards, memory), configuration, adapters,
  writing charter overrides, security integration.
- Pitch line: autonomous delivery where the safe path is the default one.

## 13. Build order

Three modules, one release, built in dependency order, each with its own implementation plan:

1. Guards and CLI core: state writer, three-state exits, hooks, sweeps, verdict lint,
   identity, obligations, outward-text lint, traces.
2. Team: charters, agent generation, skills, planner flow, steward, runtime adapter.
3. Memory and security: spine, notes, index, memory lint, consolidation, ZIRAN adapter
   (S2 to S4, then S1 once the ZIRAN release with plugin agent support exists).

Upstream prerequisite, in parallel with module 1: the ZIRAN change for S1, planned and
shipped in the ZIRAN repository under its own spec.

v1 ships when all three pass the end-to-end scripted day and the owner has run one real day
on it. The repository stays PRIVATE until the owner judges it stable enough to publish.

## 14. Resolved questions (owner, 2026-09-24)

- Q1. ZIRAN support for Claude Code plugin agent files ships in ZIRAN first; WUWEI pins that
  release (section 7, S1).
- Q2. ZIRAN has no MCP server; the CLI is the integration surface. `watch-registry` covers
  MCP drift (section 7, S3).
- Q3. Private until stable enough to become public (section 13).

## 15. Post-v1 (M5): always-on responder and inbound messaging

Decided 2026-09-24: designed now, built after v1, tracked under milestone M5.

### 15.1 Why it needs a new process

A plugin runs only inside a Claude Code session; hooks fire on session events and scheduled
tasks need the app open. Responding to messages as they arrive needs one process outside
Claude Code. It is the only long-running process WUWEI ever runs.

### 15.2 Components

- `wuwei listen`: stdlib process. Polls poll-type inbound adapters on an interval (default
  60 s), accepts webhook-type adapters on a local port behind a tunnel, deduplicates by event
  id, persists a cursor per source, and appends normalised events to `inbox/inbox.jsonl`:
  `{id, source, channel, thread, sender, text, ts}` with text passed through the redactor
  before it is stored. Writes a clock line like the watch; ships launchd and systemd unit
  templates. Honours `responder.enabled = false` in `config.toml` as a kill switch.
- `responder` role (tenth role): for each batch of new inbox events the listener launches a
  headless Claude Code run (`claude -p`) with the responder agent, then exits. No resident
  agent.
- Inbound adapter interface (section 8): Slack by polling the Web API with `urllib`;
  WhatsApp by webhook.
- Redactor adapter (section 8): built-in patterns for phone numbers, emails and secrets by
  default.

### 15.3 Security envelope (every item is a guard with a mutation test)

- Sender and channel allowlists from config; anything else is logged and ignored.
- Responder tools: read-only lookups into the workspace and repos, and drafting. No shell, no
  repository writes, no tracker writes, no `Agent` spawning.
- Auto-send only acknowledgements and mechanical replies, through the outward-text guard.
  Anything carrying a technical claim, disagreement or scope statement becomes a draft in the
  owner's DM.
- No new work: the responder may file an intake item for the next morning gate, never start
  work.
- Per-sender and global rate limits.
- ZIRAN `analyze-traces` over every responder session at session end, not at the two-hour
  sweep; a dangerous sequence disables the responder until the owner re-enables it.
- An adversarial test suite drives the responder with injection messages drawn from ZIRAN's
  vector library and asserts no tool call outside the allowlist and no send outside the
  auto-send class.

### 15.4 Remote operation and the control plane (owner, 2026-09-24)

Goal: the owner operates the team remotely, stays responsive in the workspace's chat
channels, and receives escalations and replies to them without opening the chat tool or the
code host.

- Default control plane: Claude Code Remote Control plus push notifications. Decisions stay
  question widgets in the planner's session and reach the phone as notifications with
  tappable options. No extra infrastructure.
- Messaging control planes, optional: Signal and WhatsApp adapters for alerts and short
  replies when the owner is outside the Claude app. The listener parses replies such as
  "approve D-3", "option B on D-5" or "drop it" into decision answers; an unparseable reply is
  echoed back with the options, never guessed.
- Escalations over a messaging adapter carry the decision at the owner's `owner.verbosity.dm`
  level: the id, the question, the options with scores and the reason for the recommendation
  at `brief`, more fields at `standard`, the whole record at `full`. A `more D-n` reply sends
  the whole record. Whether workspace content may leave the approved tools at all is the
  workspace owner's policy call, recorded in `config.toml`
  (`control_plane.content = "summary" | "none"`), default `summary`. `summary` permits the
  `dm` level text and the `more D-n` reply; `none` sends only the id and the option letters.
- Responder default for remote operation: every non-mechanical reply and every proactive post
  is a draft delivered to the control plane for approve, edit or drop. Auto-send is limited
  to acknowledgements in channels marked internal; channels marked external (client-facing)
  never auto-send.
- Remote operation needs the session host awake and online. Recommended: a small always-on
  machine running the workspace session, driven from the phone. Cloud sessions free the
  laptop but cannot read the local workspace.
- On Team and Enterprise plans Remote Control is off until an organisation Owner enables it.

### 15.5 Signal constraints

- No official bot API. The adapter drives `signal-cli` (community project) on the listener
  host, as a subprocess; it carries its own runtime dependency, outside the stdlib core.
- A dedicated number registered for the bot. Never linked as a secondary device of the
  owner's personal account, which would expose every private chat to the bot.
- Received messages are polled; no public endpoint.
- Protocol changes can break `signal-cli` until it is updated: the adapter reports exit 2
  and the control plane falls back to Remote Control push.

### 15.6 WhatsApp constraints

- Official WhatsApp Business Platform only (Meta Cloud API, or a provider such as Twilio). It
  needs a business account and a dedicated number. Libraries that drive personal WhatsApp
  accounts break Meta's terms and are not supported.
- Inbound is a webhook: a public HTTPS endpoint (tunnel or small relay) that answers Meta's
  verification handshake and verifies the request signature on every call; unsigned or
  mis-signed requests are dropped and logged.
- Free-form replies only within the provider's customer-service window after the user's last
  message; outside it, pre-approved templates only. The adapter enforces this and exits 1
  instead of sending.
- Phone numbers and message bodies are personal data: redacted before traces, inbox storage
  and memory.

### 15.7 Hosting

The listener runs where it can stay up: the owner's machine while awake, or a small VM. The
workspace on that host holds the inbox; the responder's drafts reach the owner through the
chat adapter's DM.

### 15.8 Always-on operations (owner, 2026-09-24)

- Dead-man switch. The listener pings an external check endpoint (configurable URL, for
  example a hosted cron monitor) every 5 minutes. When pings stop, the external service
  alerts the owner's phone. Nothing on the host can report the host's own death, so this is
  the only liveness signal trusted while the owner is away.
- Budget governor. Daily token and cost caps per role and per workspace in `config.toml`,
  measured from the headless runs' usage output. At 80 percent a notify goes to the control
  plane; at 100 percent the workspace degrades to escalations only (no new seat launches,
  no routines) until the owner raises the cap or the day rolls over. A launch that would
  cross the cap is refused by the agent-launch guard.
- Routines. Recurring jobs owned by the listener instead of the app: each routine declares a
  cron, a charter, a budget, its allowed adapters and its outward-action class, and runs
  headless. Approvals are stored per routine in the workspace, so a new routine is run once
  by hand before its first unattended run. The owner's existing recurring jobs (daily brief,
  mention triage, PR review watch, meeting prep, meeting-notes sync, weekly status) are the
  reference set.
- Quiet hours and urgency. Working hours for the owner and per channel audience (with time
  zones) in config. Outside them, posts to people are queued and sent at the start of the
  audience's next working window. Every escalation carries an urgency: `page` (the day is
  blocked, loss is irreversible, or a security finding fired) goes out at once, even in quiet
  hours; `digest` batches into the next digest.
- Undo log. Every outward action (chat post, PR comment, tracker write) is recorded with the
  adapter call that reverts it (delete or edit a message, delete a comment, restore the prior
  tracker state). The control plane accepts "undo last post" and "retract <action id>".
  Actions a provider cannot revert are marked irreversible and always need approval.
- Workspace isolation. One listener process, credential set, memory, inbox and allowlist per
  workspace, each with its own service unit and working directory. A process refuses to read
  another workspace's directory, and a message is answered only with its own workspace's
  context. Credentials are per workspace, from that workspace's environment file, never
  shared.

### 15.9 Sessions started from the control plane (owner, 2026-09-24)

A plugin cannot open a top-level session; the listener can. Verified against the Claude Code
docs on 2026-09-24: `claude -p --output-format json` returns a `session_id`; `claude -p
--resume <id> "<message>"` continues it; `--permission-mode dontAsk` refuses anything not
pre-approved and `--allowedTools` pre-approves tools; `claude --cloud "<task>"` starts a cloud
session. Unconfirmed and therefore not relied on: enabling Remote Control at launch, and how
a headless run treats a question to the user.

- Command vocabulary, from a messaging control plane only: `plan`, `status`, `report`,
  `run <routine>`, `ask <question>`, `cloud <repo> <task>`, `stop <session>`, `stop all`.
  Anything else is answered with the vocabulary. No free-form shell, ever.
- One control-plane thread maps to one session id. The listener starts `claude -p` with the
  matching skill and the workspace, the role's tools pre-approved, `dontAsk` for the rest;
  each reply in the thread resumes the session with `--resume`.
- Headless runs never wait on a question widget: the planner writes decisions to the queue
  and ends its turn; the listener sends them out; the reply resumes the session. A refused
  tool call becomes a decision, never a silent stall.
- `ask` runs a read-only seat. `cloud` starts a cloud session for repository-only work (no
  access to the local workspace, memory or adapters); its result comes back as a summary
  and a link, and it is covered by the budget governor.
- Guards: only the owner's number; the sender's Signal safety number is pinned and a change
  (new SIM, reinstall) refuses commands until re-confirmed on the host; `plan`, `run`,
  `cloud` and anything that posts outward or spends above a configured threshold need a
  second factor (a TOTP code in the message, or a confirmation reply within 2 minutes);
  `stop all` is always accepted from the owner's number and needs no second factor; CAP,
  memory floor, budget and quiet hours apply to every started session.

### 15.10 People and inbound routing (owner, 2026-09-28)

The listener routes messages from people, not only work.

- People register in config: person, relationship (manager, client lead, direct team, peer,
  other) and reply window in working hours.
- Each inbound message is classified as mechanical (answered under 4.9), work within the
  goals (to discovery intake, 5.7), work outside the goals (a new-work decision), needs-you
  (a holistic or personal ask the owner must answer), or FYI (digest only).
- Needs-you from internal people: an acknowledgement in the owner's voice with a time
  commitment only if the channel's tier allows auto-send, otherwise drafted; plus a full
  draft reply with a prep brief from the workspace for the owner to approve, edit or drop.
  Needs-you from external people: surfaced with a prep brief only; the owner writes the reply.
- Outbound tiers (4.9) govern what the responder may send; where 15.3 and 15.4 are stricter
  for a channel, the stricter rule wins, and every direct message, including an
  acknowledgement, is a draft for one-tap approval.
- Reply obligations: each needs-you ask is owed until answered. It starts as a `nudge` and
  becomes a `page` as its reply window closes. The Stop guard refuses day close while a reply
  is owed to a person.
