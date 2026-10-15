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

- Goals in `.wuwei/goals.md` are the standing mandate.
- A plan pass (`/wuwei-plan`, `wuwei plan pass`) adds, drops or re-ranks items in a running queue.
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
`owner review: owner/repo#n at <sha7>`, `exception: owner/repo#n at <sha7>: <gap>`. Any other
question is refused back to the model. A `one-way:` answer becomes an ADR in the repository. An
accepted exception drops that gap at that head and adds a follow-up item that closes it.

## 6. The evidence contract

| Evidence | Applies |
|---|---|
| `WUWEI-Item: <id>` names a plan item | every PR |
| The repository's PR template sections | when it has a template |
| A test in the diff, or `No test: <reason>` (docs-only exempt) | every PR |
| At most 400 changed lines (generated files aside), or `Size: <reason>` | every PR |
| `Rollback: <how>` | full tier, or `owner_paths` touched |
| Spec engine artifacts in the diff | standard and full, when the repo has `.specify/` or `openspec/` |
| Gates passed at an ancestor of the head, one at the head | light quality; standard arch, quality, security; full + goal |
| CI green, threads answered, a reviewer requested | every PR |
| Owner review or an owner ruling at that head | `owner_paths` touched |
| Open under three days | every PR |

Error budget: when a repository's 28-day change failure rate (reverts over merges, at least five
merges) is over 15 percent, every tier there rises one step. Verdicts count only when attested at
the sentinel's stop (shape linted, hash, gate, item, head, confidence, agent recorded). Gaps are
actionable, waiting or the owner's; an unreadable code host is a waiting gap, never a pass.

## 7. The doors

Refused: a merge with gaps; `--admin`; `gh api` writes to protection, rulesets, statuses, merges,
collaborators, hooks, keys, secrets and environments; `gh repo delete`; force pushes in every form;
pushes to or deletion of the default branch; a secret or the canary in an MCP call or network
command; writes to the ledger; a hand-made `wuwei hook` call; an owner question without a class.
Asked through the harness: terraform, tofu, pulumi, kubectl and helm writes.

A door that cannot read its evidence stays shut; every other hook fails open and records
`hook.error`. `wuwei doctor` reports each door's strength per repository: wall (code host or
credentials), refused (hook), detected (audit).

Andon: `wuwei andon owner/repo --reason` holds new builds in one repository until cleared; others
flow.

## 8. Hooks

| Hook | Role |
|---|---|
| SessionStart | the way of working, `_common.md`, the planner charter, goals, standards, the board |
| PreToolUse | the doors; the PR standard with a ready body once per session |
| PostToolUse | traces; what a new PR lacks; prompts, rulings, exceptions, ADR notes |
| SubagentStop | seat stops with tokens and confidence; verdict lint and attestation |
| Stop | one reminder per distinct set of actionable gaps; never a loop |

## 9. Learning

At each checkpoint the steward writes the retro with at most three proposals: defect vaccines (a
regression test item and a gate standard per escaped defect), calibration and gate yield findings,
skills and memory lines for a repository (landed through a PR there), and rules to retire (a rule
that caught nothing in 30 days; a new rule is a note for its first five days). A kind of owner
question always answered with the recommendation becomes a rule.

## 10. Records, report, DORA

`.wuwei/`: `config.toml`, `plan.json`, `goals.md`, `standards.md`, `verdicts/`, `ledger.jsonl`
(hash-chained, versioned rows, `wuwei verify`), `traces.jsonl`, `days/<date>/report.md`,
`retro/<date>.md`, `canary`, `cache/`.

The report: plan passes and checkpoints with the diff since the last, the board, merges through the
check or as exceptions, the doors, owner prompts, seats and verdicts, learning (escapes traced to
gates with confidence, change failure rate and raised tiers, unplanned PRs, gate yield, tokens by
role, open exceptions, the weekly sample), telemetry, ledger integrity. DORA comes from the code
host alone. Replay cases (`wuwei evidence --record`) hold every future version to past answers.

## 11. Configuration and budgets

Five keys: `repos`, `owner_paths`, `prioritisation`, `tracker`, `telemetry`. Runtime at most 2,500
lines of stdlib Python (a test holds it). A change that breaks a budget deletes something first.

## 12. Deferred

- Walls: an agent identity on the code host, rulesets, CODEOWNERS, a required `wuwei/evidence`
  status posted by CI (#918).
- Attestations cross-checked against the harness transcript (#962).
- Spec engine step and content checks beyond artifacts in the diff.
- A shared standards repository for teams; auditing human PRs as first-class items.
- The Codex runtime.

## 13. From 0.x

0.x workspaces are not migrated: `wuwei init` writes a fresh 1.0 workspace, and DORA reads the code
host, so no history is lost. The 0.x line stays on its tag (v0.34.0).
