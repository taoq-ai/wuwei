# WUWEI 1.0: design

- Status: PROPOSED for the owner's approval (#1020)
- Date: 2026-10-15
- Supersedes: `docs/specs/2026-09-24-wuwei-design.md` (0.x)

无为 (wuwei) means effortless action. WUWEI 1.0 is a Claude Code plugin that audits the work of an
agent team. It teaches the way at the moment it matters, reads the evidence the work leaves
behind, and holds the few doors that do not reopen. It does not prescribe steps, wrap git or gh,
or stop the work to prevent bad behaviour: the work goes on, and nothing it does goes unrecorded.

## 1. Why 1.0

0.x prescribed every step (`wuwei next` returned the commands) and tracked the journey as state
rebuilt from a session it did not control. Each path the model took that the protocol did not
model (a resumed seat, a shell write, a raw `gh` call, a merge in the UI) broke that state, and
each fix modelled one more path. 1.0 reads outcomes instead: it does not care how the work was
done, only whether its evidence exists.

## 2. Principles

1. Outcomes, not steps. The process says what evidence must exist when an item is done.
2. The artifacts are the truth: git, the code host, spec files and verdict files. The ledger holds
   only what they cannot: plan changes, attestations, owner rulings, refusals and checkpoints.
3. An auditor with narrow police powers. A short, closed list of doors is held; everything else
   passes and is recorded.
4. The owner decides only what matters: one-way doors, scope and goal changes, trust boundaries,
   owner reviews. A process step never reaches the owner.
5. No wrappers. The model uses git, gh and the repository's tools directly. WUWEI's CLI reads and
   records.
6. The harness owns permissions. Who may call which tool is Claude Code's permission rules; WUWEI
   adds its deny and ask rules at init and checks only what a static rule cannot: content, evidence
   and completion.
7. Configuration holds facts, not behaviour: five keys.

## 3. The team

The roles and charters stay: planner (the owner's session), lead, builder, four sentinels (arch,
quality, security, goal), shepherd and steward. `charters/` is the one source; `wuwei agents build`
generates the role agents with their reviewed tool grants (`agents/allowlist.json`). Seats have no
AskUserQuestion: only the planner reaches the owner.

## 4. The day

- A plan pass (`/wuwei-plan`) adds, drops or re-ranks items in `.wuwei/plan.json`, a running queue
  that carries across days. A day has as many passes as it needs: morning, queue dry, the owner
  adds or extends, something changes.
- A close (`/wuwei-close`) is a checkpoint: `wuwei close` writes the report for the day so far and
  the steward writes the retro. Nothing is locked; the next pass reopens the day. There is no end
  time.
- Goals (`.wuwei/goals.md`) are the standing mandate. A plan inside the goals starts without a
  question.
- Ranking: WSJF (default) or RICE, computed by `wuwei plan add` from the lead's scores and evidence.

## 5. The evidence contract

`wuwei evidence owner/repo#n` (and the board, `wuwei status`) reads a PR and returns its gaps.
Each gap is actionable (the model can close it now), waiting (CI running, the code host
unreadable) or the owner's (owner review).

| Evidence | light | standard | full |
|---|---|---|---|
| `WUWEI-Item: <id>` names a plan item | yes | yes | yes |
| Spec engine artifacts in the diff, when the repository has `.specify/` or `openspec/` | no | yes | yes |
| A test in the diff, or `No test: <reason>` (docs-only changes exempt) | yes | yes | yes |
| Gates passed at an ancestor of the head, one of them at the head | quality | arch, quality, security | + goal |
| CI green; every review thread answered; a reviewer requested | yes | yes | yes |
| Owner review (or an owner ruling at that head) on `owner_paths` | when touched | when touched | when touched |

A verdict counts only when WUWEI attested it: at the reviewer's SubagentStop, the hook reads the
file the reviewer names (`Verdict file: <path>`), lints its shape and records its hash, gate,
item, head and agent. A file edited afterwards no longer counts. An item is done when a linked PR
merges; the board marks it.

## 6. The doors

Refused (PreToolUse deny, with the reason and the path that works):

- `gh pr merge` while the PR has gaps; `--admin`.
- Force push in any form, push to or deletion of the default branch.
- `gh api` writes to protection, rulesets, statuses, merges, collaborators, hooks, keys, secrets
  and environments; `gh repo delete`.
- A secret pattern or the workspace canary in an outward call (MCP tools; gh, curl and other
  network commands).
- Writes to `.wuwei/ledger.jsonl`; a hand-made `wuwei hook` call.
- An AskUserQuestion that does not start with a decision class (`one-way:`, `scope:`, `goal:`,
  `trust:`, `infra:`, `owner review:`): the process answers it, and the model records an
  assumption.

Asked (PreToolUse ask, the harness's own prompt): infrastructure commands (terraform, tofu,
pulumi, kubectl, helm writes).

A door that cannot read its evidence stays shut. A guard that cannot parse a command lets it
through, and the trace records it. Every other hook fails open and records `hook.error`.

## 7. Hooks

| Hook | Role |
|---|---|
| SessionStart | The way of working, `_common.md` and the planner charter, goals, local standards and the board. |
| PreToolUse | The doors; a once-per-session note with the PR standard before `gh pr create`. |
| PostToolUse | A trace per call (telemetry); after `gh pr create`, what the new PR still lacks; owner answers recorded as prompts and rulings. |
| SubagentStop | Records every seat stop; lints and attests a sentinel's verdict, sending a malformed one back once. |
| Stop | One reminder per distinct set of actionable gaps, never a loop: waits end the turn, a closed day is quiet, `stop_hook_active` always passes. |

## 8. Owner decisions

| Class | Example | How |
|---|---|---|
| `goal:` | approve the first goals | AskUserQuestion from a plan pass |
| `scope:` | work outside the goals, a reviewer's out-of-scope ask | AskUserQuestion |
| `one-way:` | dropping data, a published contract | AskUserQuestion |
| `trust:` | a trust-boundary question a gate escalates | AskUserQuestion |
| `infra:` | an infrastructure change | the harness's ask prompt |
| `owner review:` | a change under `owner_paths` | a review on the code host, or AskUserQuestion naming `owner/repo#n at <sha7>` |

Everything else is decided by the process and shown in the report. The report counts owner
prompts and questions sent back; the steward turns a question the owner keeps answering with the
recommendation into a process rule.

## 9. Configuration and records

`.wuwei/config.toml`: `repos`, `owner_paths`, `prioritisation` (wsjf or rice), `tracker`,
`telemetry`. Everything else is discovered or is part of the process.

`.wuwei/`: `plan.json`, `goals.md`, `standards.md` (rules the retro promoted), `verdicts/`,
`ledger.jsonl` (hash-chained, `wuwei verify`), `traces.jsonl`, `days/<date>/report.md`,
`retro/<date>.md`, `canary`, `cache/`.

## 10. Report, telemetry and DORA

`wuwei report` reads the ledger, traces and code host: plan passes and checkpoints, the board,
merges (each through WUWEI's check, or an exception), doors and their reasons, owner prompts,
seats and verdicts, tool calls and outward calls, hook errors, ledger integrity. `wuwei report
--dora` gives lead time (PR open to merge), deployments (or releases), change failure rate
(reverts over merges) and time to restore (unmeasured until incidents exist), from the code host
alone, so history starts complete.

## 11. Budgets

Runtime at most 2,500 lines of stdlib Python (a test holds it), five config keys, no state the
code host or git already holds, and every door named in section 6. A change that breaks a budget
deletes something first.

## 12. Deferred

- Walls: an agent identity of its own on the code host, rulesets, CODEOWNERS, and a required
  `wuwei/evidence` status (#918); `wuwei doctor` already reports each door's strength per repo.
- Attestations cross-checked against the harness transcript (#962).
- Exceptions that expire into plan items; reports as a diff since the last checkpoint.
- Escaped defects traced to the gates that passed them (#957); gate yield; earned trust (#919).
- Auditing human PRs; a different model for one gate; the Codex runtime.
- The ZIRAN audit baseline for the new agent set.

## 13. From 0.x

0.x workspaces are not migrated: `wuwei init` writes a fresh 1.0 workspace beside the old files,
and DORA reads the code host, so no history is lost. The 0.x line stays on its tag (v0.34.0).
