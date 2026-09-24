# WUWEI 无为: design

- Status: PROPOSED, for owner review
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
  several repositories, and is asked only for decisions, new work, and merges.
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

- Merging or approving pull requests. Always a human act; no profile allows it.
- A hosted service, database or long-running server.
- Multi-user team coordination (v1 is one person's workspace).
- Replacing the tracker, chat tool or CI. Adapters talk to them; WUWEI does not own them.
- Runtime guardrails for production agents (use a guardrail product) or LLM evaluation.

## 2. Context and constraints

- Runs inside Claude Code. Roles ship as plugin agent types; hooks fire on their tool calls.
- A second runtime (Codex) is supported through an adapter that dispatches the same charter
  by file path. Codex sandboxes have no network and cannot reach an MCP server, so every
  guard and state change is a CLI, not an MCP tool.
- Stdlib Python only at runtime. No package install beyond the plugin itself.
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
| CLI | The only writer of workspace state and the only home of guards, sweeps, index and metrics. | stdlib, adapters |
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
    index.md           generated; one line per note and per past day
    notes/*.md         settled facts with frontmatter
    CHANGELOG.md       every dated rule change, verbatim; never loaded by seats
  days/YYYY-MM-DD/
    plan.md  state.json  events.jsonl  traces.jsonl
    briefs/  decisions/  deliverables/  retro/  report.md
  archive/             days older than 30, summary lines kept in the index
```

### 3.4 Three-state exits

Every guard, sweep and adapter call returns one of: `0` clean, `1` findings, `2` could not
run. Exit 2 blocks exactly like exit 1 and prints why. An absent adapter or scanner reports
"unmeasured", which the report shows as such and never counts as clean.

## 4. Guards

### 4.1 Hook table

| Event | Trigger | Refuses when |
|---|---|---|
| PreToolUse | `Agent` launch | no brief logged for it; a gate seat while its item's builder is live or its tree is dirty; running seats at CAP or free memory below the configured floor |
| PreToolUse | `git commit`, `git push` | author or committer differs from repository config; force-push; push to the default branch; push before the fast checks passed |
| PreToolUse | `gh pr create` | the pre-PR gate set has not all passed; no reviewer named in the same action |
| PreToolUse | `gh pr merge`, `gh pr review --approve` | always |
| PreToolUse | chat or tracker adapter call | outward-text lint fails; a technical claim, disagreement or scope statement without an approved draft |
| PreToolUse | Write or Edit on `state.json`, `events.jsonl` | always; state changes go through the CLI |
| PreToolUse | top-level `cd` out of the workspace | always; use `git -C` or a subshell |
| PostToolUse | any tool | never refuses; appends the call to `traces.jsonl` in OTel JSONL shape |
| PostToolUse | write to `decisions/gate-*.md` | verdict lint fails; the verdict is returned to the seat |
| SubagentStop | a seat finishes | its three-line retro note is missing; otherwise records it |
| SessionStart | new session | never refuses; prints the memory payload and its size, flags a dead watch process and orphans from the last close |
| PreCompact | before summarising | never refuses; flushes pending state and events |
| Stop | day close | reply obligations owed, visibility obligations owed, or the retro did not land |

### 4.2 Sweeps

Run by the watch process every two hours, written to `events.jsonl` as `watch: sweep`:
reply obligations (every open PR, three comment surfaces, fail-closed acknowledgement
ledger), PR visibility (reviewer requested, channel post logged with reviewer mentions,
verdict recorded), staleness (no commit and no report for 15 minutes), and the scanner over
the day's traces. The watch writes a clock line every 10 minutes; a missing clock line is a
failure signal.

### 4.3 Outward-text lint

Configured in `config.toml`: the owner's name and pronouns (never used in third person in
text sent as the owner), patterns that reveal the routine's internal state (drafts pending,
queues, which agent wrote what), banned characters, and a maximum length per channel.

### 4.4 Profiles

- `strict` (default): every guard above blocks.
- `standard`: the outward-text lint warns instead of blocking. Merge and approve are still
  refused.

## 5. The team

### 5.1 Roles

| Role | Seat | Writes |
|---|---|---|
| planner | the user's session | plan, dispatch, receive, sweep, report; state through the CLI |
| lead | per day | ranked discovery with evidence, scope, overlap matrix, track and flags |
| builder | per item | spec and implementation in the item's worktree |
| sentinel-arch | per gate | one verdict file |
| sentinel-quality | per gate | one verdict file |
| sentinel-security | per gate | one verdict file; runs the scanner when `agent_surface` is set |
| sentinel-goal | per docs gate | one verdict file |
| shepherd | per PR set | PR raise, reviewer requests, thread replies, obligation ledger |
| steward | at each sweep and at close, fresh seat | steering notes, the decision queue, the retro and charter commits |

### 5.2 Flow

```
/wuwei plan -> planner -> lead -> MORNING GATE (user approves or edits)
  -> per item: builder -> pre-PR gates in parallel (arch, quality, security; goal on docs)
  -> shepherd raises, requests reviewers, posts
  -> fix round -> arch delta -> ... -> user merges
/wuwei report -> steward retro -> planner report -> Stop guard
```

### 5.3 Rules

- Tracks. SLICE (default): no contract, boundary, schema or infrastructure change and under
  about twenty tasks; spec and implementation in one builder session; one gate set at
  pre-PR. FULL: adds a spec-done gate that blocks only on what changes what gets built.
- Flags set by the lead: `trust_surface`, `boundary_relevant`, `agent_surface`.
- Pre-PR gate set: arch, quality and security in parallel on every code item. After the PR is
  open, fix rounds and deltas are arch-only.
- Cycle budget: one fix round plus one delta check per gate. Residual non-blocking findings
  become review notes in the PR body. A trust-boundary security finding always blocks.
- A re-gate continues the same sentinel with the delta; a fresh seat only for a lost agent.
- CAP counts running build seats. Host floors (free memory, seat count) come from config.
- Seat policy (model and runtime per role) is set at the morning gate and stored in state.
- Boundary and environment register come from config; the arch sentinel checks against them.
- Verdict shape: a `Verdict: PASS|FIX|PARK|ESCALATE` line; findings with severity,
  `file:line`, failure scenario and `blocks: yes|no`; a probe or mutation line per claim (or
  "not run"); residual risk; the retro note.
- Retro note, every seat: three lines prefixed `Blocked:`, `Gap:`, `Change:`.

### 5.4 When the user is asked

At the morning gate; for any blocker or decision (one question per decision, recommended
option first, pending decisions batched, pre-triaged by the steward); for new work items;
for merges. Otherwise the session is silent, with a digest at most every two hours.

### 5.5 The steward

Outside the dispatch path. Reads `events.jsonl`, verdicts, traces and CLI metrics: fix rounds
per item, hand-backs per PR, time in phase, verdict-lint rejections, decisions reaching the
user per day. Writes steering notes the planner must acknowledge, the pre-triaged decision
queue, and the retro with its charter commits. Never briefs a seat, never dispatches, never
changes item state. A day on which the steward did not run is a finding in the next plan.

## 6. Memory

### 6.1 Kinds

| Kind | Home | Loaded | Writer |
|---|---|---|---|
| Working | `days/<date>/state.json`, `events.jsonl` | on demand by the planner | CLI |
| Episodic | `days/<date>/` | by summary line in the index | planner, steward |
| Procedural | charters, `memory/CHANGELOG.md`, guards | charter as system prompt; changelog never | steward, via commits |
| Semantic | `memory/spine.md`, `memory/notes/` | spine in full, notes by index | any seat, via `wuwei note` |

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

### 6.5 Routing

A decision goes to a decision note only if someone will later ask why the system is shaped
this way. A world fact goes to the spine or a note, never only to a ticket. A lesson about
how to work goes to a charter through the steward, never to a log.

### 6.6 Consolidation

Daily: the steward folds the retro into charters at close, and the Stop guard verifies it
landed. Weekly: `/wuwei consolidate` as a scheduled task finds contradictions and stale
summaries across notes and archives days older than 30.

### 6.7 Claude's own memory

Holds user preferences and working style only. Workspace facts stay in the workspace, so
nothing mixes across workspaces.

## 7. Security integration (ZIRAN)

All through the ZIRAN CLI via the `scanner` adapter.

- S1. Role audit. ZIRAN's tool-chain analysis over the role and tool matrix proposes each
  agent's allowlist. The repository's CI runs the ZIRAN GitHub Action over `agents/` and
  fails when an agent's tools widen past its allowlist. Requires a ZIRAN adapter that reads
  Claude Code plugin agent files (a contribution to ZIRAN, tracked separately).
- S2. Runtime traces. Each sweep runs `ziran analyze-traces --source otel` over the day's
  `traces.jsonl`. A dangerous sequence observed in a live session parks the affected item
  and prompts the user.
- S3. MCP audit. `/wuwei init` and each morning plan run ZIRAN's MCP metadata analysis over
  the MCP servers attached to the session.
- S4. Agent-surface gate. When `agent_surface` is set, the security sentinel runs
  `ziran audit` and `ziran ci --severity-threshold <config>` at pre-PR; each finding becomes a
  verdict row.

With the adapter set to `none` or ZIRAN absent, S2 to S4 report "unmeasured" (exit 2).

## 8. Adapters

Each adapter is a module implementing a fixed interface. The `none` implementation records
that it did nothing and returns exit 2 where a measurement was expected.

| Adapter | Interface | Reference implementation |
|---|---|---|
| tracker | `claim(item)`, `transition(item, state)`, `create(draft)`, `history(item)` | Linear |
| chat | `post(channel, text, thread)`, `dm(text)` | Slack |
| review_bot | `score(pr)`, `open_findings(pr)` | Greptile |
| runtime | `dispatch(role, brief_path, worktree, write)`, `status(job)`, `result(job)` | Claude (default), Codex |
| scanner | `audit(path)`, `gate(result, threshold)`, `traces(file)`, `mcp(servers)` | ZIRAN |

## 9. Error handling

- Every guard fails closed: an error inside a guard is exit 2, which blocks.
- A read that returns an error body is never parsed as data (the GitHub API returns error
  JSON on stdout).
- State writes are atomic (write to a temp file, then rename). `events.jsonl` is
  append-only.
- A lost seat is relaunched from its persisted brief; recovery reads `git log` since the
  item's recorded head and never redoes committed work.
- A dead watch process is detected by its missing clock line, not by its pid file.

## 10. Testing

- Guards: table tests for exits 0, 1 and 2, plus a mutation test per guard that disables it
  and asserts a test goes red.
- Hooks: recorded Claude Code hook payloads piped through each shim; assert allow or block
  and the message.
- Agents: a golden test regenerates `agents/` from `charters/` and fails on drift; the ZIRAN
  action fails on allowlist widening.
- End to end: a fixture workspace and a demo repository with record-and-replay adapters run
  a scripted day (plan, gate, one item through build, gates, raise, one fix round, close),
  asserting on events and exit codes, never on model prose.
- Triggering: `claude plugin eval` over skill descriptions, including near-miss negatives.
- Test runner: pytest as a development dependency only.

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
   (S1 to S4).

v1 ships when all three pass the end-to-end scripted day and the owner has run one real day
on it.

## 14. Open questions

- Q1. ZIRAN reading Claude Code plugin agent files (S1) is a ZIRAN change. Ship it in ZIRAN
  first, or ship S1 behind a WUWEI-side converter until ZIRAN supports it?
- Q2. Does ZIRAN expose, or plan to expose, its own MCP server? The design does not depend on
  it; if it exists, the security sentinel could use it for interactive investigation only.
- Q3. Public from day one, or private until the first real day has run on it?
