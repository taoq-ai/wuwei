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
  merging was always a human act. Amended (owner, 2026-10-04, #478): the guard refuses and
  asks; only the owner's recorded answer (once, today, always) lets the same action through.
- Approving pull requests, or bypassing branch protection to merge. WUWEI never approves a
  review and never merges with admin override; a merge happens only when the repository's
  own rules already allow it (section 4.6).
- A hosted service or database. A long-running process is out of scope for v1; M5 adds
  exactly one, the listener (section 15). The optional telemetry collector (5.13) is the
  project's, outside the plugin, and the plugin never needs it.
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
  `python3 -I -P -S` with explicit plugin import paths (owner decision, 2026-09-28; `-S`
  added by #346). Isolated mode ignores PYTHON* settings except PYTHONEXECUTABLE on macOS,
  excludes user site-packages and the working directory from import paths. Explicit -P
  enforces Python 3.11+. `-S` skips the `site` import: the stdlib-only CLI sets its own
  import paths and needs nothing from site-packages or `.pth` files, which also no longer
  run on every tool call. PATH remains trusted for interpreter selection.
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
    tracker/         none (default), linear, jira, github
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
                       environment register, outward-text rules, spec engine (5.10)
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
  metrics/             weekly telemetry aggregates and the workspace token (5.13)
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
| PreToolUse | `Agent` launch | no brief logged for it; a gate seat while its item's builder is live or its tree is dirty; running seats at CAP or free memory below the configured floor; an item without a ticket while tracker hygiene requires one (5.11) |
| PreToolUse | `git commit`, `git push` | author or committer differs from repository config; force-push; push to the default branch; push before the fast checks passed (owner, 2026-10-05, #530: below strict a missing fast check is a warning under observe and the owner's card under guarded, naming the check) |
| PreToolUse | `gh pr create` | the pre-PR gate set has not all passed (#530: a warning under observe, the owner's card under guarded); no reviewer named in the same action; `--repo` and `--head` given apart, or naming a branch that is not a recorded item branch (#534: with both, or after `cd <recorded worktree> &&`, it runs from any directory) |
| PreToolUse | `gh pr merge` | the merge policy (4.6) does not clear this PR at this head |
| PreToolUse | `gh pr review --approve`, `--admin`, protection changes | always |
| PreToolUse | any deploy action (4.7) | always |
| PreToolUse | chat, tracker or docs (5.12) adapter call | outward-text lint fails; a technical claim, disagreement or scope statement without an approved draft |
| PreToolUse | Write or Edit on `state.json`, `events.jsonl` | always; state changes go through the CLI |
| PreToolUse | Write, Edit, MultiEdit or NotebookEdit in an item worktree, outside the spec engine's directories | under spec mode, a step of the configured engine before implementation is not done for the item (5.10) |
| PreToolUse | top-level `cd` out of the workspace | always; use `git -C` or a subshell |
| PostToolUse | any tool | never refuses; appends the call to `traces.jsonl` in OTel JSONL shape |
| PostToolUse | write to `decisions/gate-*.md` | verdict lint fails; the verdict is returned to the seat |
| PostToolUse | Write, Edit, MultiEdit, NotebookEdit or Bash in an item worktree | never refuses; records each spec step whose artifact appeared (5.10) |
| SubagentStop | a seat finishes | its three-line retro note is missing, or a builder's last message does not name its spec artifacts (5.10); otherwise records it, flagging a last message that asks the owner a question without a decision id (5.8) |
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
  120; head, CI, mergeability, reviews, comments, threads) and, on a change with a part that
  needs a planner action (`watch.ACTIONS`: merged, closed, new commits, conflicts, new
  comments, reviews, a failed check), records a `pr.changed` event and wakes the planner
  session (and, in M5, launches a headless shepherd run). Each part is delivered once
  (`watch.delivered`) until its evidence changes; `updated_at` is evidence time only; a
  SessionStart in the registered planner session consumes the wake; `wuwei watch why <pr>`
  shows what fired and what was suppressed (#674). Nothing needs to be re-armed by a seat.
- Overnight, without a session (owner, 2026-10-08, #511). `wuwei sweep obligations --headless`
  (and `wuwei shepherd`, every 15 minutes, installed with `wuwei shepherd schedule`, from the
  Shepherd card in a session or, under strict, by the owner in a host terminal) sweeps the
  owning day: the newest day, today included, whose plan is approved. It does nothing while a
  planner session is live. It checks an `approved` PR against the 4.6 policy and queues it;
  until #524 lands the merge waits for the morning `wuwei pr act`. It sends a `review_stale` ping through 4.9, and
  queues every other state with its evidence as `shepherd.overnight` events, which open the
  next morning plan. It never replies, fixes, rebases, starts a seat or calls a model.
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

The internal-state patterns (`outward.patterns`, empty by default) apply by kind and
audience (#533). Tracker, docs and code-host writes are the team's records and never read
them. On chat and mail, a client or public reader gets a card naming the audience and the
matched word, decided with the approval tier, so one approval sends it. A team or company
reader gets the message; under `autonomy.mode = "supervised"` an `outward.lint` event and a
warning name the word, and under autonomous nothing is recorded. The strict posture keeps
the refusal. A message only the owner reads is never checked.

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
refused as opaque. Each bypass form is a test case in the guard's table. Amended (owner,
2026-10-05, #530): below strict an opaque command runs with one `guard.would_refuse` warning
naming what could not be read, unless its literal text names a publish target (a
protected-branch, force, tag or no-verify push, a deploy, a release, a gh merge, approval,
admin, protection or text write, a hooks path change); the records floor stays.

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

Amended (owner, 2026-10-05, #524): a merge the policy does not clear is a grantable owner
action like a deploy (4.7). `wuwei merge` (and `wuwei pr act`) asks the owner on a decision card
(Keep owner-only, Allow once, Allow today, Always allow per repository; no Always under
`strict`), and a merge the plan lists is a planned card the morning gate asks, per repository
or per PR. The recorded answer replaces only eligibility and pacing (`merge.auto`, risk flags,
never-auto paths, size, cycle budget, soak, daily cap, quiet hours, breaker); every
precondition above still holds at the current head, and the repository must allow squash
merges. A precondition that fails names the condition: no grant lifts it. With no grant,
`[merge] default_tier` decides: `ask` writes the card, `owner_only` prints the exact
`gh pr merge <url> --squash --match-head-commit <sha>` for a host terminal; unset, it is
`owner_only` under `strict` and `ask` otherwise. Granted merges are journaled, watched and
undo-logged like auto-merges.

### 4.7 Deployment ban (owner, 2026-09-28)

WUWEI never deploys, in any profile, routine or remote command. Refused always, after the
normalisation in 4.5: dispatching or re-running a workflow the config marks as deploying,
`gh release create` and tag pushes, pushes and merges to branches in the configured
environment register (for example `production`, `release/*`), GitHub deployment and
environment API calls, and the deploy commands of common tools (`kubectl apply`, `helm
upgrade`/`install`, `terraform apply`, `pulumi up`, `vercel`/`netlify` deploy, `fly deploy`,
`gcloud`/`aws`/`az` deploy verbs, `docker push`), extendable by `deploy.deny` in config. A
merge into a repository with `merge_deploys = true` is a deployment and goes to the owner.

Amended (owner, 2026-10-04, #478): the guard refuses and asks; only the owner's recorded answer
(once, today, always) lets the same action through. The refusal writes a decision card
(`Keep owner-only`, `Allow once`, `Allow today`, `Always allow`; no `Always allow` under strict);
the answer is the grant, matched on the action class and the repository. A standing grant is
one `[grants]` line, ignored under strict and removed with `wuwei grants revoke`. No seat,
default or hook creates a grant.

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
- Tracker writes (5.11): comments and ticket creations whose kind is in `tracker.auto` are
  auto-sent; every other tracker write is a draft, and the approve rules above still apply
  to each message. A GitHub `project` or `board` whose owner is not in
  `outbound.code_host_orgs` is an external party, so every write to it is a draft whatever
  `auto` says; Linear and Jira tickets are internal to the configured workspace or site.

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

Records (owner, 2026-10-03, #357). The records under `.wuwei/` are written by the workflow
from the owner's answers; no step asks the owner to create or edit a file by hand. The owner
answers questions (in the session, in the DM, or y/N at a terminal) and may edit any record
afterwards; the planner records. The host terminal remains for the strict posture and for
credentials. (owner, 2026-10-05, #529) Outside strict the owner's answer on a card is the
confirmation of the config write its record command makes: `calibrate --answer` for an
interview card, `config set --from-card D-n` for a decision whose options carry a `Value:`
row `KEY = VALUE` (or, as before, a title that reads `KEY = VALUE`). The answer is recorded
hashed on the planner's session row when the card is answered, and the command writes only
that answer, as shown (a list is replaced, not extended); an answer that sets nothing (Defer,
Keep) records the outcome only. A `config set` in a session without a card exits 1 naming the
card; under strict the command is printed for a host terminal. (#600) A config record whose
`Previous:` line records the key's value before the change is two-way: its undo is the same
`config set` back to that value; the first route stores it two-way and, without a better
class, `approach`. A config record is never taken under the mandate; it waits for the
owner's answer on its card. `repos.N.fast_checks = []` means none configured: items build,
the PR body says `checks: none configured`, CI and the gates are the evidence; strict asks the
repository's fast-checks card once before its first launch. `calibrate --questions` writes
that card (detected checks or none, with the reason), taken under the mandate in autonomous
mode.

Availability (owner, 2026-10-04, #477). The owner's session is never blocked by work.
Seats run in the background; any command that can run longer than a few seconds (fast
checks, `dispatch opinion`, `steward run`, calibration) runs in the background, and the
planner acts on its completion notification. The planner's turn ends with the board in one
line (`wuwei status --line`, which names the running seats by role; `wuwei status` and
`wuwei next` give each seat's item and start time), and the owner can speak at any time; the planner answers from the board, never by
resuming or interrupting a seat. Owner questions are the one thing that waits, because
they wait for the owner.

Pace (owner, 2026-10-08, #579). A day runs at one pace, chosen on the morning gate card and
recorded in day state (`pace`); `wuwei plan set pace=<p>` changes it during the day for items
tiered afterwards. The pace sets the inputs that tiers (#280), process depth (#567) and CAP
(#528) already read; it never adds a second tier or depth table:

| | careful | steady (default) | fast |
| --- | --- | --- | --- |
| Tier | light rises to standard; guard code or trust paths run full | the computed tier | the computed tier; guard code or trust paths run full; a standard item with a measured diff, no guard code, trust path, lead flag or FULL track runs at light depth |
| Fix rounds | follow the depth (#567) | as today | follow the depth: light depth is re-read by the same sentinel |
| Checks | the fast checks and `repos.tests` before the PR | the fast checks; CI runs the suite | `repos.tests` on the test files the diff changes; CI is the gate |
| Seats | CAP minus one | CAP | CAP; every launch waits while the load average is at or over the core count |
| Cards | as the classes say | as the classes say | as the classes say |

`wuwei plan propose` advises the pace from three inputs and names the one that binds: the
queue (predicted tiers, items whose `paths` touch guard code, expected cycle minutes from the
#567 medians against the envelope end, the nearest goal date), the host (cores, load average,
the last `repos.tests` duration) and the token budget (items the budget reaches at that
pace). When inputs disagree the advice takes the slower pace and says what unlocks the faster
one; the budget only advises against a pace. The owner's default (`[pace] default`) is shown
in one line and never overridden. The pace never moves a floor: records, publish grants,
strict refusals, trust-boundary findings, merge only at the gated head with green required
checks, decision routing and every 9.2 invariant hold at every pace (I15 to I17).

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
- Process depth follows the tier (owner, 2026-10-08, #567). The tier (#280, from the diff,
  the repository floor and the lead tier) decides the process depth, not only the gate
  count. The brief and the launch prompt carry a `Depth:` line, so a seat never decides it;
  the gate seats read the tier `dispatch next` recorded, never the builder's prediction.

  | | light | standard | full |
  |---|---|---|---|
  | Spec engine | none (#280) | the engine's steps | the engine's steps |
  | Builder class sweep | none | the classes `wuwei sweep classes <worktree>` lists from the changed files | every class |
  | Gates | quality | arch, quality, security | arch, quality, security, goal when docs |
  | Mutation step (gate step zero) | none | only when the diff touches `guards/`, `grants`, `outward`, a hook or a `trust_paths` entry | always |
  | After a fix | the same sentinel re-reads the diff and rewrites its `Verdict:` and `Head:` lines | the delta round | the delta round |
  | Verdict shape | `Verdict:`, `Head:`, findings | as below | as below |
  | Decision records | a Routine record under mandate prints one line in `decision show` (`--full` prints it) | the same | the same |
  | Retro note | only when a line is not `none` | every seat | every seat |

  A skipped step zero at standard writes `Mutation: skipped (depth standard)`. No step adds
  a refusal: the light shape is an acceptance, and a verdict whose seat or item cannot be
  resolved is linted at the standard shape.
- CAP counts running build seats. The free-memory floor comes from config.
  Amended (owner, 2026-10-05, #528): CAP and `host.seats` derive from the measured host,
  never from a shipped number: the running seats plus the seats that fit above the memory
  floor at the measured seat cost, one per core; `host.seats` is that fit but never under
  one gate's three sentinels, so a gate always fits, and CAP is the fit. A sweep where a gate
  waits for seats starts no new planned build. A damaged day log falls back to the default
  seat cost with a warning. `[budget] tokens_per_day`, with the median input plus output tokens per
  `seat.usage` row, bounds CAP from the other side (at least 1). A positive config `cap` or
  `host.seats` is the owner's one-key override. Plan propose, each `dispatch next --all`
  sweep, the agent-launch guard and `dispatch opinion` derive it live; the plan, the gate
  card and the status line name what bound it (`memory`, `host.seats`, `budget`, `owner`,
  `unmeasured`).
  Amended (owner, 2026-10-10, #658): the memory estimate applies only when a seat runtime of
  the day (`adapters.runtime` or a seat policy runtime) launches its own process, that is
  any runtime but `claude` and `none`; it is then smoothed as the median of today's last five
  readings (each sweep records its reading on `cap.derived`), bound `memory`. Claude subagent
  seats share one process, so free memory does not track their count: CAP and `host.seats`
  are the configured `host.seats`, else one per core, bound `host.seats`, and free memory is
  not read. The free-memory floor still refuses a launch under either rule.
- Seat policy (model and runtime per role) is set at the morning gate and stored in state.
- Boundary and environment register come from config; the arch sentinel checks against them.
- Verdict shape (at light, see Process depth above): a `Verdict: PASS|FIX|PARK|ESCALATE` line; findings with severity,
  `file:line`, failure scenario and `blocks: yes|no`; a probe or mutation line per claim (or
  "not run"); residual risk; the retro note.
- Retro note, every seat: three lines prefixed `Blocked:`, `Gap:`, `Change:` (at light, only
  when a line is not `none`; an absent note is recorded as `none` on every line).
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
  their semantics. `host.seats` derives per the #658 rule unless config pins it. A
  ceiling refusal names `host.seats`.
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
digest at most every two hours that lists the decisions cruise mode answered. Under
`autonomy.mode = autonomous` a decision the mandate covers (5.8, decision classes) is never a
card (owner, 2026-10-05, #530).

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
- cycle time (owner, 2026-10-08, #567): `cycle_minutes` per item, from its first
  `plan.approved` or `plan.added` to its merge, across days; `gate_minutes` from its first
  sentinel launch to its last received verdict; `cycle_by_tier`, the median per tier against
  the targets light under 60 and standard under 180 minutes on the fixture day. The report
  shows them under `## Cycle time`; the retro names the tier whose median moved most week
  over week. A missed target is a reading, never a refusal.
- per pace (owner, 2026-10-08, #579): `by_pace`, per pace the days, items merged, cycle
  minutes per tier, escaped defects (the measure above) and cards asked; a day counts at its
  final pace. The report and the retro show them under `## Pace` and name a pace that costs
  escaped defects. After ten days at two paces the steward proposes `pace.default` on one
  config card, at most once per ten days.
- DORA keys (owner, 2026-10-08, #586): `wuwei dora [--window 28]` prints five rows, each with
  its source or the reason it is unmeasured. Lead time to merge is the median
  `cycle_minutes` of items merged in the window; change failure rate is the escaped share
  of those items (the measure above); deployment frequency and lead time to deploy read the
  code host's deployments, or its published releases when a repository never deployed;
  time to restore stays unmeasured until on-call incidents exist (#415). The report and the
  retro show the table under `## DORA (last 28 days)`, the week digest ends its Metrics with
  it, and `wuwei dora` exits 2 when the code host could not run. A key is a reading, never a
  refusal.

The baseline is the owner's hand-run month before WUWEI, recorded once in the workspace at
`memory/notes/baseline.md` (type `reference`), never in this repository. A metric that
cannot be computed reports "unmeasured", never zero.

### 5.7 Goals, discovery and prioritisation (owner, 2026-09-28)

Goals. `memory/goals.md` holds the owner's goals, one block each: id (`G-n`), outcome, measure,
target, date, priority. While it has none, the lead proposes goals in its JSON, the morning
gate shows them and the planner records the approved blocks with `wuwei goals edit --file`
(5.2); later, seats and the steward may propose changes (6.8) but `wuwei promote` refuses a goal change that the owner has not approved at the
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

### 5.8 Decision framework (owner, 2026-09-28; amended 2026-10-01, #282 and #301; amended 2026-10-04, #475)

Every decision that the owner or cruise mode answers is a record
`days/<date>/decisions/D-<n>.md` in one shape (MADR with a Kepner-Tregoe evaluation); a
two-way open question inside the item is an assumption instead (5.3):

- `Question:` one line; `Context:` what forces the decision, with evidence paths
- `Class:` one of the decision classes in 5.8.1
- `Role:` optional, one line: the role (charter name) that wrote the record; its confidence is
  scored per role (5.8.1, Calibration)
- `Options:` at least two, one of them doing nothing or deferring, as the table
  `Option | Title | Rationale | Consequence`: a short title (at most 40 characters, no quote,
  backtick, `$` or backslash), why the option scores as it does against the musts and wants,
  and what changes if it is chosen, what it costs and what it closes (owner, 2026-10-04, #475)
- `Musts:` pass/fail criteria that filter options out
- `Wants:` weighted criteria (weights 1 to 10), each option scored 0 to 10 against each
- `Recommendation:` the option with the highest weighted score among those passing every
  must, with `Confidence: high|medium|low`, and `Reasoning:` one line naming the wants that
  decided it and what would flip it (owner, 2026-10-04, #475)
- `Lenses:` for an engineering class (`design`, `boundary`, `refactor`, `dependency-bump`),
  the table `Lens | <option ids>` with one line per option for each configured lens. The
  defaults are SOLID (which principle it keeps or breaks), twelve-factor (config, backing
  services, processes and dev-prod parity where relevant), YAGNI (what it builds that no item
  needs yet) and ponytail (a simpler thing that works: stdlib before custom, native before a
  dependency). `[decisions.lenses]` maps a name to its one-line question: a name adds a lens,
  an empty question drops one. Prioritisation keeps its framework's evidence lines (5.6) and
  reversibility keeps the one-way or two-way test; neither is a configured lens
  (owner, 2026-10-04, #475)
- `Reversibility: one-way|two-way`, `Blast radius:` who or what is affected if it is wrong
- `Pre-mortem:` the most likely way the recommendation fails
- `Revisit:` a date or trigger that reopens it
- `Decided-by:` `owner` as written by the seat, or `cruise <class>@L<n>` written by the CLI
  when cruise mode answers it; `Outcome:` once taken

Routing by class. The record's class level and the conditions in 5.8.1 decide whether the
CLI answers it or the owner does; anything cruise mode does not answer goes to the owner.
When unsure, it is one-way.

Decision classes (owner, 2026-10-05, #530). `decision route` derives an MIT CISR class from
two axes already in the record. Risk is low when the record is two-way and its blast radius
starts with item, own branch, own PR or day; anything else is high. Ambiguity is low when
Confidence is not low and the 5.8.1 margin is at least 0.2. Routine is low on both,
Consequential is high risk with low ambiguity, Exploratory is low risk with high ambiguity and
Strategic is high on both. The 5.8.1 classes `retry` (a fix round after FIX verdicts),
`approach` (a builder's task round, a choice between seat procedures), `park` (a parked item's
next step) and `accept-residual` are Routine by definition. `autonomy.mode` holds the owner's
setup answer, default `autonomous`: a Routine, Consequential or Exploratory record whose
recommendation scores ahead is taken as recommended, written `Decided-by: mandate` by the CLI,
listed in the digest and in the day report with the reversal command, and never a card; a tie,
a Strategic record, a one-way record (an `unsure` one too, unless its class is Routine by
definition) and a record written `Decided-by: owner` (a security finding) go to the owner with
the lens lines. A one-way record is never Routine by definition. Under `supervised` routing stays
as before this amendment. The lint OK line names the class, and a record without a
recommendation is refused with "add the recommendation and the reasoning".

Measured reversibility (owner, 2026-10-08, #557). A record counts as two-way only when the CLI
knows the undo for its action and that undo ran once in this workspace. The class gives the
action kind. The commit classes (`approach`, `retry`, `accept-residual`, `scope-cut` and the
engineering classes) undo with a git revert on the item branch. `park`, `defer` and `re-plan`
undo with `wuwei undo D-n`. `merge` undoes with a revert PR through `wuwei undo <event id>`,
and only when every repository the record names declares `merge_deploys = false` (4.6). A
message has no undo (4.9), and `other` or a record without a class has none registered, so
each of them is one-way. `wuwei undo rehearse commit` and `wuwei undo rehearse decision` run
the undo once on a scratch target and write `memory/rehearsals.json`, which only those
commands write; a merge counts after its first real `wuwei undo`. The CLI only lowers a door.
`decision lint` prints the correction and keeps its exit code, and `decision route` writes
`Reversibility: one-way` and a Notes line into the record on its first route, so the record
comes to the owner as a card. `wuwei next` returns each missing rehearsal as a run row after
the gate. The day report lists what was undone today and what cannot be undone.

Enforcement. A PostToolUse decision lint on writes to `decisions/D-*.md` refuses a record
missing any field, with an unknown class, with fewer than two options, or whose
recommendation is not the top passing option by the stated weights (the CLI recomputes the
score). A record written from 2026-10-04 on is also refused without `Class:`, the four option
columns, unique titles, `Reasoning:` or, for an engineering class, exactly one lens row per
configured lens; earlier records still count in the history readers (owner, 2026-10-04,
#475). The owner's question card labels each option with its title, the recommended one first
and marked (Recommended); each description is the rationale, the consequence and the lens
lines, cut to their first sentence at brief verbosity; the question ends with the first
sentence of the reasoning. A seat question that is not a decision record is refused, in every runtime: a
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
| `design` | an architecture, interface or data-shape choice that outlives the item (owner, 2026-10-04, #475) | L0 | L3 |
| `boundary` | moving or changing a module, service or ownership boundary (owner, 2026-10-04, #475) | L0 | L3 |
| `refactor` | restructuring code without changing behaviour (owner, 2026-10-04, #475) | L0 | L3 |
| `merge` | merging a pull request (4.6) | L3 | L3 |
| `message` | sending or replying to a person; the 4.9 tiers are unchanged; an external confirmation holds no reversible work (5.8.2) | L0 | L1 |
| `other` | anything no class above covers | L0 | L1 |

The L2 defaults are the two-way, inside-the-item decisions seats took on their own before
cruise mode. `[decisions.cruise]` in `config.toml`: `enabled` (default true), `margin`
(default 0.2), `max_per_day` (default 20), `undo_minutes` (default 60), `budget_share`
(default 0.1, above 0 and at most 0.5), `budget_window_days` (default 14), `burn_warn`
(default 2.0), `calibration_threshold` (default 0.15, above 0 and below 1),
`calibration_min` (default 10), `shadow_days` (default 5), `shadow_min` (default 5), and `levels.<class>`, which only lowers a class. The config check refuses an unknown class, a
level outside 0 to 3, or a level above the class's ceiling. The running level lives in
`memory/cruise.json`, starts at the default, and is written only by `wuwei promote` (raises
with ledger evidence after a passed shadow and morning-gate approval, lowers when the error budget is spent). A class runs at the lowest
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
carries the class ones; the rest are checked on every record. Under `autonomy.mode =
autonomous` (5.8, decision classes) the ceilings bind a two-way record not written for the
owner through its action's floor (merge policy 4.6, publish grants 4.7, outbound tiers 4.9),
not the decision record (#530); one-way records and trust-boundary findings still go to the owner.

Merge. The `merge` class answers only where `merge.auto = true` and the merge policy clears
the merge; the policy's eligibility, preconditions, soak window, daily cap and breaker
replace the other conditions above, unchanged; the ceilings still apply. Auto-merges do
not count toward `max_per_day`. At L3 (the default, and the behaviour before cruise mode) an auto-merge
appears in the digest; at L2 a nudge also goes out when the soak window opens; at L0 or L1
every merge goes to the owner.

Promotion and demotion. The steward proposes raising a class one level through propose and
promote (6.8) after 10 agreements and no reversal in that class over 14 days, with its error
budget unspent; an agreement is an owner answer equal to the recommendation, or a cruise
answer whose undo window closed without an undo. `wuwei promote` lands a raise only when the
owner approved it at the morning gate, and never above the ceiling. Once a week the steward
re-asks the owner one cruise-answered record per class from the past seven days, with the
answer hidden; a different choice counts as a reversal.

Shadow promotion (owner, 2026-10-08, #560). Agreement alone said nothing about what the next
level would do on live records, so a raise is shadowed first. When a class reaches its
agreements, propose starts a shadow at the next level in `memory/cruise.json` instead of a
card. While it runs, each record the mandate takes for that class also gets the answer the
shadow level would have given (`decision_shadows`, written only by `wuwei decision route`);
the live route never changes. The steward scores each shadow answer against the record's final
outcome: an owner answer, or a cruise answer whose undo window closed. One disagreement ends
the shadow, and the ledger names the record and both options. The shadow passes after
`shadow_days` with at least `shadow_min` scored answers, all agreeing. Only a passed shadow
gets the raise card, the card ends the shadow so it asks once, and `wuwei promote` lands a
raise only from a card that carries a passed shadow. A raise to L1 changes no route, so its
shadow passes at once. After an ended shadow the agreements count again from its end.
`bin/wuwei cruise shadow` prints the shadows and the day report has a `## Cruise shadow`
section.

Error budget (owner, 2026-10-08, #558). A single event no longer lowers a class: one unlucky
reversal dropped a class, and a slow drift of bad calls never tripped anything. Each class
has a budget per `budget_window_days` window. Its events are reversals (an undo, a later
owner answer that differs from a cruise answer, a weekly sample answered differently) and
escaped defects (5.6) attributed to a cruise answer of the class; the allowance is
`budget_share` times the cruise answers of the class in the window. The budget is spent
when the events exceed the allowance and number at least two. The burn rate is the events
of the last 48 hours against the window's allowance, scaled to the window
(`events x window_days / (2 x allowance)`); at `burn_warn` or above the steward writes one
`cruise.burn` nudge a day naming the events, whose action is `wuwei cruise budget`. The
steward review (every `steward run` and `dispatch next`) evaluates the budgets. A spent
class runs one level lower, never below L0, through the promote writer, with a ledger line
that starts `budget spent: <class>` and names every event; `cruise.json` holds the level it
took away. When the window refills (the class is no longer spent) the CLI restores the held
level through the same writer with a `budget refilled` ledger line. That restore is the one
level raise without a morning-gate card, and it goes only back to the held level, never
above it or the ceiling; any other level write, such as an approved raise, clears the hold.
Thin-margin escalations still go to the owner and are flagged on the route, but no longer
lower a class. A class with a spent budget, or with a budget event since its last level
change, gets no raise card. `wuwei cruise budget` prints class, level, answered, spent,
allowance, burn and state, and exits 1 when any class is not ok.

Calibration (owner, 2026-10-08, #559). A record's stated Confidence is scored against what
happened. The CLI stores `confidence` and `role` (from the optional `Role:` field) in the
`decision.decided` payload of every record a seat, the mandate or a cruise rule takes. Over
the `budget_window_days` window each taken record with a stored confidence and a closed undo
window is scored: forecast high 0.9, medium 0.6, low 0.3; outcome 0 when an undo, a reversal,
a weekly sample answered differently or an escaped defect names it, else 1. The Brier score
(mean squared difference) is computed per class and per role. Fewer than `calibration_min`
scored records is `too few`; above `calibration_threshold` is `uncalibrated`; else
`calibrated`. The steward review stores the uncalibrated classes and roles in `cruise.json`
under `calibration` through the promote writer, with one ledger line naming the broken
records, only when the sets change. An uncalibrated class runs at most L1. A record whose
`Role:` is stored uncalibrated routes with high ambiguity, so Routine becomes Exploratory and
Consequential becomes Strategic (a card); this never refuses. A class gets a raise card only
when its live state is `calibrated`. `too few` blocks promotion only. `wuwei cruise
calibration` prints kind, name, scored, brier and state, and exits 1 when any row is
uncalibrated. The day report and the retro carry a `## Calibration` section.

Kill switch. `decisions.cruise.enabled = false` runs every class at L0 without changing any
running or configured level, so turning it back on restores them. The status line (5.9) then
shows `cruise off | L<max>`, the highest level a class would run at, and `cruise L<max>`
while it is on, followed by `· budget <classes> spent` while an error budget holds a class
lower, `· uncalibrated <roles>` while a role is stored uncalibrated (#559), and
`· shadow <classes>` while a class runs in shadow or waits for its raise card (#560).

Novelty (owner, 2026-10-08, #556). Blast radius is only known for targets the workspace
has touched. A decision or guarded action whose target is novel runs one level lower than
its class level, never below L0 and never above the ceiling. A target is a repository
(`repo:<org>/<name>`), channel (`channel:<id>`), person (`person:<ns>:<id>`), connector
tool (`tool:<server>/<name>`), dependency (`dependency:<ecosystem>/<name>`), environment
(`env:<name>`) or workflow (`workflow:<name>`). Under `autonomy.mode = "autonomous"` with no
cruise levels, one level lower means a card: `decision route` sends a record naming a novel
target to the owner (Routine included), an outward chat send to a novel channel holds as a
draft, and a standing grant pattern does not apply to a novel repository. Under supervised
routing does not change. A target is seen when config names it, or after the owner answered
one card for it (a Keep owner-only grant answer leaves it novel; for a draft only an
approval counts), or after an action on it was taken under mandate and not reversed within
the undo window, whichever comes first; the mandate form arrives with the cruise levels.
`init --upgrade` seeds the seen set from the CLI-written events and sent chat drafts of the
last 30 days, so an upgraded workspace is not asked about what it already uses. The CLI
keeps the first-seen date and the clearing in `memory/targets.json`, which no seat can
write (the records floor). A novel target never creates a grant on its own.

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
at 80 percent, a person's ask nearing its reply window, a telemetry week ready to send
(5.13)), `silent` (visible, never pushed:
normal progress, L3 cruise answers, auto-merges that went well). Lanes: Work (items by phase),
Decisions (waiting on the owner), People (asks owed by the owner, 15.10). An event the
classifier cannot read is a `nudge`, never `silent`.

Surfaces, all reading the same classification:

- Status line. `wuwei status --line` for the Claude Code status line (#521): one line of at
  most 100 columns (`--width <n>`), read left to right by importance. First the one thing to
  do now when there is one (`restart Claude Code: hooks <old> still running`, `no plan yet`,
  `gate waiting`, `decision D-n waiting`), then the day's items counted in words (`5 planned
  · 2 building · 1 in review · 3 shipped`, CAP only on the seats token) and the running
  seats by role with the bound that set CAP (`seats 4/1 by host.seats (lead, arch, +2 more)`,
  cut at whole names; #658), then pages, nudges
  and the posture when it is not guarded. `wuwei status` prints the same groups one per line
  with the detail: each running seat with role, item and start time, watch, listen,
  sessions, the next person reply due, the next meeting, the day's negotiation loops (5.8.2)
  and the plugin and template versions. It shares the hook latency
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

### 5.10 Specification mode (owner, 2026-10-03, #411)

Every item that is not trivial is specified with one configured spec engine before it is
built, and the hooks keep the engine's steps in order. `[spec]` in `config.toml`:

- `engine` (default `"speckit"`): `speckit`, `superpowers`, `openspec`, or `none`, which
  checks nothing (the behaviour before this section).
- `mode` (default `"strict"`): `strict` refuses at every enforcement point below;
  `advisory` lets each call through and records the first gap per item and day as one
  `spec.warned` event, which `wuwei next` and the report list; `off` checks nothing. The
  spec checks are not a 9.1 posture area: `mode` is their only setting, and under the
  `observe` posture `strict` runs as `advisory`.
- `skip_tiers` (default `["light"]`): the lead tiers (#280) whose items need no spec.

Engines. The builder runs every step, in order, with the engine's own command or skill;
the CLI reads only the artifacts, in the item's worktree, found by the item id lowercased
(the branch rule of `wuwei worktree add`). A step is done when its artifact is present and
reads as stated; a missing or unreadable artifact, or two paths that match the item, is not
done. The next step is the first one not done; artifact times are not compared. Every step
runs under `strict`; none is optional. Every engine ends with WUWEI's own validation: the
build loop's fast checks and the gates (5.3).

spec-kit: the feature directory is the one directory under `specs/` named `<item>` or
ending in `-<item>` (`create-new-feature.sh --short-name <item>`); each step is
`/speckit.<step>`.

| Step | Artifact in the feature directory |
|---|---|
| `specify` | `spec.md` |
| `clarify` | a `## Clarifications` section in `spec.md`: each question answered with the seat's recommendation as an assumption (5.3), or none |
| `plan` | `plan.md` |
| `tasks` | `tasks.md` |
| `analyze` | `analysis.md`, the saved report, with no finding of severity CRITICAL or HIGH |
| `checklist` | every item checked in `checklists/*.md` (`specify` writes `requirements.md`) |
| `implement` | every task in `tasks.md` checked |

Governing document (owner, 2026-10-10, #664). An analysis that checks the spec only
against itself misses a conflict with the document the item answers to. The lead names
that document on the candidate as `governed_by` (`<path>` or `<path>#<heading>`, relative
to the repository), which `plan approve` and `plan add` copy to the item; without it, a
`Governing: <path>#<heading>` line in `spec.md` names it, and the item's value wins. A
heading matches when its text equals the name or starts with the name and a space; the
section runs to the next heading of the same or a higher level. A spec-kit builder brief
for a governed item ends with a `## Governing document` block: the reference, the line
range, the section text and the instruction to end the analyze report with a
`## Governing` table, one row per `spec.md` assumption with the verdict `agrees`,
`conflicts` or `not covered` and the cited `<path>:<line>`. `wuwei spec analysis` refuses
(exit 2, nothing written) a governed item's report without that table, or with fewer valid
rows than assumptions, and a reference that is not a file in the worktree or names no
heading in it. A gate brief's `Spec:` line names the reference and the range; the goal
sentinel checks each row against its cited line and treats a `conflicts` row as a violated
requirement unless a recorded decision rules on it. Without a governing document nothing
changes.

superpowers: the skills of the superpowers plugin; the item is the topic in the file names.

| Step | Artifact |
|---|---|
| `brainstorming` | `docs/superpowers/specs/<date>-<item>-design.md` |
| `writing-plans` | `docs/superpowers/plans/<date>-<item>.md` |
| `executing-plans` with `test-driven-development` | every step in that plan checked |
| `verification-before-completion` | the fast checks and the gates; nothing more |

OpenSpec: the change is `openspec/changes/<item>/`, and after `archive` the one directory
under `openspec/changes/archive/` ending in `-<item>`; each step is `/openspec:<step>` or
the `openspec` command.

| Step | Artifact in the change |
|---|---|
| `proposal` | `proposal.md` |
| `specs` and `design` | at least one `specs/<capability>/spec.md`; `design.md` where the proposal needs one |
| `tasks` | `tasks.md` |
| `validate` | `validation.json`, the saved `openspec validate <item> --strict --json`, every entry valid |
| `apply` | every task in `tasks.md` checked |
| `archive` | the change moved under `openspec/changes/archive/`, before the gates |

The steps before implementation are the rows above `implement`, `executing-plans` and
`apply`.

Trivial items. An item needs no spec when the owner ran `wuwei plan set <item>
spec=skipped --reason <why>`, or when its lead tier (`items.<item>.tier`) is in
`skip_tiers` and the owner did not run `wuwei plan set <item> spec=required`. `plan set` is
an owner action, refused from agent tools like `config set`; it writes `items.<item>.spec`
(the value and the reason) and a `spec.override` event. A skipped item passes every check
below; the first check that sees it writes one `spec.skipped` event with the reason. A
tier skip holds only while the diff agrees: at the move to the gates, when the tier the
diff computes (#280, before the floor and the lead tier) is not in `skip_tiers`, the item
needs its spec after all.

Enforcement. Cooperative mistake prevention (9.1), in item worktrees only (the item whose
recorded worktree contains the path):

- PreToolUse on Write, Edit, MultiEdit and NotebookEdit refuses a path outside the
  engine's own directories (`specs/` and `.specify/`, `docs/superpowers/`, `openspec/`)
  while a step before implementation is not done. The reason names the next step, its
  artifact and its command, and the engine's install line when its files are absent from
  the repository.
- PostToolUse on the same tools and Bash records each step whose artifact newly appears as
  one `spec.step` event (item, engine, step, path) per item and day. It never refuses.
- The build loop (5.3) moves an item to the gates (implement to gate, fix to delta) only
  when every step is done, implementation included, on every runtime. A gap goes back to
  the builder as a failing check named `spec`, under the same error signature and stuck
  rule. `wuwei dispatch next` refuses the gates to an item at `gate` with a gap, naming
  the step.
- SubagentStop refuses a builder seat's stop while its last message does not name the
  item's artifacts (the spec-kit feature directory, the OpenSpec change, or the superpowers
  design and plan files).
- Briefs (5.2): the builder brief carries the engine's step table with the item's paths
  and commands, or the skip and its reason; gate briefs carry the artifact paths.

`spec.step`, `spec.skipped`, `spec.warned`, `spec.override` and `items.<item>.spec` are
written only by the CLI. The artifacts are written by the seat: they show the work was
done, never that the owner agreed; only `plan set` lowers the requirement for one item.

Engine presence. `wuwei setup` and `wuwei doctor` look for each engine in each configured
repository: `.specify/` for spec-kit, `openspec/` for OpenSpec, and a `superpowers@` entry
in Claude Code's installed plugins file (`scanner.mcp.plugins_file`) for superpowers.
Setup proposes the engine it finds, spec-kit when it finds none, and the interview asks
"Which spec engine do your repositories use?" with that answer first. A configured engine
absent from a repository is a doctor fail carrying its install line; `none` never is.
`wuwei calibrate` already reads `.specify/memory/constitution.md` as a convention source.

Seats and owner. The builder, lead and planner charters and the plan skill name the
configured engine's steps and the skip rule; the orientation block (`wuwei next`) shows the
engine and mode; the docs glossary defines spec engine and strict mode, and the
configuration page documents `[spec]`.
### 5.13 Telemetry (owner, 2026-10-03, #421)

Telemetry tells the owner, and the project when the owner agrees, whether WUWEI itself
works: how often its guards refuse or cannot run, how long a hook takes, how often items
loop, how many decisions reach the owner. Three layers: the signals the CLI already
records, a weekly aggregate computed off the hook path, and proposals from it; sharing is
optional and the owner's choice. Nothing runs in a hook and nothing derived is applied on
its own. `[telemetry]` in `config.toml`:

- `enabled` (default true): false stops the aggregate, the proposals, sharing and the
  OpenTelemetry export; the events a day needs are recorded as before.
- `share` (default `""`, not asked yet, which behaves as `"off"`): `"anonymous"`,
  `"attributed"` or `"off"`. Set by the interview question below, by the owner with
  `bin/wuwei config set telemetry.share`, or by `wuwei telemetry off`. A calibration
  profile (#313) never carries a `telemetry` key: consent is per workspace.
- `endpoint` (default: the project's collector URL, empty until the project deploys it):
  where anonymous mode posts. Empty, or not `https://`, keeps every week local.
- `repository` (default `"taoq-ai/wuwei"`): where attributed mode opens issues.

The cadence is a week and is not configurable; no hook keeps a clock for telemetry.

Signals. The raw layer is the events the CLI already appends, read through a fixed
vocabulary. Telemetry adds two fields to records that already exist, and no record and no
step to any hook:

- hook outcomes: each `refusals` row of `hook.refusal` and each `guard.would_refuse`
  gains `exit` (1 refused, 2 could not run); a `hook.refusal` without rows (a config that
  does not load, #326) counts as guard `config`, exit 2. Allowed calls are the PostToolUse
  rows of `traces.jsonl`. Heartbeat probe calls record nothing, as before.
- hook latency: the heartbeat (#287) already times its four hook probes (`refused`,
  `allowed`, `state_write`, `read_loop`) on every clock tick; each of those probe rows
  gains `ms`, the call's wall milliseconds including interpreter start: the hook as the
  owner feels it. The 10.6 CPU budget stays the benchmark's.
- seats: `seat launched`, `seat stopped`, `seat.usage` (its duration).
- items: `plan.approved`, `state.import`, `plan.added`, the `phase_changes` of state
  writes, `gate.received`, `gate.tiered`, `build.parked`.
- decisions: `decision.routed`, `decision.decided`, `decision.reversed`, and the record's
  `Class:` field (5.8).
- loops: `negotiation.loop` (5.8.2).
- owner interactions: `decision.decided` with `decided_by` `owner`; DM commands, the
  `remote.*` events written by `wuwei listen`; owner host actions, `remote.acknowledged`,
  `state.recovered`, `integrity_confirmation`, `mcp.decided`, `draft.sending` and
  `draft.dropped`.
- configuration facts, read from `config.toml` when aggregating: `security.posture`,
  `profile`, the adapter name per port, the number of repositories.
- versions, read when aggregating: the plugin version, Python major.minor, the OS family
  (`darwin`, `linux` or `other`).
- errors: the exit-2 rows above.

The vocabulary's version is `schema` in every aggregate and payload, starting at 1. Changing
a key or a definition below raises it and amends this section.

Aggregation. One step of the watch sweep (4.2), at most once per 24 hours (a `telemetry_at`
mark, like the steward's), never in a hook and never in a seat. It reads the day
directories under `days/` whose date falls in an ISO week (`2026-W40`, in
`owner.timezone`) and writes `.wuwei/metrics/<week>.json`, a generated record only the CLI
writes and that `protect_state` guards like `state.json`. Each run refreshes the current
week (`final: false`) and finalises each earlier week, of the last four, that has day
directories and no final file (`final: true`, with its proposals). Budget: 10 seconds of
wall time per run and 20 MB per `events.jsonl`; past either the run stops, keeps the
previous file and records `telemetry.skipped` with the week and the reason, and the next
run tries again. A telemetry failure never changes the sweep's exit and is never owed work.
`wuwei metrics --week [<week>]` prints a week's file, computing it when absent; it is a
command, never a hook.

Metrics, per week. A value that cannot be computed is `"unmeasured"`, never zero;
percentiles as in 5.6.

| Key | Definition |
|---|---|
| `days` | day directories in the week |
| `tool_calls` | PostToolUse rows in `traces.jsonl` |
| `refusals` | per guard (a hook-table module name, or `config`), refusal rows with exit 1 |
| `unmeasured` | per guard, refusal rows with exit 2 |
| `warnings` | per guard, `guard.would_refuse` records |
| `refusal_rate` | refusals over tool calls plus refusals |
| `unmeasured_rate` | unmeasured over refusals plus unmeasured plus warnings |
| `first_hour_refusals` | refusals, unmeasured and warnings in the first hour after the first event of the workspace's earliest day; present only in that day's week |
| `hook_latency_ms` | p50, p95 and max of the heartbeat hook probes' `ms` |
| `seats_launched`, `seats_lost` | `seat launched` records; launches with no `seat stopped` by the end of their day |
| `seat_minutes` | p50 and p90 of `seat.usage` durations |
| `phase_entries` | per phase, moves into it |
| `plan_to_merge_hours` | p50 and p75, from an item's first approval to its move to `merged`, for items merged in the week |
| `gate_rounds_per_item` | p50 and max of `gate.received` per item with a verdict in the week |
| `fix_rounds_per_item` | p50 and max of moves into `fix` per item with a verdict in the week |
| `gate_tiers` | per tier, the computed tier of `gate.tiered` (#280) |
| `long_loops` | `negotiation.loop` records: items over the loop threshold (5.8.2) |
| `stuck_parks` | `build.parked` records (5.3) |
| `decisions` | decision ids routed or decided in the week |
| `decisions_by_class` | per 5.8.1 class, from the record's `Class:`; unreadable counts as `other` |
| `decided_by` | `decision.decided` per `owner`, `seat` and `cruise` (any `cruise <class>@L<n>`) |
| `reversals` | `decision.reversed` records |
| `owner_wait_hours` | p50 and p90 from `decision.routed` to `decision.decided`, for decisions decided in the week |
| `owner_asks_per_item` | mean owner routes per item that had one (5.8) |
| `unnecessary_asks` | owner answers equal to the recommendation (5.8) |
| `owner_actions` | DM commands and owner host actions (Signals) |
| `escaped_by_tier` | per tier, merged items and escaped ones (#280), over the retained days |
| `lead_time_merge_hours` | median `cycle_minutes` over 60 of items merged in the week (5.6, #586) |
| `lead_time_deploy_hours` | median of that plus the hours from merge to the first deploy at or after it, for items whose pull request is in a deploying repository; read from the code host once, when the week is final |
| `deploys_per_week` | deployments (or published releases) created in the week; read from the code host once, when the week is final |
| `change_failure_rate` | escaped items (5.6) over items merged in the week |
| `time_to_restore_hours` | unmeasured until on-call incidents exist (#415) |
| `aggregation_ms` | the run's wall time |

Proposals. Finalising a week evaluates a fixed list of rules against it; a new rule amends
this section. A proposal carries its rule, one line of evidence (the numbers that met the
rule) and one owner command. Nothing is applied on its own, as with calibration (#278).

| Rule | When | Command |
|---|---|---|
| `floor-raise` | a tier below `full` has 5 or more merged items in `escaped_by_tier` and an escaped share of at least 0.2 | per repository whose floor is at or below that tier: `bin/wuwei config set repos.<n>.gates.floor '"<next tier>"'` |
| `floor-lower` | `full` has 10 or more merged items and none escaped | per repository at `full`: the same command with `standard` |
| `area-block` | a posture area running at `warn` had no `guard.would_refuse` in a week of at least 3 days | `bin/wuwei config set security.areas.<area> '"block"'` |
| `wait-hours` | 3 or more external waits (5.8.2) answered in the week, p90 under half of `decisions.wait_hours` | `bin/wuwei config set decisions.wait_hours <max(4, ceil(p90 x 1.5))>` |
| `fast-checks` | 5 or more items with a verdict and a `fix_rounds_per_item` p50 of 1 or more | `bin/wuwei calibrate --measure`, which proposes the fast checks itself (#328) |

Cruise promotions stay the steward's (5.8.1). A finalised week's proposals reach the owner
once, at the next morning gate: `wuwei telemetry proposals --widget` prints one yes-or-no
question per proposal (#359, yes recommended, the command named) and records
`telemetry.presented` for the week, so it is not asked again. Yes is the owner's command,
which records itself like any owner command (#414); no records nothing. Without
`--widget` the command lists the latest final week's proposals and writes nothing.

Sharing. Nothing leaves the machine unless `share` is `"anonymous"` or `"attributed"`, and
then only the payload of a final week, a JSON object with exactly these top-level keys:
`schema`; `week`; `token` (anonymous only); `versions` (`plugin`, `python`, `os`); `config`
(`posture`, `profile`, `adapters`, `repositories`), where `adapters` maps each port name to
its adapter name and `repositories` is a count; and `metrics`, the keys of the table above;
never the proposals or anything else in the file. Anonymisation, checked by
`telemetry.validate` before every send and by the collector on receipt:

- every key comes from this section; every key inside a metric is a guard module name,
  `config`, a phase, a tier, a 5.8.1 class, a posture area, `p50`, `p75`, `p90`, `p95`,
  `max`, `merged`, `escaped`, `owner`, `seat` or `cruise`; every key inside `adapters` is
  a port name; an adapter name is one shipped under `adapters/<port>/`;
- every value is a non-negative integer, a non-negative number rounded to two decimals,
  `"unmeasured"`, a version (`^\d+\.\d+(\.\d+)?$`), a week (`^\d{4}-W\d{2}$`), a token
  (`^[0-9a-f]{32}$`), a posture name (`observe`, `guarded`, `strict`), a profile name
  (`strict`, `standard`), an OS family (`darwin`, `linux`, `other`) or one of those names;
- so no repository, item, ticket, pull request, person, handle, path, branch, command,
  reason text or time finer than the ISO week; repositories appear only as a count;
- the serialised payload is at most 16 KB.

A payload that breaks a rule is not sent; the run records `telemetry.unsent` with the rule.

- `anonymous`: the sweep posts the payload as JSON over HTTPS to `endpoint` (stdlib
  `urllib` in the watch-service adapter, beside the heartbeat ping; 5 second timeout) with
  `token`, 32 hex characters generated once per workspace with `secrets` and kept in
  `.wuwei/metrics/token`, the only identifier. No login and no secret in the plugin. The
  collector, like any web server, sees the sender's IP address and does not store it. No
  endpoint, a network error or a non-2xx answer records `telemetry.unsent` and keeps the
  week for the next run, the four newest weeks at most; nothing waits or blocks. A 409
  answer counts as sent: the collector already has the week. A sent week records
  `telemetry.shared` (week and mode) and `shared` in its file.
- `attributed`: the sweep records `telemetry.ready` once per final week (a nudge, 5.9).
  The owner runs `bin/wuwei telemetry send`, an owner action on the host refused from agent
  tools like `config set`, which prints the exact issue, asks yes or no (#414) and opens it
  on `repository` with the code host adapter's `issue` (`gh issue create`). The issue comes
  from the owner's GitHub account and shows the owner's login: that is the difference from
  anonymous. Title `telemetry: <week>`; body the payload as a two-column Markdown table,
  without the token, so an attributed week never ties the anonymous ones to a person. The
  canary and honeytoken checks (7.1) apply; the outward-text lint does not, because the
  body is the validated rendering, not authored text.
- `off`: nothing is sent; the aggregate and the proposals continue while `enabled`.

OpenTelemetry export (owner, 2026-10-03). The vocabulary maps to OpenTelemetry without
translation: a day is a trace; each hook call and each seat run is a span with the
attributes `wuwei.event`, `wuwei.guard`, `wuwei.outcome` (`allow`, `warn`, `refuse` or
`unmeasured`), `wuwei.reason_code` (the guard and the exit class), `wuwei.posture` and
`wuwei.item`; decisions, loops, gate rounds and owner interactions are span events; the
weekly metrics are counters and histograms. A hook-call span takes its record's time and no
duration, since no hook keeps a clock; a seat span runs from `seat launched` to `seat
stopped`. `[telemetry.otlp]`, off by default and set only by the owner with `bin/wuwei
config set`:

- `endpoint` (default `""`, off): an `https://` OTLP/HTTP base URL on the owner's own
  platform.
- `headers_env` (default `""`): the name of the `.wuwei/env` variable holding the auth
  headers as comma-separated `key=value` pairs; the value never enters config, events or
  output.

While `enabled` and `endpoint` is set, each watch sweep posts the records appended since
the last export as OTLP/HTTP JSON to `<endpoint>/v1/traces`, and each newly finalised week
to `<endpoint>/v1/metrics`, built with stdlib `json` and `urllib` in the watch-service
adapter (no SDK, 5 second timeout, inside the 10-second budget above). An `otlp_at` mark
(the day and byte offset of the last exported record) advances only on a 2xx answer; a
failure records `telemetry.unsent` with mode `otlp` and the next sweep resends from the
mark, so nothing waits or blocks. The export carries only the attributes and counts above,
never command text, reasons or record bodies. It is the owner's own data, identifiers
included, so it never goes to the project and is not the anonymous payload. `events.jsonl`
stays the source of truth and what the aggregation reads.

`wuwei telemetry preview [<week>]` prints exactly what each mode would send for that final
week (the latest by default) and names the mode in force. `wuwei telemetry off` sets
`share = "off"` without a confirmation, since it only narrows what leaves, and records
`telemetry.off`; turning sharing on is the owner's (the interview or `config set`). Every
`telemetry.*` event is written only by the CLI; `telemetry.ready` is a nudge and the rest
are silent.

Interview. One workspace question after the posture: "Share weekly usage counts with the
WUWEI project?", choices in this order:

- Anonymous: "Counts only, sent over HTTPS with a random workspace id; no account, nothing
  about your code or people."
- Attributed: "The same counts as a GitHub issue opened from your gh account, so it shows
  your login."
- Off: "Nothing leaves this machine; the counts stay local."

Project side, in this repository and outside the plugin. `scripts/telemetry-worker/` holds
the collector: a small function that checks a payload with `telemetry.validate` itself
(the module is bundled at deploy), accepts only a `week` among the four ISO weeks before the
week of receipt and one payload per token and week (a repeat gets 409), takes at most 10
payloads a day per IP address kept in memory only, never written, and at most 1000 writes a
day in all (past either limit it answers 429), and writes it to a public dataset repository as `data/<week>/<token>.json`
with a bot token that lives only in the worker; plus a deploy note. The project's weekly
summary comes from the dataset (`scripts/telemetry-worker/summary.py`), not from the
plugin. Attributed issues are found by their title; a repository workflow labels an issue
`telemetry` when its title starts with `telemetry: `.

Residual risk. The token is unauthenticated, so anyone can post invented weeks; the
collector's checks bound what is stored and the summary counts per token. Its limits bound
how many arrive: a sender rotating IP addresses can still fill the daily cap, which spends
no more of the bot token than the cap and delays real weeks to a later run. A process
running as the owner can forge `.wuwei/metrics/` (9.1); the payload rules bound what such a
forgery can carry out to numbers in the schema.
### 5.11 Tracker hygiene (owner, 2026-10-03, #416)

Every work item lives in a ticket in the team's tracker, and the ticket carries the item's
story: its decisions, progress, verdicts, pull request and close. The tracker port (section
8) already reads the backlog and moves states (claim, in review, done, 4.6); this section
makes the ticket required, lets the day open tickets for what it finds, and writes the story
as comments.

Configuration. `adapters.tracker` is `linear`, `jira`, `github` (issues, plus Projects v2
when a board is set) or `none`. The schema default stays `none`, so a first day works on
defaults; `setup` and the interview recommend `linear`. `[tracker]` in `config.toml`:

| Key | Default | Meaning |
|---|---|---|
| `required` | `true` | every item needs a ticket; in force only when `adapters.tracker` is not `none` |
| `skip_tiers` | `[]` | tiers (`light`, `standard`, `full`, as in `repos.gates.floor`) whose items need no ticket |
| `strict_close` | `true` | day close refuses a merged item whose ticket did not reach the done state |
| `create` | `["bugs", "triage", "follow-ups"]` | the classes seats may open tickets for |
| `log` | `["decisions", "progress", "verdicts", "pr", "close"]` | the comment kinds written to an item's ticket |
| `auto` | `["progress", "pr", "close"]` | the write kinds sent without approval; every other write is a draft |
| `max_per_item_per_day` | `10` | comments per ticket per day, the fold included |
| `project` | `""` | where tickets are created: a Linear team id (empty: `backlog_filter`), a Jira project key, or a GitHub `owner/repo` (empty: the first configured repository) |
| `board` | `""` | GitHub only: a Projects v2 board as `<owner>/<number>`; empty uses labels |

`backlog_filter`, `states.in_review` and `states.done` keep their meaning for every adapter.
`auto` accepts the comment kinds and the creation classes plus `items`. The config check
refuses an unknown value in `create`, `log`, `auto` or `skip_tiers`.

Ticket of an item. `tickets` in `state.json` maps an item id to its ticket id and source,
written only by the CLI: `plan approve` and `plan add` record the candidate's `ticket` field
(the lead names it; GitHub ticket ids such as `owner/repo#12` are never item ids) or, for a
candidate discovered from the tracker backlog, the candidate id itself; `wuwei tracker
create <item>` records the ticket it opens; `wuwei plan set <item> ticket=<id>` records an
existing ticket once the adapter's `created(item)` confirms it exists. `plan approve
--import-yesterday` carries yesterday's tickets with the items. Every tracker operation on an
item (claim, transitions, comments, history for lead time) uses its ticket id; only while
`required` is not in force does an item without one fall back to its own id, as before.

Enforcement. While `required` is in force, an item whose tier is not in `skip_tiers` and that
has no ticket is refused by one CLI function, `tracker.check`, with one reason: `<item> has no
ticket: bin/wuwei tracker create <item> (opens one from the item's record) or bin/wuwei plan
set <item> ticket=<id>`, or, while a ticket draft for it is pending, `bin/wuwei drafts approve
<draft>`. The refusal points:

- `plan approve`: one refusal lists every approved item without a ticket; nothing is approved;
- `plan add` (intraday intake, 5.7): the candidate becomes an owner proposal with the reason;
- `build next`, before the claim, and `dispatch next`, before the gates;
- PreToolUse `Agent` launch for a brief whose item has none (4.1), part of the seat launch
  contract and so under the `seats` area (9.1).

The tier that decides is the item's recorded gate tier when there is one, else the lead's
tier; an item with neither is not exempt. An exempt item gets one `tracker.skipped` event at
admission. A gate tier that later rises out of `skip_tiers` makes `dispatch next` refuse until
the ticket exists.

Close. While `required` is in force and `strict_close` is on, `wuwei close` refuses while an
item merged today has no successful done transition (the `tracker.call` event that the merge
path writes, 4.6), naming `bin/wuwei tracker done <item>`, which runs the same transition
again. Carried and parked items keep their tickets open. With `strict_close = false` the same
line is printed and does not refuse.

Creation. `wuwei tracker create <item>` opens the item's own ticket (class `items`) from its
record: the title from the candidate's scope, the description from its evidence, goal and
track. `wuwei tracker create --bug|--triage|--follow-up <subject> "<title>" --evidence
"<line>"` opens a ticket of that class: a builder or a gate that finds a bug outside its
item's scope (`--bug`), the on-call seat for a triage result (`--triage`, 5.10; its subject
is the incident id), the planner for a follow-up the retro proposes (`--follow-up`). The
class must be in `create`, or the command refuses (exit 1) naming the key. The subject's
ticket is the parent: Linear creates a sub-issue, Jira links the two with a Relates link,
GitHub writes a `Related: <parent>` line that the host cross-references; a bug is a Jira
`Bug` and carries the GitHub `bug` label. Evidence lines are repository-relative (`file:line`,
a failing test id, a command); a line holding an absolute path is refused. Creation is
idempotent per class, subject and title: a second call prints the existing ticket or draft
and writes nothing. Each ticket that exists records one `tracker.created` event (class,
subject, ticket, parent), and the board lists the day's created tickets per item.

Comments. One CLI writer, `wuwei tracker log`, run by the watch sweep (4.2), by `wuwei close`
once the close passes, and on demand, turns the day's CLI events into comments on each
item's ticket, once each. Every entry has a stable key (its kind and subject), kept in
`tracker_log` in `state.json` with its outcome (written, drafted, refused, folded), so a
second run writes nothing new. The text is a template filled from the record and prefixed
`[<day> <item>]`; it is never a raw record and never holds an absolute path, and it passes
the outward lint (4.3) like any message. A refused entry is recorded with its reason and not
retried.

| Kind | From (CLI events) | Comment |
|---|---|---|
| `decisions` | `decision.decided` for a record naming the item | `Decision D-<n>: <question>. Outcome: <outcome>.` |
| `progress` | phase changes, builder and gate starts and stops, fast-check results, a park | one line each, such as `Phase: implement.` or `Fast checks: 3 passed, 1 failed.` |
| `verdicts` | `gate.received` | `Review <role> (<round>): <verdict>, <n> blocking findings.` |
| `pr` | `pr.raised`, `pr.claimed` | `Pull request: <url>.` |
| `close` | `wuwei close` | `Merged in <pr>.`, `Carried to <date> (D-<n>).` or `Parked (D-<n>).` |

Approval. Comments and creations are external writes sent as the owner, so they go through
the tracker port's text-bearing operations and the outward policy (4.9, 9.1): a write whose
kind or class is in `auto` is sent, and any other write becomes a draft in the draft queue
that the owner approves, edits or drops; the writer records it as drafted and never sends it
again. `auto` plays for the tracker the part that work channels play for chat: mechanical
text derived from records. The 4.9 rules still come first: a text that names a person,
matches a sensitive, commitment or disagreement pattern, or cannot be classified is a draft
whatever `auto` says, so the `message` ceiling of cruise mode (5.8.1) holds; tracker writes
are not decision records and cruise levels do not apply to them. A GitHub `project` or
`board` whose owner is not in `outbound.code_host_orgs` is an external party, so every write
to it is a draft whatever `auto` says; Linear and Jira tickets are internal to the
configured workspace or site. Every tracker write, comments and creations, passes the
humanizer pass of the outward policy (`[outward] humanize`, default true, #420) before it is
drafted or sent. With the defaults,
progress, pull request and close comments are sent; decisions, verdicts and every creation,
the item's own ticket included, are drafts. When the owner approves an `items` draft and the
adapter confirms the ticket, the CLI records it in `tickets`.

Loop cap. A ticket receives at most `max_per_item_per_day` comments a day. When the entries
waiting for a ticket at one run would pass the cap, the last allowed comment is one fold,
`Folded <n> updates: <kind> <count>, ...`, and the CLI writes one `tracker.folded` event with
the counts; entries after it that day are counted in `tracker_log` only and shown on the
board. A looping seat therefore cannot flood a ticket. Creations are not capped; they are
idempotent.

Adapters. The tracker port gains `comment(item, text, category)`. `create(draft)` takes the
draft `{title, description, item, category, parent}` and returns `{id, url}`, where `id` is
the ticket id every other operation accepts; `category` and `parent` are metadata to the
outward policy. Each adapter implements the whole port with `urllib`, reads its credentials
by name from `.wuwei/env` (kept out of seat environments), and passes the port contract test
against recorded fixtures. `claim` assigns the ticket to the credential's user; `history`
returns state changes in one shape for lead time (5.6).

| Adapter | Ticket id | Credentials | backlog, create, comment, transition |
|---|---|---|---|
| `linear` | `ENG-123` | `LINEAR_API_KEY` | GraphQL: the team's open issues; `issueCreate` with `parentId`; `commentCreate`; the workflow state with the configured name |
| `jira` | `PROJ-123` | `JIRA_SITE` (https), `JIRA_EMAIL`, `JIRA_API_TOKEN` | REST: JQL search of `project` not in the Done category, narrowed by `backlog_filter`; create a Task or Bug and a Relates link; add a comment; the transition whose target status has the configured name |
| `github` | `owner/repo#123` | `GITHUB_TRACKER_TOKEN`, a fine-grained token for issues and projects only | GraphQL: open issues of `project`, `backlog_filter` as a label; create an issue; add a comment; with `board`, the Projects v2 Status option with the configured name, otherwise a label for `in_review` and closing the issue for `done` |

Setup and health. `setup` reads each repository's README, CONTRIBUTING and pull request
template for tracker links (`linear.app`, `atlassian.net`) and prints what it found before
the interview. The interview asks where the backlog lives (Linear first, as recommended;
Jira; GitHub; none; or `<tracker> <project>` typed in), whether every item needs a ticket
(every item; all but `light` items; optional), and which tracker updates go without approval
(progress, pull request and close; those plus new tickets; everything; nothing). `doctor`
fails the tracker row when `required` is in force and the adapter cannot read the backlog,
naming the missing credentials or `bin/wuwei config set tracker.required false`.

Owner-facing. The board, `wuwei next` and the DM show an item's ticket id beside its name.
The documentation adds a `[tracker]` section to configuration.md, glossary entries (ticket,
tracker hygiene, fold), one paragraph in daily.md ("every item has a ticket; you see the
ticket id on the board and in the DM") and reference rows for `tracker create`, `tracker
log`, `tracker done` and `plan set`.
### 5.12 Documentation system (owner, 2026-10-03, #418)

Where the team's documentation lives, whether an item changed it, and pages written from
the records. With `docs.system = "none"` nothing in this section applies.

Configuration, `[docs]` in `config.toml`:

- `system`: `notion`, `confluence`, `markdown` (pages as files in the item's repository) or
  `none`. The schema default is `none`, so a workspace that never chose one is unchanged;
  setup and the interview recommend `notion` unless the repositories' links point
  elsewhere. The value selects the `docs` port's adapter (section 8); the config check
  refuses a name with no adapter under `adapters/docs/`.
- `required_tiers` (default `["standard", "full"]`): the gate tiers, named as
  `repos.gates.floor` names them, whose items carry the docs obligation. `light` items are
  exempt by default.
- `space`: the parent page for `notion` and `confluence`, as its id or its link; for
  `confluence` it is the `https` link, which also names the site. `root` (default `docs`):
  the directory, relative to the item's repository, for `markdown`.
- `publish` (default `["report", "retro"]`): what the day writes there besides item pages.
- `auto` (default `[]`): the write kinds (`page`, `report`, `retro`) written without
  approval; every other write is a draft (4.9).
- `strict_close` (default `true`): the day close refuses an unmet obligation; `false`
  lists it in the report instead.

The docs obligation. An item whose recorded gate tier (written when `dispatch next` tiers
it) is in `required_tiers` carries one `docs` value, set by `wuwei plan set <item>
docs=<value>` or by `wuwei docs page <item>`:

- `<page>`: the page it updated, as a page id or link, or for `markdown` a path under
  `root`; `plan set` reads it through the port and refuses a page that does not exist;
- `new`: a new page under `space`, written from the record after the merge. Under
  `markdown`, `plan set` refuses `new`; the builder runs `wuwei docs page <item>` before
  the gate, which records the path;
- `none, <reason>`: the item changes no documentation; the one-line reason appears in the
  report.

The builder sets the value before it stands down; the planner may set it. The value is the
item's own declaration, never an owner approval: the quality gate reviews it and the report
shows it. An item tiered outside `required_tiers` has no obligation and gets one
`docs.exempt` event when it is tiered.

Checks, at two points:

- Before the gate verdict. The quality brief carries the obligation and the recorded
  value. The quality sentinel checks the value against the diff under the `DOC` class: a
  missing value, or `none` for a change to documented behaviour (a command, a config key,
  an interface, user-visible output), is a blocking finding naming `plan set <item>
  docs=...`. `wuwei dispatch receive` refuses a quality `PASS` while the value is missing,
  so a missing value cannot pass the gate.
- At close. `wuwei close` refuses while an item merged today in a required tier has no
  value; has `new` or a `notion` or `confluence` page with no `docs.written` event for it
  since its merge; has its docs draft still pending; or, under `markdown`, names a path its
  merged PR did not change. Each line names its command: `plan set <item> docs=...`,
  `wuwei docs page <item>` or `wuwei drafts approve <id>`. With `strict_close = false`
  these are report lines and close does not refuse. A carried or parked item keeps its
  obligation for the day it merges.

Writes. `wuwei docs page <item>` renders the item's page from its records: the title (the
item id and the first line of its scope), what changed (the scope and the PR title), why
(the outcome of the goal it serves and the item's evidence), how to use it (the PR body's
`How to use` section when it has one), and links to the PR and the ticket (5.11) when they
exist. For `new` it creates the page under `space` and records the new page as the item's
value; for a page it appends a dated section, so edits made by people stay. Under
`markdown` it writes `<root>/<item>.md`, or the recorded path, in the item's worktree
before the gate; the builder commits it and it goes out with the item's PR.
`wuwei docs publish report|retro` writes the day's page once per kind per day, a second
call naming the first: the report page holds the report's Merged, Parked, Decisions
answered, Carry and Docs sections under `Report <date>`; the retro page holds the retro's
Applied and Proposed sections under `Retro <date>`. `wuwei report` and `wuwei retro` publish
their page when `publish` lists it. Under `markdown`, `publish` has no effect: there is no
pull request to carry the day's pages.

Approval and content. Every write to `notion` or `confluence` goes through the docs port
under the outward policy (4.3, 4.9): a kind listed in `auto` is written at once, any other
becomes a draft in the queue the owner approves, edits or drops, and the lint and the
sensitive-topic rules apply to both. Every docs write, `markdown` included, first goes
through the humanizer pass (`[outward] humanize`, default true, #420). A `markdown` write is a file in the item's worktree
that leaves through the item's PR and its gates, so it is never a draft. A rendered page
holds no raw record (state, events, verdicts, decision files), no absolute path and no
credential; the renderer refuses rather than strips. Every write is one `docs.written`
event (item, kind, adapter, page, draft id when it came from one); `docs.written` and
`docs.exempt` are written only by the CLI. Seats write documentation only through `wuwei
docs`: the default `outward.tool_patterns` add the Notion and Atlassian MCP write tools
under channel `docs`, so a direct MCP write meets the same policy.

Adapters. The `docs` port has two operations: `read(ref)` returns the page's id, title,
link and last update; `write(draft)` creates a page under `draft.parent` when `draft.ref`
is empty, otherwise appends to `draft.ref`, from `kind`, `item`, `title` and a Markdown
`body`, and returns the page's id and link.

- `notion`: REST, pages and blocks: read a page, create a page with the body as blocks,
  append blocks to a page. Credential `NOTION_TOKEN`.
- `confluence`: REST, pages: read a page with its version, create a page in the parent's
  space, append by updating the page with the next version number and the body in storage
  format. Credentials `CONFLUENCE_EMAIL` and `CONFLUENCE_API_TOKEN`; the site comes from
  `space`.
- `markdown`: files under `root` in the item's worktree, written atomically; no
  credentials and no network.
- `none`: records that it did nothing.

Credentials are named in `.wuwei/env` and kept out of seat environments. Each adapter
passes the docs port contract test with recorded fixtures; no test reaches the network.

Setup, interview and doctor. The interview asks "Where does your documentation live?" with
Notion, Confluence, Markdown and None, or a page link as free text that sets `system` and
`space` together. Setup reads each configured repository's README and CONTRIBUTING for
documentation links (`notion.so` or `notion.site` for `notion`, `atlassian.net/wiki` for
`confluence`, with the linked page as `space`) and offers the system it found first; with
none found Notion leads. `doctor` adds a docs row: `not used` under `none`; under `notion`
or `confluence`, a fail when `space` is empty, a credential is missing, or `read(space)`
could not run or found no page; under `markdown`, a fail when `root` is not a directory in
a configured repository; each fail names the fix; a warn when `publish` is set under
`markdown`.

Owner-facing: a `[docs]` section in configuration.md, glossary entries for the docs system
and the docs obligation, one paragraph in daily.md, and reference rows for `wuwei docs
page`, `wuwei docs publish` and `plan set <item> docs=`. The board and `wuwei next` show
an item's unmet obligation.

### 5.14 Memory over time (owner, 2026-10-03, #443)

Records grow every day; what a session loads must not. Memory has three tiers by age and
use, one producer per tier, and a token budget for what SessionStart loads.

- `raw`: a day's records under `days/<date>/`, complete and never edited. A day older than
  `consolidation.archive_after_days` (default 30) moves, at `wuwei consolidate`, into
  `archive/<year>/<date>.tar.gz`; `wuwei memory show <date>` prints it from either place.
  An archived day leaves `memory/index.md`; its month digest stands for it.
- `digest`: one Markdown record per ISO week (`memory/digests/<year>-W<week>.md`) and per
  month (`memory/digests/<year>-<month>.md`), rebuilt from the day records in a fixed
  shape: `## Decisions` (id, question, outcome), `## Lessons` (ledger lines landed or
  rejected), `## Metrics` (the report's outcome lines; the #421 effectiveness metrics join
  when #422 lands), `## Incidents` (page-tier events by kind), `## Items` (closed and
  carried). `wuwei close` rebuilds the current week; `wuwei consolidate` rebuilds the
  weeks and months of the days it archives plus the current ones. Free text in a line
  passes the outward lint (owner-addressed) and carries no path; a line that fails keeps
  only its structured fields (date, id, outcome label, target name, counts). `[memory]
  digest = "week"` (or `"off"`, no digests).
- `rules`: the local charter overrides and the spine and notes. Promoted rules live only in
  charters (6.8); a digest records that a lesson landed, never the rule text.

Budget. `[memory] budget_tokens` (default 6000) caps the SessionStart payload, built in
priority order: digests (latest month, then current week), rules (spine, note lines of
the index), today (raw day lines of the index, the promote line). When the whole would
exceed the budget, SessionStart loads digests and rules only and says so in one line. The
orientation block and `Active constraints:` (#358) precede the payload and are not part
of it. `doctor` warns when a raw day is older than the archive window, which means
`consolidate` has not run.

Forgetting. `consolidate` proposes, with one evidence line each, to archive a note no
brief, decision or retro under `days/` or the archive has named in 60 days; to fold one of
two near-duplicate notes into the other; to drop a charter rule superseded by a later
near-duplicate line in the same charter; and to drop a charter rule a later answered
decision contradicts. Proposals sit in `memory/forget.json` as `F-n`; `wuwei consolidate
--widget` asks them (#359) and `wuwei memory forget F-n apply|keep` is a host terminal owner
action. `apply` asks y/N, then lands the change through `wuwei promote`'s own landing,
which keeps the before text under `memory/archive/` and appends the ledger, and records a
`memory.folded` event. Nothing is removed without that record; `keep` declines and the
proposal is not asked again.

No duplicate memory. The harness has its own memory (CLAUDE.md, auto-memory, rules
files). WUWEI's records stay the source and nothing is read back from the harness. `wuwei
memory export --claude`, run by `consolidate` and by `promote` when a proposal landed,
writes the charters' rule lines and the current week's lessons as one block between
markers it owns into the workspace's `CLAUDE.md` (or `[memory] export_to`), idempotent.
Harness rules files (#441) get the same export when that item lands.

Digests, `forget.json` and the archive are producer-only records under the records guard
(9.1). `wuwei memory status` prints sizes and tokens per tier, the payload against the
budget, the last consolidate and the pending proposals.

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
  and prompts the user. Amendment (owner trial, 2026-10-03, #352): only seats park and prompt;
  registered non-seat sessions are noted once per day, unknown sessions are noted once per
  day and prompt once per day under strict.
- S3. MCP audit and drift. `/wuwei init` runs ZIRAN's MCP metadata analysis over the MCP
  servers attached to the session and registers them with `ziran watch-registry`; each
  morning plan runs the registry check, so a server whose tools changed after approval is
  flagged before any seat uses it. Amendment (owner, 2026-10-03, #325): the check scans only
  servers Claude Code would attach (project servers need approval), one server per scanner
  call, never runs an unpinned `uvx`, `npx` or `pipx run` launcher, and warns by default:
  `scanner.mcp.block` (default `["critical"]`) sets what blocks launches, while a check that
  could not run always blocks. Amendment (owner, 2026-10-03, #351): the default list is
  empty; the security posture decides (strict blocks critical, high and unmeasured).
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
| tracker | `backlog(filter)`, `claim(item)`, `transition(item, state)`, `create(draft)`, `comment(item, text, category)`, `history(item)`, `created(item)` | Linear (recommended), Jira, GitHub issues and Projects (5.11) |
| chat | `post(channel, text, thread)`, `dm(text)` | Slack |
| docs (5.12) | `read(ref)`, `write(draft)` | Notion (recommended), Confluence, repository Markdown |
| review_bot | `score(pr)`, `open_findings(pr)` | Greptile |
| runtime | `dispatch(role, brief_path, worktree, write)`, `status(job)`, `result(job)` (includes usage: tokens, cost, model, duration) | Claude (default), Codex |
| scanner | `audit(path)`, `gate(result, threshold)`, `traces(file)`, `mcp(servers)` | ZIRAN |
| code_host | `pr(ref)`, `checks(ref, sha)`, `reviews(ref)`, `threads(ref)`, `protection(repo, branch)`, `create_pr(draft)`, `request_reviewers(ref, logins)`, `comment(ref, text, thread)`, `merge(ref, sha)`, `revert_pr(ref)`, `issue(repo, title, body)` (5.13) | GitHub through `gh` (default); GitLab possible later |
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

Security posture (owner, 2026-10-03, #331). What the cooperative guards refuse is
configurable by where the plugin runs: `security.posture` is `observe`, `guarded` (default)
or `strict`, and `[security.areas]` overrides one area with `off`, `warn` or `block`.
`guards.mode = "shadow"` (#308) is deprecated and means `observe`.

Autonomy (owner, 2026-10-05, #530): under `observe` and `guarded` a guard is a warning or a
card, never a wall, with one floor: records are written by the workflow and answered by the
owner. A refusal that names the plain form the seat runs itself is coaching, not a wall.
Under `strict`, refusals stay.

| Area | What it covers | observe | guarded (default) | strict |
| --- | --- | --- | --- | --- |
| `records` | State, events, config, generated instructions, verdicts, decisions, traces, session records (`protect_state`, `decision`, `verdict`, `traces`, `lifecycle`) | block | block | block |
| `publish` | Commit and push rules, the owned-PR anchor and day close (`commit_push`, `stop`); deploys and PR actions (`deploy`, `pr`) | warn | block | block |
| `integrity` | The plugin integrity gate (`integrity`) | warn | block | block |
| `mcp` | The MCP registry launch gate | warn | warn | block |
| `outward` | The outward text lint (`outward`) and the question citation check (`decision.check_question`) | warn | warn | block |
| `seats` | The seat launch contract: logged brief, capacity, memory, clean worktree (`agent_launch`) | warn | warn | block |

Below strict a `block` is a card (deploy, release, publish, evidence; merge with #524) or a
fix the seat runs; only `records` is a wall.

Floors no posture and no override lowers:

- `records` always blocks, with canary and honeytoken egress and owner disposition markers, whose refusal reads `posture: records = block (floor; no setting lowers it)`. An override below `block` is a `config check` finding (exit 1), and every hook then fails closed as for any broken config.
- Owner-only actions (`deploy`, `pr`, and approve-tier messages through `outward`) block, and below strict they ask on a card: a deploy, release or publish asks the owner, and only the owner's recorded answer (once, today, always) lets the same action through (#478); a held message is a draft card (#526). Below strict such a refusal carries no `owner-only action` line; under strict it keeps it. Admin merge, approvals and branch protection stay owner-only. Amended (owner, 2026-10-05, #524): a merge the merge policy does not clear asks the owner on a card like a deploy, and the grant never lifts a 4.6 precondition. Raising a PR and pushing a feature branch are not owner-only: they follow `publish`, and missing evidence asks on a card (once, today) under guarded (#530).
- MCP: under `guarded` and `strict` a registry check that could not run blocks launches whatever `security.areas.mcp` says, unless it is `off`. A finding blocks only at a severity in `scanner.mcp.block`, which is unset by default: no severity under `guarded`; `critical`, `high` and `unmeasured` under `strict`. Under `observe`, and with `mcp = "off"`, the list has no effect and `config check` says so.

The posture changes what the cooperative guards refuse, never the hard boundaries above.

### 9.2 Safety invariants (owner, 2026-10-05, #530)

The hooks are the runtime monitor; this table is the property list they are checked
against. `tests/test_invariants.py` checks every row on every case of posture x audience x
topic x kind x grant state x umbrella x connector mode, and walks every guard reason under
`observe` and `guarded`.

| Id | Invariant | Checked by | Notes |
| --- | --- | --- | --- |
| I1 | Under observe and guarded no path reaches a wall except the records floor | the reason corpus levelled by `hook.posture`; per case, `classify` and the deploy guard | Owned: config and integrity re-confirmation through the card record (the follow-up in `specs/530-posture-day`, Deferred). Exempt: the merge family (a session merge names `bin/wuwei merge`, #524; approval, `--admin`, branch protection and a shepherd merge stay the owner's), the heartbeat probe, `permissions.deny` (deferred), the owner's own Keep answer, owner-written block rows, day state recovery, unknown git (the hook levels it to a warning below strict); a broken config is records |
| I2 | Every held message has a card path that leads to a send | per case, a held `classify` result; per posture, hold, the Draft card answered Send now, approve, the same call sends | Under strict the owner approves at the host |
| I3 | A merge happens only at the head the gates checked with green required checks | per posture, the `pr` guard refuses a session `gh pr merge` and `--admin`, naming `bin/wuwei merge`; per posture x grant x head, `merge.execute` merges only at the gated, green head with a matching grant | #524; a grant lifts only auto-merge eligibility and pacing, never a 4.6 precondition |
| I4 | A message to the owner's own DM always sends | per case, chat to the owner DM | |
| I5 | No seat, default or hook creates a grant | per case, grant rows and `grants.standing` before and after the deploy guard and the record gate; the shipped config | A once grant is spent, never created; the shipped `merge.default_tier` is empty; `today` is written only by the owner's autonomy answer (#530) |
| I6 | A seat never posts an owner disposition marker | per posture, an MCP payload and `gh pr comment` carrying `WUWEI parked ` | Records floor |
| I7 | Docs and tracker writes follow `docs.auto` and `tracker.auto` | per case, WUWEI's own adapter write; a connector write under the send umbrella | #535 |
| I8 | A record command runs from the planner only after a card answer outside strict | per case, `bin/wuwei decide D-1 once` and `bin/wuwei config set cap 2 --from-card D-1` through `protect_state` from the planner and a seat | #529 |
| I9 | A branch push and a PR raise with recorded evidence succeed from the planner and the builder below strict, and a tag push with a release grant or an Allow once release card passes | per posture, through the hook | #547; below strict the deploy guard's release card and grants gate a tag and `push_check` passes it; under strict `push_check` refuses it |
| I10 | Under observe and guarded no opaque read-only command is refused | per posture, a script read, a `$(...)` read and a `python3 -c` print through the hook | #547 |
| I11 | A class runs lower only when its error budget is spent (more events than the allowance and at least two), never on a single event and never through a refusal | `budget_classes.measure` on 3 of 20, 2 of 20 within 48 hours, none, and 1 of 5; no single-trigger lowering left in `cruise` | #558; the lowered class routes its records to a card and is restored when the window refills |
| I12 | A class or role is uncalibrated only when its Brier score over at least calibration_min scored records is above calibration_threshold; an uncalibrated class runs at most L1, an uncalibrated role only moves a record toward the owner, never through a refusal | `calibration_scores.measure` on 12 high with 5 broken, 10 high stood and 9 high stood; `cruise.level` with and without a stored class; `cisr(..., ambiguous=True)` on a Routine and a Consequential record | #559; too few blocks promotion only |
| I13 | A shadow never changes a live route | `cruise.level` with and without a stored shadow row, for every class, shadow level and state, cruise on, off and supervised; the full route equality in `tests/test_cruise.py` | #560 |
| I14 | A raise lands only after a passed shadow | a raise card with no shadow answered `raise` leaves the running levels unchanged | #560; the #558 budget restore is the one raise with no card |
| I15 | No pace lowers a floor: a tier never drops, depth is light only for a light tier or fast on a measured, unflagged standard item without guard code, and no pace plans more seats than the host fits | `pace.adjust` on every pace, tier, guard, flag and measurement; `pace.seats` on every pace and load; `dispatch.depth` on an untiered item and for a gate reader | #579, #567 |
| I16 | No pace changes who decides | `cruise.level` for every class and `decision.route` on a two-way and a one-way record with the day at each pace; `plan set pace=fast` through `protect_state` passes for the planner below strict, never for a seat | #579 |
| I17 | Fast merges only at green required checks | the merge policy, the PR guard and the launch guard never read the pace; `merge.green` on a pending required check is not green | #579; I3 keeps the gated head |
| I18 | The setup answers never allow a publish target | per posture, `grants.active` with `merge.default_tier = "today"` covers only a merge on a configured repository below strict; no `init.allow_rules` rule matches a deploy, release, protected-branch push or force push | #530 |
| I19 | A thread reply follows its recorded participants: a team participant sends, a client or public one is held as a draft, never blocked, below strict | per posture, audience and umbrella, `classify` on a reply in thread `C0TEAM/1.2` whose recorded participant is one person of that audience | #526 |
| I20 | CAP comes from the host: the owner's cap when set, else, for seats that are separate processes, the seats that fit above the memory floor, one per core, at least one, and for Claude subagent seats one per core whatever the free memory; a token budget never raises it | `calibrate.host` on free memory below the floor, one seat and eight seats above it, x 1 and 4 cores x owner cap 0 and 3 x no budget and a budget with no recorded usage x a process and a subagent seat policy | #528, #658 |
| I21 | An internal-state word (`outward.patterns`) never refuses or holds a tracker, docs or other write; team or company chat is never held and is refused only under strict; a client or public chat an owner row would send is held as a draft naming the word | per posture, audience and kind, `classify` and the outward lint with and without the word, with owner rows that send to the client and public channels | #533 |
| I22 | A record keeps a two-way door only when the CLI knows the undo for its action and that undo ran once in this workspace; a message never does | `undo.measured` for every class and no class with an empty ledger and a full one; a seat's Write to `memory/rehearsals.json` | #557; the pinned cases stay in `tests/test_undo.py`. #600: a config write that records its previous value is two-way; its undo is config set with that value, so it needs no rehearsal |
| I23 | A target the workspace never touched goes to the owner once, and only an owner answer, config or the seed clears it | `decision route` on a two-way Routine record naming a new repository under autonomous; a seat's Write to `memory/targets.json` | #556; the pinned cases stay in `tests/test_novelty.py` |
| I24 | Every guard reads the same people, channels and connectors from the register as from `config.toml` | `graph.drift` of the register built from the fixture's people, channel classes and connector modes | #552; the guard-decision equality stays in `tests/test_graph.py` |
| I25 | Doctor and the commit and push guard agree on `repos.N.identity`: both pass a set one, both fail an empty one with the same reason and the same `bin/wuwei config set` fix | doctor's identity row against `commit_push.unset_identity`, the helper the guard raises from, with a set, an empty and a malformed identity | #605; one helper, `commit_push.unset_identity`; doctor fills in the identity git resolves; the guard and native hook runs stay in `tests/test_commit_push.py` and `tests/test_git_hook.py` |
| I26 | Every command `next` returns to start a planned item exits 0 in a multi-repository workspace: `worktree add` names the candidate's `--repo`, and an item with no repository is parked with its reason | `dispatch._start` on a two-repository fixture with one candidate carrying `repo` and one without; the `worktree add` command run through its command function with the VCS boundary faked, and the other item's command is `plan park` | #603; one repository keeps `worktree add <item>`; `tests/test_dispatch.py` runs the park through `main`; the walking day in `tests/test_path_day.py` runs the brief too |
| I27 | A fresh day's gate-confirmed proposed goals approve the plan, and approve never writes owner memory | `plan.approve` over the empty goals template with the day's `goals.md`; `memory/goals.md` unchanged after | #603; `goals edit` records them after the gate and stays the owner's under strict |
| I28 | A stored interview answer never overwrites a key present in `config.toml` with a value other than its default unless `config promote --keys` names it | an autonomy answer recorded with `autonomy.mode = "supervised"` present: the promote proposal keeps it and lists it, the proposal with `--keys autonomy.mode` applies it | #604; measured repository facts and `setup` apply as before |
| I31 | An empty fast-check list never refuses a launch below strict | per posture, `build._repo` on a repository with `fast_checks = []` and no card answered | #600; strict refuses naming `calibrate --questions` until the owner answers the fast-checks card |
| I32 | A config card with a list value records without a prompt below strict | per posture, a routed card with a Value row `repos.0.fast_checks = ["make test"]` answered in the planner session, then `config set --from-card D-n` with the host prompt failing | #600; strict prints the command for a host terminal |
| I33 | A config record is never Strategic on its own | Class `other` and none x door one-way, two-way and unsure x confidence high and low: `undo.correct`, then `cisr`, on a record with Value rows and a Previous line | #600; a seat's better class stands |
| I34 | A docs-only diff never lowers review when anything else would raise it: a lead flag, a FULL track, a trust, never-auto, FULL-pattern, binary or agent-instruction path, or a full floor keeps arch, quality and security; a plain document with nothing raising it gets one reviewer | `dispatch.tier` on a document diff, alone and with each raising path, under each lead flag, track and floor | #622; one decision in `dispatch.tier` (`_docs_role`); goal for a document, quality for a spec or pre-registration |
| I35 | No item opens a fix round past its round cap: `build.open_fix` refuses at the cap and `dispatch next` turns a blocking finding at the cap into a park with the finding and what would unpark it | `dispatch.max_rounds` for `gates.max_rounds` 1, 2 and 3 x each tier override 0, 1 and 3 x each item tier; `build.open_fix` on an item whose build used its cap, with and without a tier override | #623; one cap read in `dispatch.max_rounds`, one round opened in `build.open_fix`; after the cap non-blocking notes ship in the PR body |
| I36 | An item ticket is attached by the planner below strict or by the owner, never by a seat: `tracker create <item>` and `plan set <item> ticket=<id>` pass for the registered planner below strict and never for a seat, whose reason names the planner; `tracker create --bug` stays a seat command | per posture, `protect_state.check_bash` on both commands for the planner and for a seat, and on a seat's `tracker create --bug A Broken --evidence cli/x.py:1` | #636; the gate's Approve opens the tickets the plan proposed; under strict the owner runs the commands in a host terminal |
| I37 | An item with `owner_merge` set is never merged by WUWEI: `merge check`, `wuwei merge`, `pr act`, the PR guard and the overnight shepherd refuse naming the flag, under any grant; cleared, they follow the normal policy | `merge.owner_hold` on a set, cleared, absent and malformed record in the walk; the path table `test_owner_merge_holds_on_every_path` (each path x flag set and cleared x no grant and a today grant) | #678; one read in `merge.check`; only `wuwei plan set` writes it; agent tools set it, the owner clears it |

A later item that adds a rule adds its row here and its check to `tests/test_invariants.py`.

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
