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
  asks the owner only for decisions the mandate does not take (5.8), work outside the
  goals, and merges the merge policy does not clear (4.6).
- G2. Guards enforce the rules at the moment of action. A rule that can be broken without a
  refusal is not a rule.
- G3. Security first: agent tool permissions are least-privilege and audited, live sessions
  are checked for dangerous tool sequences, and items that build agents are gated by an
  agent security scanner (ZIRAN by default).
- G4. Memory that outlives the session: episodes, procedure and settled facts, each with one
  home and one writer.
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
- A hosted service or database. A long-running process is out of scope for v1; M5 added
  exactly one, the listener (section 15), (retired by #789, owner, 2026-10-10). The optional telemetry collector (5.13) is the
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
  skills/            wuwei-init, wuwei-plan, wuwei-report, wuwei-retro
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
  templates/         workspace skeleton
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
    goals.md           the owner's goals (5.7); plan approve or the owner writes it
    index.md           generated; one line per past day
    notes/baseline.md  the owner's baseline (5.6)
    archive/           dropped charter rules
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
  inbound and control-plane parsing (retired by #789, owner, 2026-10-10). Each translates its input into one core call and its
  result into the caller's format. None holds a rule.
- Tests: the core is tested against fake adapters and recorded fixtures, never against the
  real tools or the network; adapters get contract tests plus recorded-output tests.

## 4. Guards

### 4.1 Hook table

| Event | Trigger | Refuses when |
|---|---|---|
| PreToolUse | `Agent` launch | no brief logged for it; a gate seat while its item's builder is live or its tree is dirty; running seats at CAP or free memory below the configured floor; an item without a ticket while tracker hygiene requires one (5.11). An untyped launch (`general-purpose`, `Explore` or any type outside the WUWEI seats) in a day is registered as an adhoc seat, never refused; `bin/wuwei seat start --role <role> --adhoc "<prompt>"` labels it (#676). The `WUWEI brief: <path>` line may stand on any line of the prompt; the text around WUWEI's launch prompt is kept on the seat as its planner note, which `wuwei why <item>` shows. A WUWEI seat type launched with no brief line, or with a brief that does not match, is refused naming `bin/wuwei brief <role> <item> <name>` while `guards.enforce` is on; with it off the seat is registered as an adhoc seat labelled with its role, with that warning. The CAP, host seat, free memory and ticket refusals are logged as `guard.would_refuse` either way (#837), and every launch refusal the hook lets through is shown to the session as `seat not registered: <reason>` (#660) |
| PreToolUse | `git push` | a force push in any form (`--force*`, `-f` in a flag cluster, `--mirror`, a `+` refspec), or a push to a configured repository's default branch, naming `bin/wuwei pr raise ... --item` (#839); identity, the default branch and the fast checks stay with the native Git hooks |
| PreToolUse | `gh pr create` | a recorded item that links no PR, naming `bin/wuwei pr raise ... --item` (#783, #837, #839: from the item worktree, after `cd <recorded worktree> &&`, or with `--repo` and `--head` naming its branch); the gate set and the reviewer rule run in `bin/wuwei pr raise` |
| PreToolUse | `gh pr merge` | always, naming `bin/wuwei merge`, which runs the merge policy (4.6) (#839) |
| PreToolUse | `gh pr review --approve`, `--admin`, protection changes | always |
| PreToolUse | any deploy action (4.7) | always |
| PreToolUse | an MCP tool not on `outward.allow` that is not local (4.9) | the call may send to other people (a write), whatever `guards.enforce` says; the outward-text lint (4.3) logs its findings |
| PreToolUse | Write or Edit on `state.json`, `events.jsonl` | always; state changes go through the CLI |
| PreToolUse | Write, Edit, MultiEdit or NotebookEdit in an item worktree, outside the spec engine's directories | under spec mode, a step of the configured engine before implementation is not done for the item (5.10) |
| PreToolUse | top-level `cd` out of the workspace | always; use `git -C` or a subshell |
| PostToolUse | any tool | never refuses; appends the call to `traces.jsonl` in OTel JSONL shape |
| PostToolUse | write to `decisions/gate-*.md` | verdict lint fails; the verdict is returned to the seat |
| PostToolUse | `AskUserQuestion` | never refuses a well-formed card; records the owner's answer to an Owner step card for the command that asked it (#831) |
| PostToolUse | Write, Edit, MultiEdit, NotebookEdit or Bash in an item worktree | never refuses; records each spec step whose artifact appeared (5.10) |
| SubagentStop | a seat finishes | its three-line retro note is missing, or a builder's last message does not name its spec artifacts (5.10); otherwise records it |
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
  code host, never from memory: `conflicted` (not mergeable against its base), `ci_red`, `base_red`,
  `changes_requested`, `threads_unanswered` (the reply obligations above), `review_stale`
  (awaiting review past `pr.review_window`), `approved`, `merged`. Each state names its
  required action and a deadline (`pr.action_minutes`, default 30):
  - `conflicted`: rebase in the item's worktree, resolve, run the fast checks, push;
  - `ci_red`: a fix round in the item's worktree;
  - `base_red` (#728): every red check also fails at the PR's base commit, so no action: the
    item waits and `pr state` prints `base_red: <check> fails at <base sha> too`;
  - `changes_requested` and `threads_unanswered`: triage each thread: a fix request becomes a
    fix round, a question gets a reply (auto-send tier for team PR threads, 4.9), a
    disagreement or scope change becomes a decision for the owner (5.8);
  - `review_stale`: re-request review, then post in the review channel;
  - `approved`: `wuwei merge` when the policy clears it (4.6), otherwise a merge decision;
  - `merged`: done.
  An overdue action is a `warn` (owner, 2026-10-10, #789), then a `page` at twice the deadline (5.9).
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
  Shepherd card in a session) sweeps the
  owning day: the newest day, today included, whose plan is approved. It does nothing while a
  planner session is live. It checks an `approved` PR against the 4.6 policy and queues it;
  until #524 lands the merge waits for the morning `wuwei pr act`. It sends a `review_stale` ping through 4.9, and
  queues every other state with its evidence as `shepherd.overnight` events, which open the
  next morning plan. It never replies, fixes, rebases, starts a seat or calls a model.
- Anchor at every turn. The Stop hook refuses to end a planner turn while any owned PR has an
  action past its deadline and no park, naming the PR, its state and the
  action. The day close additionally requires every owned PR merged, parked or explicitly
  carried to the next day.

`wuwei next` shows one row per owned PR: state, last action, what it waits on and time to
deadline, so the owner never checks PRs one by one.

### 4.3 Outward-text lint

Configured in `config.toml`: the owner's name and pronouns (never used in third person in
text sent as the owner), banned characters, and a maximum length per channel. A message only
the owner reads skips the third-person rules. The internal-state patterns (`outward.patterns`)
were retired with the audience classes (owner, 2026-10-11, #838).

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
2026-10-05, #530): an opaque command runs with one `guard.would_refuse` warning
naming what could not be read, unless its literal text names a publish target (a
protected-branch, force, tag or no-verify push, a deploy, a release, a gh merge, approval,
admin, protection or text write, a hooks path change); the records floor stays.
Amended (owner, 2026-10-11, #839): guards match exact argv per command segment (`shlex`), with
leading assignments, `env` and `sh -c` unwrapped and here-doc bodies skipped. A call they
cannot split is logged, never refused. Interpreter snippets, scripts, aliases and names built
at run time are not read: the code host and the credential layout hold them.

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
A merge the policy does not clear is the owner's decision on the Owner step card of
`wuwei merge <pr>` (5.8), with the conditions below unchanged.

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
  30), during which the owner can veto from the control plane (retired by #789, owner, 2026-10-10).

Mechanics: `gh pr merge --squash --match-head-commit <sha>` (or the repository's merge queue),
so a push between the check and the merge makes it fail rather than merge unreviewed code.
Never `--admin`, never a change to branch protection, never an approval. At most
`merge.max_per_day` auto-merges per repository (default 5); none during quiet hours.

After the merge: the watch follows the base branch's checks for the merge commit. A red check
opens a revert PR at once, pages the owner, and trips the breaker. Every merge is an event
carrying the evidence (head sha, verdicts, checks, approvals).

Circuit breaker: auto-merge turns off for a repository, until the owner turns it back on,
when a merged PR is reverted or red on the base branch, or when the rolling 14-day escaped
defect rate for auto-merged PRs (5.6) exceeds the owner's baseline. Any precondition that
cannot be read is exit 2: not cleared, so the merge goes to the owner.

Amended (owner, 2026-10-11, #816): the merge policy alone decides a merge.
Quiet hours, the daily cap and the soak are waits the policy clears later; every precondition
above holds at the current head and names its condition. The eligibility rules (`merge.auto`,
the breaker, the approved plan, risk flags, the cycle budget, never-auto paths, size and
`[merge] owner_paths`) are the owner's decision: when only they stand, `wuwei merge` prints one
Owner step card for that PR at its head, `wuwei next` names it, and the owner's recorded Yes
merges it, journaled and watched like an auto-merge.

Amended (owner, 2026-10-10, #668): a PR whose head turns a check that fails at its base commit
green skips the soak (`merge.soak_skip`: `base_fix`, the default, or `never`); every other
rule still holds. A held merge reads either `waits: soak ends at <time>` or
`owner merges: <rule>`, and `wuwei merge check` prints the next step on a `Next:` line.

Amended (owner, 2026-10-10, #675): `trust_surface` makes the security gate required instead of
the item ineligible. A flagged item is eligible once `security` is in its recorded gate set and
its verdict is PASS at the head, delta round included; until then the PR waits on the gate,
never on the owner. `boundary_relevant` and `agent_surface` are unchanged. A diff touching a
`[merge] owner_paths` glob, renames included, is the owner's decision (#816); the reason names
the path and the glob.

Amended (owner, 2026-10-10, #785): the merge method follows the repository:
`repos.merge_method` (`auto`, the default, `squash`, `rebase` or `merge`). Under `auto` WUWEI
uses the first method the repository and its rulesets allow of squash, rebase, merge; an
explicit method is used only when allowed. Where the text above says `--squash` it reads
`--<method>`, and where it says the repository must allow squash merges it reads the chosen
method; `wuwei merge check` names it. A merge commit or rebase merge is followed for red base
checks and reverts; the 14-day line outcome is measured for squash merges.

### 4.7 Deployment ban (owner, 2026-09-28)

WUWEI never deploys, in any profile, routine or remote command. Refused always, after the
normalisation in 4.5: dispatching or re-running a workflow the config marks as deploying,
`gh release create` and tag pushes, pushes and merges to branches in the configured
environment register (for example `production`, `release/*`), GitHub deployment and
environment API calls, and the deploy commands of common tools (`kubectl apply`, `helm
upgrade`/`install`, `terraform apply`, `pulumi up`, `vercel`/`netlify` deploy, `fly deploy`,
`gcloud`/`aws`/`az` deploy verbs, `docker push`), extendable by `deploy.deny` in config. A
merge into a repository with `merge_deploys = true` is a deployment and goes to the owner.

Amended (owner, 2026-10-11, #816): the guard refuses and prints the Owner step card of that
exact command; only the owner's recorded Yes on it lets that command through, the same day. No
standing line, seat, default or hook answers for the owner. The hook matches these by exact
argv (#839); a session merge is refused naming `bin/wuwei merge`, which checks
`merge_deploys` and environment bases.

### 4.8 Voice (owner, 2026-09-28)

Retired by #789 (owner, 2026-10-11, #833).

### 4.9 Outward sends (owner, 2026-10-11, #838)

The approval tiers, audience classes, drafts, learning cards and the register of 2026-09-28
were retired by #789 (owner, 2026-10-11, #838). Outward sending is one exact allowlist.

- An MCP send to other people leaves only through a tool named exactly in `outward.allow`
  (no pattern, prefix or case folding). Any other write is refused on the floor, naming the
  one line the owner adds: `bin/wuwei config set outward.allow '["<tool>"]' --add`, which asks
  its Owner step card in the session (#831). For a canvas or page id the refusal first names
  `outbound.owner.pages`; for mail, `outbound.owner.mail` only while it is unset, never with an
  address filled in. Reads
  pass. A tool that is neither a read nor a write by name and names no channel runs; the lint
  guard logs the line (B5 lead call: no new walls).
- Local: a tool that acts only on the owner's machine (#727), and a call whose every
  destination is the owner's own surface, are never outward sends. The canary check and the
  outward lint still run; the lint skips its third-person rules for the owner's surfaces.

| Surface | The owner's config | Matches |
| --- | --- | --- |
| Slack self-DM | `outbound.owner.slack.dm`, `outbound.owner.slack.user` | a message whose channel or recipient is one of them |
| Slack canvas | `outbound.owner.pages` (canvas ids) | a canvas write whose `canvas_id` is the owner's |
| Notion or Confluence page | `outbound.owner.pages` (page ids) | a page update by `page_id`, or a create whose `parent.page_id` is the owner's |
| Mail to self | `outbound.owner.mail` | every recipient, cc, bcc and address in the text is the owner's |

  A call with no destination never resolves to the owner. A code-host comment is never local.
- Duties: WUWEI's own outward writes (a PR review ping, a tracker comment or ticket, a docs
  page, the day report, a PR thread reply through `pr act --reply`) go through its adapter
  ports, configured by the owner. Each runs the canary check, refuses owner disposition
  markers, runs the outward lint and then sends; none needs `outward.allow`.

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
| steward | at each sweep and at close, fresh seat | the retro and charter proposals |

### 5.2 Flow

```
/wuwei plan -> planner -> lead -> MORNING GATE (user approves or edits)
  -> per item: builder -> pre-PR gates in parallel (arch, quality, security; goal on docs)
  -> shepherd raises, requests reviewers, posts, and owns the PR until merged (4.2.1)
  -> fix round -> arch delta -> ... -> merge policy: auto-merge, or the user merges
/wuwei report -> steward retro -> planner report -> Stop guard
```

Briefs (amended 2026-10-01, #301; amended 2026-10-11, #789 part 14). Every seat brief carries a
mandate block of three fixed lines: decide alone what the brief, the charter and the
standards answer; record two-way choices under `Assumptions:` in the spec or PR body (5.3);
name a one-way, scope, goal or trust-boundary question in the result (a sentinel's ESCALATE,
a builder's `Blocked:` line), which `wuwei next` asks the owner. It adds the commands the
owner runs (`deploy.deny`). A seat does not ask what it may decide.

Records (owner, 2026-10-03, #357). The records under `.wuwei/` are written by the workflow
from the owner's answers; no step asks the owner to create or edit a file by hand. The owner
answers questions in the session, on the Owner step card of the command that needs the
answer (#831), and may edit any record afterwards; the planner records.
`repos.N.fast_checks = []` means none configured: items build, the PR body says
`checks: none configured`, CI and the gates are the evidence.

Availability (owner, 2026-10-04, #477). The owner's session is never blocked by work.
Seats run in the background; any command that can run longer than a few seconds (fast
checks, `dispatch opinion`, `steward run`, calibration) runs in the background, and the
planner acts on its completion notification. The planner's turn ends with the day in one
line (`wuwei status --line`, which names the running seats by role; `wuwei status` and
`wuwei next` give each seat's item and start time), and the owner can speak at any time; the planner answers from `wuwei next` and `wuwei status --line`, never by
resuming or interrupting a seat. Owner questions are the one thing that waits, because
they wait for the owner.

Process depth (owner, 2026-10-11, #811): the tier alone sets it (#280, #567) and CAP alone sets
the seats (#528); no day value adjusts either.

### 5.3 Rules

- Tracks. SLICE (default): no contract, boundary, schema or infrastructure change and under
  about twenty tasks; spec and implementation in one builder session; one gate set at
  pre-PR. FULL: adds a spec-done gate that blocks only on what changes what gets built.
- Flags set by the lead: `trust_surface`, `boundary_relevant`, `agent_surface`.
- Pre-PR gate set: arch, quality and security in parallel on every code item. After the PR is
  open, fix rounds and deltas are arch-only.
- Assume and record (amended 2026-10-01, #301). "When unsure, it is one-way" (5.8) still
  decides reversibility. An open question on a two-way door inside the item is not asked:
  the seat takes its recommendation, records it under `Assumptions:` in the item's spec or
  PR body (what was assumed, why, what would overturn it) and continues. Gates review
  assumptions as findings. Only a one-way door, a trust-surface area, or a question outside the item (its agreed
  scope, the queue, a person) reaches the owner, as a sentinel's ESCALATE or a builder's
  `Blocked:` line that `wuwei next` asks (5.8).
- Negotiation budget (amended 2026-10-01, #301): one fix round plus one delta check per
  gate. Residual non-blocking findings become review notes in the PR body. A trust-boundary
  security finding always blocks. The verdict lint refuses a finding without a failure
  scenario and a verdict without a probe or mutation row. Exceeding the budget is a design
  reconsideration, never another round: the CLI parks the item with the reason stating why
  the approach keeps leaking; what replaces it is agreed with the owner before more code,
  and the reconsideration is recorded in its spec (constitution, Cycle budget).
  Amended (owner, 2026-10-10, #732; owner, 2026-10-11, #789 part 14): a PARK verdict parks
  the item in code; an ESCALATE verdict asks the owner on the Owner step card of
  `dispatch next`, which `build next` names too; a blocked item with no round left parks
  in code and names `wuwei plan resume`.
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
  | Mutation step (gate step zero) | none | only when the diff touches `guards/`, `outward`, a hook or a `trust_paths` entry, or the item is flagged `trust_surface` or `boundary_relevant` (#663) | always |
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
  with its reason instead of spending more budget, and `wuwei plan resume` asks the owner. Progress, not activity, keeps a
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
  ceiling refusal names `host.seats`. Once the build is done and the item is at its gates, `build next`
  answers what `dispatch next` decides (#666). At raise both return the shepherd's brief
  command, then its launch, in the gate shape (#783).
  answers what `dispatch next` decides (#666).
- Broken main amendment (owner, 2026-10-10, #648). A fast check that fails only on files the
  item did not change is main's, not the item's: the build loop records it under
  `main_broken` with the check and the first failing path, opens one fix item for it through
  `plan add` (one per file per repository), and sets the item's build action to `wait`
  naming that fix item instead of a builder round. A held item takes no seat. Once the fix
  item merges (or is parked), `build next` returns a `continue` that tells the builder to
  rebase and rerun its checks. A test failure is never held.
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

What reaches the owner comes from `wuwei next`, one named decision at a time, on the Owner
step card of the command that needs it (5.8): the morning gate (goals, ranked queue, seat
policy); work outside the goals or above the auto-start bar (5.7); a merge the merge policy
does not clear or one the owner keeps; an ESCALATE verdict; a parked item to resume; a scope
change a reviewer asks on a PR. Never for what a seat's mandate lets it decide (5.2).
Otherwise the session is silent (owner, 2026-10-11, #789).

### 5.5 The steward

Outside the dispatch path. Reads `events.jsonl`, verdicts, traces and CLI metrics: fix rounds
per item, hand-backs per PR, time in phase, verdict-lint rejections, decisions reaching the
user per day, build-loop iterations and stuck parks per item, and cost per item, role and day. Writes
the retro. Charter and note changes it only proposes; `wuwei promote` lands them
(section 6.8). Never briefs a seat, never dispatches, never changes item state. A day on
which the steward did not run is a finding in the next plan.

The steward runs at each sweep and at close. It never gates a dispatch: the round cap (5.3)
is the budget (owner, 2026-10-11, #789).

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
- DORA keys (owner, 2026-10-08, #586): `wuwei dora [--window 28]` prints five rows, each with
  its source or the reason it is unmeasured. Lead time to merge is the median
  `cycle_minutes` of items merged in the window; change failure rate is the escaped share
  of those items (the measure above); deployment frequency and lead time to deploy read the
  code host's deployments, or its published releases when a repository never deployed;
  time to restore stays unmeasured until on-call incidents exist (#415). The report and the
  retro show the table under `## DORA (last 28 days)`, and `wuwei dora` exits 2 when the code host could not run. A key is a reading, never a
  refusal.

The baseline is the owner's hand-run month before WUWEI, recorded once in the workspace at
`memory/notes/baseline.md`, never in this repository. A metric that
cannot be computed reports "unmeasured", never zero.

### 5.7 Goals, discovery and prioritisation (owner, 2026-09-28)

Goals. `memory/goals.md` holds the owner's goals, one block each: id (`G-n`), outcome, measure,
target, date, priority. While it has none, the lead proposes goals in its JSON, the morning
gate shows them and `wuwei plan approve` records the approved blocks (5.2); later, seats and the steward may propose changes (6.8) but `wuwei promote` refuses a goal change that the owner has not approved at the
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

### 5.8 Owner decisions (owner, 2026-10-11, #789 part 14; replaces the decision framework of 2026-09-28)

A seat assumes and records a two-way choice in its spec (5.3); it names a one-way, scope,
goal or trust-boundary question in its result. No seat writes a decision record, routes one
or cites one. What reaches the owner comes from `wuwei next` as one named decision, on the
Owner step card of the command that applies the answer; the CLI applies the safe choice on No:

| Decision | The card | Yes | No |
|---|---|---|---|
| Morning gate | `wuwei plan gate` | `plan approve` | change something |
| Merge policy not cleared, owner_merge | `wuwei merge <pr>` | merges | `plan park` |
| ESCALATE verdict, rounds left | `wuwei dispatch next <item>` | opens the fix round | parks the item |
| Round cap spent, or another park (build limit, scanner chain, owner park) | `wuwei plan resume <item>` | resumes the item | it stays parked |
| Scope change a reviewer asks on a PR | `wuwei pr act <pr>` | opens a fix round for it | the thread waits for the owner |

A PARK verdict parks the item in code with its reason and no card; the report and `why` show
it. The process checks stay in code: the round cap, gates at head, the merge policy. The D-n
records of past days stay readable.

### 5.9 Cockpit, signals and briefings (owner, 2026-09-28) (cockpit, menu bar and briefings retired: owner, 2026-10-11, #789)

The owner should not need to ask for status. State is pushed to two surfaces, and
attention is demanded only for what matters.

Signals. Every event is classified once by `signal.classify` into a delivery tier and
an owner lane. Tiers: `page` (interrupt now, even in quiet hours: the day is blocked, a
security finding fired, a base branch went red after an auto-merge, an owner decision
blocks a running item, the dead-man switch
or the budget cap hit), `warn` (owner, 2026-10-10, #789) (recorded in the day's event log for `why` and the retro,
never a list and never on the status line: an owner decision not yet blocking, a merge the
policy does not clear, work outside the goals, budget
at 80 percent, a person's ask nearing its reply window, a telemetry week ready to send
(5.13)), `silent` (visible, never pushed:
normal progress, auto-merges that went well). Lanes: Work (items by phase),
Decisions (waiting on the owner), People (asks owed by the owner, 15.10). An event the
classifier cannot read is a `warn`, never `silent`.

Amended (owner, 2026-10-10, #789): the `nudge` tier is renamed `warn` and the nudge list is deleted: no `wuwei
nudges` command, no `nudges` count on the status line or in `status --json`, no doctor
`nudges` row, no `[nudges]` config table. Every event is still appended to the day's
`events.jsonl`; `wuwei next` derives the next action, and the counts that read warnings
(trace gaps, untraced subagents, phone answers, changed PRs) keep reading them there.

Surfaces, all reading the same classification:

- Status line. `wuwei status --line` for the Claude Code status line (#521): one line of at
  most 100 columns (`--width <n>`), read left to right by importance. First the one thing to
  do now when there is one (`restart Claude Code: hooks <old> still running`, `no plan yet`,
  `gate waiting`, `decision D-n waiting`), then the day's items counted in words (`5 planned
  · 2 building · 1 in review · 3 shipped`, CAP only on the seats token) and the running
  seats by role with the bound that set CAP (`seats 4/1 by host.seats (lead, arch, +2 more)`,
  cut at whole names; #658), then pages (owner, 2026-10-10, #789)
  and `observe` when `guards.enforce` is false. `wuwei status` prints the same groups one per line
  with the detail: each running seat with role, item and start time, watch, listen,
  sessions, the next person reply due, the next meeting and the plugin and template versions. It shares the hook latency
  budget (10.6) and shows `WUWEI ? unmeasured` rather than a false green when it cannot read state.
- Phone. Pages at once and digests (owner, 2026-10-10, #789) through the control plane (Remote Control push by
  default, messaging adapters in M5 (retired by #789, owner, 2026-10-10)), plus approvals.

Cockpit, menu bar and briefings: retired (owner, 2026-10-11, #789).

### 5.10 Specification mode (owner, 2026-10-03, #411)

Every item that is not trivial is specified with one configured spec engine before it is
built, and the hooks keep the engine's steps in order. `[spec]` in `config.toml`:

- `engine` (default `"speckit"`): `speckit`, `superpowers`, `openspec`, or `none`, which
  checks nothing (the behaviour before this section).
- `mode` (default `"strict"`): `strict` refuses at every enforcement point below;
  `advisory` lets each call through and records the first gap per item and day as one
  `spec.warned` event, which `wuwei next` and the report list; `off` checks nothing. The
  spec checks have no other setting: `mode` is their only one, and with
  `guards.enforce = false` `strict` runs as `advisory`.
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
  and commands, or the skip and its reason; gate briefs name `wuwei why <item> --json`, whose `spec` field gives
  the artifact paths (#667).

`spec.step`, `spec.skipped`, `spec.warned`, `spec.override` and `items.<item>.spec` are
written only by the CLI. The artifacts are written by the seat: they show the work was
done, never that the owner agreed; only `plan set` lowers the requirement for one item.

Engine presence. `wuwei doctor` looks for each engine in each configured
repository: `.specify/` for spec-kit, `openspec/` for OpenSpec, and a `superpowers@` entry
in Claude Code's installed plugins file (`scanner.mcp.plugins_file`) for superpowers.
A configured engine
absent from a repository is a doctor fail carrying its install line; `none` never is.

Seats and owner. The builder, lead and planner charters and the plan skill name the
configured engine's steps and the skip rule; the orientation block (`wuwei next`) shows the
engine and mode; the docs glossary defines spec engine and strict mode, and the
configuration page documents `[spec]`.
### 5.13 Telemetry (owner, 2026-10-03, #421)

Telemetry tells the owner, and the project when the owner agrees, whether WUWEI itself
works: how often its guards refuse or cannot run, how long a hook takes, how often items
loop, how many decisions reach the owner. Two layers (owner, 2026-10-11, #789): the signals the CLI already
records and a weekly aggregate computed off the hook path; sharing is optional and the
owner's choice. Nothing runs in a hook. `[telemetry]` in `config.toml`:

- `enabled` (default true): false stops the aggregate, sharing and the OpenTelemetry
  export (owner, 2026-10-11, #789); the events a day needs are recorded as before.
- `share` (default `""`, not asked yet, which behaves as `"off"`): `"anonymous"`,
  `"attributed"` or `"off"`. Set by the owner with `bin/wuwei config set telemetry.share`
  or by `wuwei telemetry off`.
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
  `Class:` field, from the cards that still write a record (5.8).
- loops: `negotiation.loop`, from days before #789 part 14.
- owner interactions: `decision.decided` with `decided_by` `owner`; DM commands, the
  `remote.*` events written by `wuwei listen` (retired by #789, owner, 2026-10-10); owner host actions, `remote.acknowledged` (retired by #789, owner, 2026-10-10),
  `state.recovered`, `integrity_confirmation`, `mcp.decided`, `draft.sending` and
  `draft.dropped`.
- configuration facts, read from `config.toml` when aggregating: the posture label
  (`guarded` when `guards.enforce` is true, `observe` when false; #837 keeps the field for
  stored weeks),
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
directories and no final file (`final: true`, owner, 2026-10-11, #789). Budget: 10
seconds of wall time per run and 20 MB per `events.jsonl`; past either the run stops, keeps the
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
| `long_loops` | `negotiation.loop` records from days before #789 part 14 |
| `stuck_parks` | `build.parked` records (5.3) |
| `decisions` | decision ids routed or decided in the week |
| `decisions_by_class` | per class, from the record's `Class:`; unreadable counts as `other` |
| `decided_by` | `decision.decided` per `owner` and `seat` |
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

Proposals: deleted (owner, 2026-10-11, #789); nothing is derived from a week.

Sharing. Nothing leaves the machine unless `share` is `"anonymous"` or `"attributed"`, and
then only the payload of a final week, a JSON object with exactly these top-level keys:
`schema`; `week`; `token` (anonymous only); `versions` (`plugin`, `python`, `os`); `config`
(`posture`, `profile`, `adapters`, `repositories`), where `adapters` maps each port name to
its adapter name and `repositories` is a count; and `metrics`, the keys of the table above;
never anything else in the file (owner, 2026-10-11, #789). Anonymisation, checked by
`telemetry.validate` before every send and by the collector on receipt:

- every key comes from this section; every key inside a metric is a guard module name,
  `config`, a phase, a tier, a record class, a posture area, `p50`, `p75`, `p90`, `p95`,
  `max`, `merged`, `escaped`, `owner` or `seat`; every key inside `adapters` is
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
- `attributed`: the sweep records `telemetry.ready` once per final week (a `warn` (owner, 2026-10-10, #789), 5.9).
  The owner runs `bin/wuwei telemetry send`, an owner action on the host refused from agent
  tools like `config set`, which prints the exact issue, asks yes or no (#414) and opens it
  on `repository` with the code host adapter's `issue` (`gh issue create`). The issue comes
  from the owner's GitHub account and shows the owner's login: that is the difference from
  anonymous. Title `telemetry: <week>`; body the payload as a two-column Markdown table,
  without the token, so an attributed week never ties the anonymous ones to a person. The
  canary and honeytoken checks (7.1) apply; the outward-text lint does not, because the
  body is the validated rendering, not authored text.
- `off`: nothing is sent; the aggregate continues while `enabled` (owner, 2026-10-11, #789).

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
`telemetry.off`; turning sharing on is the owner's (`config set`). Every
`telemetry.*` event is written only by the CLI; `telemetry.ready` is a `warn` (owner, 2026-10-10, #789) and the rest
are silent.

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
defaults. `[tracker]` in `config.toml`:

| Key | Default | Meaning |
|---|---|---|
| `required` | `true` | every item needs a ticket; in force only when `adapters.tracker` is not `none` |
| `skip_tiers` | `[]` | tiers (`light`, `standard`, `full`, as in `repos.gates.floor`) whose items need no ticket |
| `strict_close` | `true` | day close refuses a merged item whose ticket did not reach the done state |
| `create` | `["bugs", "triage", "follow-ups"]` | the classes seats may open tickets for |
| `log` | `["decisions", "progress", "verdicts", "pr", "close"]` | the comment kinds written to an item's ticket |
| `auto` | `["progress", "pr", "close"]` | the kind a folded comment is filed under; every kind is sent after the lint (#838) |
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
set <item> ticket=<id>`. The refusal points:

- `plan approve`: one refusal lists every approved item without a ticket; nothing is approved;
- `plan add` (intraday intake, 5.7): the candidate becomes an owner proposal with the reason;
- `build next`, before the claim, and `dispatch next`, before the gates;
- PreToolUse `Agent` launch for a brief whose item has none (4.1), part of the seat launch
  contract and so under the `seats` area (9.1).

The tier that decides is the item's recorded gate tier when there is one, else the lead's
tier; an item with neither is not exempt. An unticketed item whose deciding tier is `light`
and not in `skip_tiers` reads `later` and is not refused (#646, I56): the gate opens its
ticket, or `close` names `bin/wuwei tracker create <item>` after it ships. An exempt item gets one `tracker.skipped` event at
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
idempotent per class, subject and title: a second call prints the existing ticket
and writes nothing. Each ticket that exists records one `tracker.created` event (class,
subject, ticket, parent).

Comments. One CLI writer, `wuwei tracker log`, run by the watch sweep (4.2), by `wuwei close`
once the close passes, and on demand, turns the day's CLI events into comments on each
item's ticket, once each. Every entry has a stable key (its kind and subject), kept in
`tracker_log` in `state.json` with its outcome (written, refused, folded), so a
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
| `close` | `wuwei close`, `plan carry` or `plan park` | `Merged in <pr>.`, `Carried to <date>.` or `Parked: <reason>.` |

Sending. Comments and creations are external writes sent as the owner, so they go through
the tracker port's text-bearing operations, which run the canary check and the outward lint
(4.3, 4.9) and then send (#838). Every tracker write, comments and creations, passes the
humanizer pass of the outward policy (`[outward] humanize`, default true, #420) before it is
sent. A refused write is recorded in `tracker_log` and not retried. When the adapter confirms
a created `items` ticket, the CLI records it in `tickets`.

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

Health. `doctor`
fails the tracker row when `required` is in force and the adapter cannot read the backlog,
naming the missing credentials or `bin/wuwei config set tracker.required false`.
`init --upgrade` from a host terminal creates the lifecycle labels the tracker port needs (today only the GitHub
`in_review` label without a board), `doctor`'s `tracker labels` row lists missing ones, and a
failed in-review move creates the label on the owner's tracker and moves again,
or otherwise names it with `bin/wuwei tracker move <item> in_review` (#670, I49).

Owner-facing. `wuwei next` and the DM show an item's ticket id beside its name.
The documentation adds a `[tracker]` section to configuration.md, glossary entries (ticket,
tracker hygiene, fold), one paragraph in daily.md ("every item has a ticket; you see the
ticket id in `wuwei next` and in the DM") and reference rows for `tracker create`, `tracker
log`, `tracker done` and `plan set`.
### 5.12 Documentation system (owner, 2026-10-03, #418) (retired: owner, 2026-10-11, #789)

Retired with the docs obligation, the page writer, the day page publisher and the docs adapters (#841). What stays: the quality sentinel reviews a change to documented behaviour as code under the `DOC` class, and a docs-only diff gets one reviewer, the goal sentinel.

### 5.14 Memory over time (owner, 2026-10-03, #443)

Records grow every day; what a session loads must not. Budget. `[memory] budget_tokens`
(default 6000) caps the SessionStart payload, built in priority order: the spine, then the
past-day lines of the index, then the promote line. When the whole would exceed the budget,
SessionStart leaves today out and says so in one line. The orientation block and
`Active constraints:` (#358) precede the payload and are not part of it.

No duplicate memory. The harness has its own memory (CLAUDE.md, auto-memory, rules
files). WUWEI's records stay the source and nothing is read back from the harness. `wuwei
memory export --claude`, run by `promote` when a proposal landed, writes the charters' rule
lines as one block between markers it owns into the workspace's `CLAUDE.md` (or
`[memory] export_to`), idempotent.

## 6. Memory

### 6.1 Kinds

| Kind | Home | Loaded | Writer |
|---|---|---|---|
| Working | `days/<date>/state.json`, `events.jsonl` | on demand by the planner | CLI |
| Episodic | `days/<date>/` | by summary line in the index | planner, steward |
| Procedural | charters, `memory/CHANGELOG.md`, `memory/ledger.jsonl`, guards | charter as system prompt; changelog and ledger never | `wuwei promote`, from steward proposals |
| Semantic | `memory/spine.md` | in full | the owner |

### 6.3 Index and payload

`wuwei index` writes `memory/index.md`: one line per past day. Session start loads the spine,
the index and today's state, and prints the payload size.

### 6.5 Routing

A design choice goes to the spec only if someone will later ask why the system is shaped
this way. A world fact goes to the spine, never only to a ticket. A lesson about
how to work goes to a charter through a steward proposal and `wuwei promote`, never to a log.

### 6.6 Consolidation

Daily: the steward folds the retro into charter proposals at close, `wuwei promote` lands
them, and the Stop guard verifies they landed.

### 6.7 Claude's own memory

Holds user preferences and working style only. Workspace facts stay in the workspace, so
nothing mixes across workspaces.

### 6.8 Self-maintaining procedure (owner, 2026-09-28)

Mechanisms adapted from autoharness (tigerless-labs/autoharness, MIT), applied to charters
rather than to Claude skills, so procedure keeps one home.

- Propose, then promote. Seats and the steward never edit a charter override directly;
  they write a proposal to `days/<date>/proposals/` (target, action `add` or `patch`, the
  new text or delta, reason, evidence path).
  `wuwei promote` is the single writer: it lints the proposal and lands it by atomic
  rename, or rejects it with the reason.
- Promote lint: the target is a local charter override in `.wuwei/charters/`, never a
  plugin charter or a user file; a rule body stays under its line cap; the evidence path
  exists; an `add` that duplicates an existing rule is rejected in favour of a `patch` of
  that rule; a lesson that contradicts an existing rule must rewrite that rule in the same
  proposal.
- Ledger. Every landed or rejected proposal appends one line to `memory/ledger.jsonl`:
  target, action, reason, evidence, date. `memory/CHANGELOG.md` stays the human-readable
  record; the ledger traces a rule back to the day that taught it.
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
  registered non-seat sessions are noted once per day, and unknown sessions are noted once
  per day.
- S3. MCP audit and drift: retired (owner, 2026-10-11, #789). WUWEI no longer watches attached
  MCP servers; an `agent_surface` change, MCP config included, is scanned by S4.
- S4. Agent-surface gate. When `agent_surface` is set, the security sentinel runs
  `ziran audit` and `ziran ci --severity-threshold <config>` at pre-PR; each finding becomes a
  verdict row.

With the adapter set to `none` or ZIRAN absent, S2 and S4 report "unmeasured" (exit 2).

### 7.1 Integrity and canaries (owner, 2026-09-28)

Tamper evidence, not tamper-proofing (9.1): a process running as the owner can also edit the
verifier, so these catch accidental changes, other plugins or packages writing into WUWEI,
supply-chain drift between sessions and prompt-injected edits, and surface them loudly.

- Signed manifest. Each release ships `MANIFEST.sha256` (every shipped file: cli, adapters,
  hooks, charters, skills, agents, templates) signed in CI with an SSH signing key
  (`ssh-keygen -Y sign`); the public key is pinned in the plugin and in the workspace at
  `wuwei init`. SessionStart and every sweep re-hash the installed plugin and verify the
  signature (`ssh-keygen -Y verify`). A mismatch is a `page` at session start naming the
  reconfirm or reinstall step; no tool call is refused for it (#839).
- Workspace integrity. `.wuwei/` is a git repository; `wuwei promote` commits every change
  it lands with a `Promoted-by: wuwei` trailer. SessionStart flags any change to charters,
  memory or goals that is uncommitted or committed without that trailer: a `warn` (owner, 2026-10-10, #789),
  a `page` for charter overrides.
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
| tracker | `backlog(filter)`, `claim(item)`, `transition(item, state)`, `create(draft)`, `comment(item, text, category)`, `history(item)`, `created(item)`, `labels(create)` | Linear (recommended), Jira, GitHub issues and Projects (5.11) |
| chat | `post(channel, text, thread)`, `dm(text)` | Slack |
| docs (5.12) (retired by #789, owner, 2026-10-11) | `read(ref)`, `write(draft)` | Notion (recommended), Confluence, repository Markdown |
| review_bot | `score(pr)`, `open_findings(pr)` | Greptile |
| runtime | `dispatch(role, brief_path, worktree, write)`, `status(job)`, `result(job)` (includes usage: tokens, cost, model, duration) | Claude (default), Codex |
| scanner | `audit(path)`, `gate(result, threshold)`, `traces(file)` | ZIRAN |
| code_host | `pr(ref)`, `checks(ref, sha)`, `reviews(ref)`, `threads(ref)`, `protection(repo, branch)`, `create_pr(draft)`, `request_reviewers(ref, logins)`, `comment(ref, text, thread)`, `merge(ref, sha, method)`, `revert_pr(ref)`, `issue(repo, title, body)` (5.13) | GitHub through `gh` (default); GitLab possible later |
| vcs | `identity(repo)`, `head(repo)`, `merge_base(repo, ref)`, `status(repo)`, `diff_stat(repo, base, head)`, `log_since(repo, sha)`, `worktree_add(repo, branch, path, remote, base)` | git |
| inbound (M5) (retired by #789, owner, 2026-10-10) | `poll(since)` or `receive(request)`, `reply(thread, text)` | Slack (poll) |
| control_plane (M5) (retired by #789, owner, 2026-10-10) | `escalate(decision)`, `notify(summary)`, `poll_replies(since)` | Remote Control plus push (default), Signal, WhatsApp |
| redactor (M5) | `redact(text) -> text, findings` | built-in patterns (default); WUMING once it ships a CLI |
| tts | `speak(text, voice, out)` | macOS `say` (default on macOS), none (no caller since #789 part 5) |
| calendar | `events(since, until)` | private ICS feed URL through `urllib`, none |
| transcripts | `recent(since)`, `transcript(meeting)` | none (default); a meeting recorder's API (no caller since #789 part 5) |

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
- the owner's exact `outward.allow` list: an MCP send to other people leaves only through a
  tool the owner added on an Owner step card (4.9);
- the out-of-process control plane (M5) for anything decided remotely (retired by #789, owner, 2026-10-10).

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
  call concerns it, and only relevant calls are parsed; a call a guard cannot read is
  logged, never refused (#839), so a parser limit never blocks work;
- guards that concern roles (brief, retro, verdicts) apply to WUWEI role seats only, not to
  other subagents.

Enforcement (owner, 2026-10-11, #837). One switch, `guards.enforce` (default true), replaces
the postures, areas and floors of #331. With it on, a guard refusal blocks with its reason. With
it off, the hook records it as `guard.would_refuse` (guard, reason, exit, target, session, item)
and lets the call through; a launch refusal is also shown to the session (#660). `init
--shadow` writes `false`; `init --upgrade` maps `security.posture = "observe"` and
`guards.mode = "shadow"` to `false`, keeps an explicit `guards.enforce` and removes the
retired keys.

The floor blocks whatever the switch says (constitution VII):

- records written by the workflow: the state-file guard, the Owner step answer recorder,
  `lifecycle`, the verdict lint, canary and honeytoken egress, owner disposition markers and a
  seat launch naming a brief that does not exist;
- the owner's edges: deploy, merge, admin, approval and branch protection, and an MCP send to
  other people through a tool not on `outward.allow` (#838). A deploy, release or publish runs
  only on the owner's recorded Yes on the Owner step card of that exact command (#816); an
  unlisted send names the `config set outward.allow ... --add` line, whose card adds it. A merge
  happens only through the merge policy; a merge it does not clear for an eligibility rule is
  one owner decision from `wuwei next` (4.6, #816).

No new walls (B5 lead call, #837): with the switch on, what blocked under the old guarded
default still blocks (the floor, the force push and default-branch edges, day close, spec mode),
and so do two process checks: a seat launch that matches no logged brief
at an unchanged head, and a bare `gh pr create` for a recorded item. What only warned stays a
logged `guard.would_refuse`: the outward lint and unknown MCP tool names, another item's scratch
directory and the CAP, host seat, free memory and ticket checks at launch. The unparsed command
and the workspace root `cd` are logged once per call either way. Plugin integrity is a
SessionStart warning and refuses no tool call (#839). The traces recorder never refuses: a slow, unreadable or unwritten record
is a warning and a `traces.slow` or `traces.gap` event.

The switch changes what the cooperative guards refuse, never the hard boundaries above.

Owner answers (owner, 2026-10-11, #831). Nothing runs in a terminal. An owner step (a spec
skip, an owner merge hold release, a config write, an integrity confirmation, a state recovery,
a doctor fix, a telemetry send) refuses until the owner answers Yes
on its Owner step card: the refusal prints the card (header `Owner step`, the exact command and
a digest of what it changes), the planner asks it with AskUserQuestion, the PostToolUse hook
records the owner's reply from a main session as a hashed `gate.asked` topic, and the same
command reads it from today's event log and proceeds. A seat's question never counts, and a
Bash call that runs `wuwei hook` is refused, so a session cannot feed the hook an answer. The
card counts whatever `guards.enforce` says. The boundary is the one the terminal prompt had: friction
against the planner and seats, not proof against a process running as the owner's user.

### 9.2 Process edges (owner, 2026-10-11, #789)

An edge is an action WUWEI cannot take back: it changes what others see or leaves the
workspace. The hooks refuse each edge outside its one path. Every other process rule lives in
code (`next`, dispatch, the verdict lint, the merge policy) and is tested where it lives.

| Edge | Rule | Guard | Test |
| --- | --- | --- | --- |
| Host merge | A PR merges only through `bin/wuwei merge` under the merge policy (4.6): at the head the gates checked, with green required checks, never with `owner_merge` set; a session `gh pr merge` or a merge API call is refused naming it; a push to a default branch is refused naming `bin/wuwei pr raise --item` | `guards/edges.py` (`check_bash`), `merge.check` | `tests/test_edges.py`, `tests/test_merge.py` |
| Approve | WUWEI never approves a PR: `gh pr review --approve` and an APPROVE review event are refused, and the code host port has no approval call | `guards/edges.py` (`check_bash`) | `tests/test_edges.py`, `tests/test_code_host.py` |
| Admin | `--admin` and branch protection or ruleset writes are refused | `guards/edges.py` (`check_bash`) | `tests/test_edges.py` |
| Force push | `git push --force` in every form (`-f`, `--force-with-lease`, `--mirror`, a `+refspec`) is refused | `guards/edges.py` (`check_bash`) | `tests/test_edges.py` |
| Deploy | WUWEI never deploys (4.7) | `guards/edges.py` (`check_deploy`) | `tests/test_edges.py` |
| Outward send | An MCP send to other people only through a tool on `outward.allow`; the owner's own surfaces are local (4.9) | `guards/edges.py` (`check_send`) | `tests/test_edges.py`, `tests/test_outward.py` |
| PR raise | An item's PR is raised with `wuwei pr raise --item`, which links it and refuses unless every gate passed at the head; a `gh pr create` for a recorded item is refused naming it while `guards.enforce` is on (#837) | `guards/edges.py` (`check_bash`), `shepherd.raise_pr` | `tests/test_edges.py`, `tests/test_shepherd.py` |

`tests/test_invariants.py` keeps one check across all guards: no guard reason is a wall,
with `guards.enforce` on or off (#530, #837).

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
   (S2 and S4, then S1 once the ZIRAN release with plugin agent support exists).

Upstream prerequisite, in parallel with module 1: the ZIRAN change for S1, planned and
shipped in the ZIRAN repository under its own spec.

v1 ships when all three pass the end-to-end scripted day and the owner has run one real day
on it. The repository stays PRIVATE until the owner judges it stable enough to publish.

## 14. Resolved questions (owner, 2026-09-24)

- Q1. ZIRAN support for Claude Code plugin agent files ships in ZIRAN first; WUWEI pins that
  release (section 7, S1).
- Q2. ZIRAN has no MCP server; the CLI is the integration surface.
- Q3. Private until stable enough to become public (section 13).

## 15. Post-v1 (M5): always-on responder and inbound messaging (retired by #789, owner, 2026-10-10)

Retired: the listener, the inbox, the inbound port and the control plane were removed by #789; the text below is history.

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
- Reply obligations: each needs-you ask is owed until answered. It starts as a `warn` (owner, 2026-10-10, #789) and
  becomes a `page` as its reply window closes. The Stop guard refuses day close while a reply
  is owed to a person.
