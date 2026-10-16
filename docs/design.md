# WUWEI 1.0: design

- Status: PROPOSED for the owner's approval (#1020)
- Date: 2026-10-15
- Supersedes: the 0.x design (`docs/specs/2026-09-24-wuwei-design.md` at tag v0.34.0)

无为 (wuwei) means effortless action. WUWEI 1.0 gives agent teams responsible autonomy: a Claude Code
plugin that audits the work by its evidence, teaches the way at the moment it matters, and holds
the few doors that do not reopen. It does not prescribe steps, wrap git or gh, or stop the work to
prevent bad behaviour: the work goes on, and nothing it does goes unrecorded. The concepts, each
with its reason, are explained in `docs/site/concepts/`.

## 1. Why 1.0

0.x prescribed every step and tracked the journey as state rebuilt from a session it did not
control. Each path the model took that the protocol did not model broke that state, and each fix
modelled one more path (186 fixes, 33k lines in 20 days). 1.0 reads outcomes: it does not care how
the work was done, only whether its evidence exists.

## 2. Principles

1. Outcomes, not steps: the process says what evidence must exist when an item is done.
2. The artifacts are the truth: git, the code host, spec and verdict files. The ledger holds only
   what they cannot: plan changes, attestations, rulings, exceptions, refusals, andon, checkpoints.
3. An auditor with narrow police powers: a closed list of doors; everything else passes and is
   recorded.
4. The owner decides only what matters: hard to undo and unsure, scope and goals, trust, owner
   reviews, exceptions. A process step never reaches the owner.
5. No wrappers: the model uses git, gh and the repository's tools; WUWEI reads and records.
6. The harness owns permissions; WUWEI adds deny and ask rules and checks what a static rule
   cannot: content, evidence and completion.
7. Be water: read each repository's own process and fill only the gaps.
8. Configuration holds facts, not behaviour: five keys.

## 3. The team

Planner (the owner's session), lead, builder, four sentinels (arch, quality, security, goal),
shepherd, steward. `charters/` is the one source; `wuwei agents build` generates the agents with
their reviewed tool grants. The quality sentinel runs on a different model than the session's
(`MODELS` in `cli/wuwei/agents.py`). Seats cannot ask the owner. The planner passes each seat its
role's lines of `.wuwei/standards.md`.

## 4. The day

- Goals in `.wuwei/goals.md` set the direction. Each plan pass ends with the plan as a view
  (`wuwei plan view`, #990) and one `plan:` question, Approve or Change; new items wait for it.
- A plan pass (`/wuwei-run`, `wuwei plan pass`) adds, drops or re-ranks items in a running queue.
  Any number per day. The lead returns only ready candidates (promise, acceptance scenarios,
  repository, files) and red-teams the plan (the riskiest item and the cheapest early test of it).
- Ranking: WSJF (default) or RICE, each score with evidence.
- A close (`/wuwei-close`, `wuwei close`) is a checkpoint: the report and the retro for the day so
  far. A later pass reopens the day; a second checkpoint reports what changed since the first.

## 5. Decisions

| | Sure | Unsure |
|---|---|---|
| Undone cheaply | act | act, record the assumption |
| Hard to undo | act, with `Rollback:` | ask the owner |

Owner questions start with their class: `one-way:`, `scope:`, `goal:`, `trust:`, `infra:`,
`owner review: owner/repo#n at <sha7>`, `exception: owner/repo#n at <sha7>: <gap>`, `plan:`,
`breaking: owner/repo#n at <sha7>: <what breaks>. Announced at <link>. Proceed?`. Any other
question is refused back to the model. A `one-way:` answer becomes an ADR in the repository. An
accepted exception drops that gap at that head and adds a follow-up item that closes it.

## 6. The evidence contract

| Evidence | Applies |
|---|---|
| The WUWEI footer (or a `WUWEI-Item: <id>` line) names a plan item | every PR |
| The repository's PR template sections | when it has a template |
| A test in the diff, or `No test: <reason>` (docs-only exempt) | every PR |
| At most 400 changed lines (generated files aside), or `Size: <reason>` | every PR |
| `Rollback: <how>` | full tier, or `owner_paths` touched |
| The spec engine's steps by their artifacts at the head (spec-kit: spec, plan, tasks all checked; full adds clarifications, a clean analysis, checked checklists; OpenSpec: proposal, a capability spec, tasks all checked) | standard and full, when the repo has `.specify/` or `openspec/` |
| The gates the diff needs passed on the branch before its PR opened, each at an ancestor of the head; a later delta re-read by the one gate it needs, unless it is docs or at most 20 lines off risky paths | the tier is the ceiling: docs none; code quality; standard adds security for risky or owner paths and arch for a wide change; a contract file takes arch at any tier; full takes all four |
| CI green, threads answered, a reviewer requested | every PR |
| Owner review or an owner ruling at that head | `owner_paths` touched |
| Open under three days | every PR |

Safety and process: only safety gaps (a test, gates at the head, CI, threads, owner review,
readable evidence, breaking changes, the spec engine's steps at full) hold a merge or show on the
board. Process fit (plan link, PR template, size,
`Rollback:`, the spec engine's steps below full, a reviewer, staleness) never blocks and is shown to nobody
while the work flows; the merge records it, the report lists it, the steward learns from it. Only a
safety gap can be an owner `exception:`.

Release PRs: a PR opened by `github-actions[bot]` or `release-please[bot]` on a `release-please--` branch
is read as generated, like docs: it needs no test and no gate. Every changed file must be `CHANGELOG.md`,
`.release-please-manifest.json` or an `extra-files` path from `release-please-config.json` on the base
branch, and every added or removed line in the manifest and extra-files patches must be a version line.
A missing patch, a rename or an unreadable config keeps every gap. CI, threads and owner review still apply.

Review statuses: a commit status whose `target_url` names a run of a workflow the repository runs on
`pull_request_review` is review evidence, not CI. Pending reads `waiting on review: <context>`, failure
reads `change request outstanding: <context>`; both are actionable safety gaps. The review-triggered
workflows come from the host (its last 100 `pull_request_review` runs, cached for a day), read only
when the head has an unsettled status. An unreadable Actions host leaves the status CI, never a pass.

Breaking changes: a break of an outward contract (declared with `!` or `BREAKING CHANGE:`, or found
by the arch gate's required `Breaking:` line; a contract file takes the arch gate at any tier)
needs an `Announcement: <link>` line and then the owner's `breaking:` confirmation at the
head. Both are safety gaps.

Error budget: when a repository's 28-day change failure rate (reverts over merges, at least five
merges) is over 15 percent, every tier there rises one step and takes its full gate set, untrimmed by
the diff. Verdicts count only when attested at
the sentinel's stop (shape linted, hash, gate, item, head, confidence, agent recorded). Gaps are
actionable, waiting or the owner's; an unreadable code host is a waiting gap, never a pass. A PR read
after it merged lists what it lacked as `post-merge:` gaps, and the report counts a finding attested
after the merge as an escape.

Operations items: an item done by a run, not a change (a backfill, a re-drive, an operator step),
records its run evidence (`wuwei plan run <id> --reason`); the board shows that evidence, not a
missing PR, and `wuwei plan done` closes it with the final evidence.

## 7. The doors

Refused: a merge with safety gaps by any route (`gh pr merge`, a REST PUT on `pulls/<n>/merge` or
`ccr/auto_merge` in any spelling of method, path, host or `{owner}/{repo}`, a GitHub MCP merge
tool; arming auto-merge passes while only CI runs); a PR opened (`gh pr create`, `gh pr new`, a
REST POST on `repos/<r>/pulls`, a GitHub MCP create tool) before the gates its diff needs pass at
the branch head, so review starts at a gated head (#1050);
`--admin`; `gh api` writes to protection, rulesets, statuses,
collaborators, hooks, keys, secrets and environments; `gh api` writes to `merges`, `git/refs/` or
`contents/` on any branch; `gh repo delete` and a REST DELETE on the repository; a `gh api graphql`
mutation that merges, arms auto-merge, opens a PR, moves a ref, commits to a branch or changes
branch protection or rulesets (among them `mergeBranch` and `enqueuePullRequest`); force pushes in
every form; pushes to or deletion of the default branch, including the GitHub MCP `push_files`,
`create_or_update_file` and `delete_file` tools on the default branch or with no branch; a secret
or the canary in an MCP call or network command; writes to the ledger; a hand-made `wuwei hook`
call; an owner question without a class.
A multi-line or unreadable Bash command whose raw text names a door program (git and push; gh with
pr, api or repo; wuwei followed by hook; `.wuwei/ledger`), with a hint to run the door command in its own
one-line call (#1068); other multi-line commands are read line by line. The doors read a command
inside a loop, an if or a brace group, a shell's `-c` body after combined flags (`bash -lc`), and,
after a wrapper (env, timeout, nice, sudo, xargs), the first program a door reads.
Asked through the harness: terraform, tofu, pulumi, kubectl and helm writes.

A door that cannot read its evidence stays shut: an error while PreToolUse judges a door call (an edit
tool in `guards.DOORS` or a Codex apply_patch, any MCP tool, or a Bash command that names a door program
or a network program in `guards.NETWORK`, read with its quotes and backslashes removed) refuses
it, names the error and records `hook.error`. Every other hook fails open and records `hook.error`. `wuwei doctor` reports each door's strength per repository: wall (code host or
credentials), refused (hook), detected (audit).

Andon: `wuwei andon owner/repo --reason` holds new builds in one repository until cleared; others
flow.

## 8. Hooks

| Hook | Role |
|---|---|
| SessionStart | the way of working, `_common.md`, the planner charter, goals, standards, the board |
| PreToolUse | the doors; the PR standard with a ready body once per session; a gate's verdict lint and attestation at its hand-back |
| PostToolUse | traces; what a new PR lacks; prompts, rulings, exceptions, ADR notes |
| SubagentStop | seat stops with tokens and confidence; verdict lint and attestation, or `verdict.missing` when a block can no longer reach the seat |
| Stop | a reminder only when actionable work is new since the last one, naming only what changed; once, to arm the watch when only waiting work is left and no watch pass ran in the last hour, or to plan from the goals when the queue is empty; never a loop |

## 9. Learning

At each checkpoint the steward writes the retro with at most three proposals: defect vaccines (a
regression test item and a gate standard per escaped defect), calibration and gate yield findings,
skills and memory lines for a repository (landed through a PR there), and rules to retire (a rule
that caught nothing in 30 days; a new rule is a note for its first five days). A kind of owner
question always answered with the recommendation becomes a rule.

## 10. Records, report, DORA

`.wuwei/`: `config.toml`, `plan.json`, `goals.md`, `standards.md`, `verdicts/`, `ledger/<clone>.jsonl`
(hash-chained, versioned rows, one file per clone, `wuwei verify`), `traces.jsonl`, `days/<date>/report.md`,
`retro/<date>.md`, `canary`, `cache/`. The state travels on the `wuwei/state` branch (`wuwei
sync`; pulled at a cloud session's start, pushed at its stops); `wuwei init --cloud` copies the
plugin into a repository's `.claude/` for cloud sessions, where repository plugins do not load.

The report: plan passes and checkpoints with the diff since the last, the board, merges through the
check or as exceptions, the doors, owner prompts, seats and verdicts, learning (escapes traced to
gates with confidence, change failure rate and raised tiers, unplanned PRs, gate yield, tokens by
role, open exceptions, the weekly sample), telemetry, ledger integrity. DORA comes from the code
host alone. Replay cases (`wuwei evidence --record`) hold every future version to past answers.

## 11. Configuration and budgets

Five keys: `repos`, `owner_paths`, `prioritisation`, `tracker`, `telemetry`. Runtime at most 3,000
lines of stdlib Python (a test holds it). A change that breaks a budget deletes something first.

Codex: the same plugin loads in Codex (it reads `.claude-plugin/`, `skills/` and
`hooks/hooks.json`, with the same hook events and outputs). The hook entry maps Codex's tool shapes
(`apply_patch`, `spawn_agent`, `request_user_input`) onto the ones the guards read; `wuwei init
--codex` writes the role agents to `.codex/agents/` and the doors to `.codex/rules/wuwei.rules`.

## 12. Deferred

- Walls: an agent identity on the code host, rulesets, CODEOWNERS, a required `wuwei/evidence`
  status posted by CI (#918).
- Attestations cross-checked against the harness transcript (#962).
- A shared standards repository for teams; auditing human PRs as first-class items.

## 13. From 0.x

`wuwei init` upgrades a 0.34 workspace in place: it reads the old config shape and rewrites it
(keeping `.wuwei/config.0x.toml`), names each retired key, carries the goals forward, imports the
open items with their PR links and the latest proposal, and imports the gate verdicts as
attestations so in-flight PRs need one delta gate, not a full set. DORA reads the code host, so
no history is lost. The 0.x line stays on its tag (v0.34.0).
