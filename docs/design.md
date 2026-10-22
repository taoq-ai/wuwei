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
8. Configuration holds facts, not behaviour: six keys.

## 3. The team

Planner (the owner's session), lead, builder, four sentinels (arch, quality, security, goal),
shepherd, steward. `charters/` is the one source; `wuwei agents build` generates the agents with
their reviewed tool grants. Each seat's model and effort come from the table in the planner charter
(`docs/site/concepts/models.md`); at least one gate per head runs on a different model than the
builder. `wuwei agents build` writes each role's default model and effort into its agent file;
the hook notes a launch that departs from the table and records what ran, and never refuses one.
Seats cannot ask the owner. The planner passes each seat its
role's lines of `.wuwei/standards.md`.

## 4. The day

- Goals in `.wuwei/goals.md` set the direction. Each plan pass ends with the plan as a view
  (`wuwei plan view`, #990) and one `plan:` question, Approve or Change; new items wait for it.
- A plan pass offers each goal past its date with no ruling as `goal: G-n met? <evidence>`. A yes
  records the goal as met (the report lists it, and it gets no new items); a no waits until its
  date moves. A ruling holds while the goal keeps the Outcome it answered, so a goal rewritten in
  place is asked again. `goals.md` changes only by the owner.
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
accepted exception drops that gap at that head and adds a follow-up item that closes it. The
accepted gap must equal the printed gap text (case, spacing, end marks and a printed `[waiting]`
aside), or equal the gates a gate gap names (`security` for `gates missing at head <sha7>:
security`); a part of either waives nothing. `wuwei evidence`, the merge door and the ready door read
exceptions alike, and the `verdict ... not counted` lines under an accepted gate gap go with it.
The question door sends back an `exception:` that names a template, size or age gap (process fit);
one that names a spec engine gap reaches the owner, since at full tier that gap is safety. When the
gap holds a finding row (a `: |` before the gap's first `. ` or `?`), the hook reads it to the row's
end (its last `|` before a `. `, `?` or the end), so the row keeps its sentences; any other gap ends
at its first `. ` or `?`, whatever `|` the question's own words hold. Each open finding row and each
checklist with an unchecked box is its own gap, so a yes waives only the gap the owner saw. A long
row prints to its last cell edge within 100 characters, unless that cut matches another spec gap of
the PR, in any file, cut or whole, the way an exception matches (case, spacing, end marks and a
printed `[waiting]` aside); then the row prints whole. Gaps whose whole texts still match that way
(rows that differ only in case, or files and feature folders whose names do) carry their place
after the feature folder, as in `specs/7-rate-limits/(2 of 2) checklists/a.md has 1 unchecked
item`, so each takes its own yes. A row whose feature folder name holds a `. ` or `?` cannot be
waived, since the hook ends its gap there.

## 6. The evidence contract

| Evidence | Applies |
|---|---|
| The WUWEI footer names a plan item (the older `WUWEI-Item: <id>` line still links, with a process-fit line naming the footer) | every PR |
| The repository's PR template sections | when it has a template |
| A test in the diff, or `No test: <reason>` (docs-only exempt) | every PR |
| At most 400 changed lines (generated files aside), or `Size: <reason>` | every PR |
| `Rollback: <how>` | full tier, or `owner_paths` touched |
| The spec engine's steps by their artifacts at the head (spec-kit: spec, plan, tasks all checked; full adds clarifications, a clean analysis, checked checklists; OpenSpec: proposal, a capability spec, tasks all checked) | standard, full and smart complex (where they hold the merge), when the repo has `.specify/` or `openspec/` |
| The gates the diff needs passed at the head before the PR turned ready (it opens as a draft so CI runs), each at an ancestor of the head; a later delta re-read by the one gate it needs, unless it is docs or at most 20 lines off risky paths. The delta is what moved in the PR's own diff against its base, so a base merge that leaves the PR's own patches alone (line numbers aside) carries the passes, as do files a dated `Generated` standards line names off risky, owner and contract paths | the tier is the ceiling: docs none; code quality; standard adds security for risky or owner paths and arch for a wide change (over 200 lines that are not prose, or 10 code files; prose as CI not started reads it below, and specs count); a contract file or a spec contract (under a spec's `contracts/` folder) takes arch at any tier; full takes all four; smart, the default, starts from standard and adds by the item's Cynefin domain (complicated: arch on a trust path; complex: security and arch) and by measured signals (a function's McCabe complexity rising over 10: security; a patch naming what a guard waives or refuses: arch; a promise in doubt: goal) |
| CI green (every check the base branch requires ran), threads answered, a reviewer requested | every PR |
| Owner review, or an `owner review:` ruling, at that head (a `breaking:` or `exception:` ruling is not one) | `owner_paths` touched |
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

CI not started: a head with no checks whose diff, read by both names of a renamed file, is empty or
holds more than prose (`.md`, `.rst`, `.adoc`), `LICENSE`, `NOTICE`, `specs/` and `openspec/` (a
`.txt`, code under `docs/` and the files seats load, such as charters, agents, skills and
`AGENTS.md`, are not prose), in a repository that ran a `pull_request` or `pull_request_target` workflow (Actions reads cached a
day), reads `CI not started at <sha7>`; a path-filtered workflow holds a code PR it skips until an
exception. An unreadable Actions host shows the gap with `(Actions host unreadable: <error>)`.

Required checks: the checks the base branch requires, by branch protection (the branch read) and by
the rulesets for the branch, cached 15 minutes per repository and branch. A required check with no
check run and no status of that name on the head, once CI has settled, reads `required check not run
at <sha7>: <names>`, an actionable safety gap, with or without auto-merge (a push with the workflow
token starts no workflow, #1156). While CI runs it reads `required check not run yet`, waiting, and
arming auto-merge passes (GitHub creates a job's check run only once it is queued). A release PR's
gap points at the way through: a `RELEASE_PAT` secret for release-please (contents and
pull-requests write), meanwhile a close and reopen or an owner exception. A failed or malformed
read shows `required checks unreadable on <branch>: <error>`, waiting, and is not cached. A PR
GitHub reports `mergeable_state` blocked with no other safety gap reads `GitHub reports the merge
blocked for a reason WUWEI cannot name`, waiting; it holds a direct merge, and arming auto-merge
passes, since GitHub's auto-merge waits on that hold.

Breaking changes: a breaking change is a SemVer 2.0.0 major, an incompatible change to the
declared public API. The public API and
the classification are declared once, in
[the evidence contract](site/concepts/evidence.md#breaking-changes). A break (declared with `!` or
`BREAKING CHANGE:`, or found by the arch gate's required `Breaking:` line; a contract file or a
spec contract takes the arch gate at any tier) needs an `Announcement: <url>` line and then the owner's `breaking:`
confirmation at the head. Both are safety gaps. The line holds one http(s) URL alone, without
brackets, of a communication that already exists: a PR or issue comment, or a published release
note or migration guide. A changelog entry written at release does not count.

Error budget: when a repository's 28-day change failure rate (change failures over merges, at most 1,
with at least five merges) is over 15 percent, every tier there rises one step and takes its full gate
set, untrimmed by the diff. A change failure is a merged PR whose title starts with the word revert
(any case), or a run of failed production deployments up to the next successful deployment of the
same environment. A deployment is production when GitHub flags its environment as production, or
when the environment name holds prod or production as a word not led by pre or non. Only the newest
100 production deployments in the window are read, one status read each. When the deployments cannot
be read, the reverts alone count. Time to restore runs from the first failed deployment of a run to
the green one. Verdicts count only when attested at
the sentinel's stop (shape linted, hash, gate, item, head, confidence, agent recorded). A gate's
verdicts are read oldest first, and only at an ancestor of the PR head. A pass counts only for this
PR, for its repository alone, or when it names no PR (an imported 0.34 verdict). The merge door and
`wuwei evidence` read the PR; the create and ready doors read none, so there a pass for any PR of
the item in that repository counts. A finding holds from any PR of the item and displaces a pass.
A later pass at an older head never clears a finding. At the same head it clears a FIX only by
naming that file on a `Supersedes:` line; otherwise only a pass from a strict descendant does. An arch `Breaking: no` clears a yes
only from a strict descendant of that yes's head, and only for this PR or its repository alone;
`Supersedes:` does not apply to it. Gaps are
actionable, waiting or the owner's; an unreadable code host is a waiting gap, never a pass. A PR read
after it merged lists what it lacked as `post-merge:` gaps, and the report counts a finding attested
after the merge as an escape.

Operations items: an item done by a run, not a change (a backfill, a re-drive, an operator step),
records its run evidence (`wuwei plan run <id> --reason`); the board shows that evidence, not a
missing PR, and `wuwei plan done` closes it with the final evidence. A Codex background job is
registered with `wuwei plan run <id> --job <job file>`: the board reads that one file, never another
plugin's folders, and shows the job running, queued, completed (with the `HANDOFF.md` path it
names), failed, cancelled or asked a question (its last answer ends in a question). A file it
cannot read shows `job state unreadable`, never done.

## 7. The doors

Refused: a merge with safety gaps by any route (`gh pr merge`, a REST PUT on `pulls/<n>/merge` or
`ccr/auto_merge` in any spelling of method, path, host or `{owner}/{repo}`, a GitHub MCP merge
tool; arming auto-merge passes while only CI runs or only GitHub's own merge hold is left); a PR
opened ready for review (`gh pr create`, `gh pr new`, a REST POST on `repos/<r>/pulls`, a GitHub MCP create tool) before the gates its diff
needs pass at the branch head, while a draft (`--draft`, `-F draft=true`, MCP `draft` true) opens so
CI runs; the flip to ready (`gh pr ready`, a REST POST on `pulls/<n>/ccr/ready_for_review`, MCP
`update_pull_request` with `draft` false) and a reviewer request on a draft (`gh pr edit
--add-reviewer`, a REST POST on `pulls/<n>/requested_reviewers`, MCP `reviewers` or
`request_copilot_review`) before the gates pass at the PR head, so review starts at a gated head
(#1050, #1074), unless the owner accepted the gate gap for that PR at that head (#1168);
`--admin` (and `--admin=true` in any spelling pflag reads as true; `--auto` counts only where pflag
reads it as the flag); a `gh api` write to an endpoint under `repositories/<id>` (spell it
`repos/<owner>/<repo>`); a `gh api graphql` query WUWEI cannot read (`--input -`, `-F query=@-`, a
missing file, or a file outside one plain one-line `gh` call); `gh api` writes to protection, rulesets, statuses,
collaborators, hooks, keys, secrets and environments; `gh api` writes to `merges`, `git/refs/` or
`contents/` on any branch; `gh repo delete` and a REST DELETE on the repository; a `gh api graphql`
mutation that merges, arms auto-merge, opens a PR, marks one ready, requests reviewers, moves a ref, commits to a branch or changes
branch protection or rulesets (among them `mergeBranch` and `enqueuePullRequest`); force pushes in
every form; pushes to or deletion of the default branch (a destination as git 2.43 reads it: `main`,
`heads/main` or `refs/heads/main` after the last colon, or the ref git itself resolves a source alone
to; the matching refspec `:`, `--all`, `--branches` and a glob whose destination can match it; a word
an option takes is no refspec, and every word after the first `--` or `--end-of-options` is one; a
push of a ref named `--`, which git reads per worktree, and a push whose refs git cannot read in 5 s
too),
including the GitHub MCP `push_files`, `create_or_update_file` and `delete_file` tools on the default branch or with no branch (a force
push, push or delete to a git directory in a scratch folder passes in one plain git call, as
SECURITY.md reads it); a git
command naming `push` after an option before the subcommand that git 2.43 does not take, or after a
`-c` or `--config-env` that sets `remote.*`, `branch.*`, `url.*` or `push.default`; a git command
after a `-c` or `--config-env` that sets an alias or an include, whatever the subcommand; a secret
or the canary in an MCP call or network command; writes to the ledger or the cache in the spellings
sh expands (`//`, `/./`, `..`, globs, braces; `find` with `-delete`, `-exec`, `-execdir`, `-fprint`,
`-fprintf` or `-fls` on them; a path in a `python -c` body; a writer or redirect after `cd .wuwei` or with a `-C`, `--chdir` or `-D` value naming it;
`git clean -x` or an exclude unless every pathspec is a plain word outside `.wuwei`, and git clean
after any git option but `-C` or with `GIT_` in the command), while
removing a cache file passes; writes under the harness's transcripts (`.claude/projects`, or `.claude` itself) in the
same spellings and after the same `cd`, `pushd`, `-C`, `--chdir` and `-D` (reads pass); a hand-made `wuwei hook` call; an
owner question without a class.
A multi-line or unreadable Bash command whose raw text names a door program (git and push; gh with
pr, api or repo; wuwei followed by hook; `.wuwei/ledger` or `.wuwei` itself), with a hint to run the door command in its own
one-line call (#1068); other multi-line commands are read line by line. `$'...'` and `$"..."` quoting
makes a command unreadable, and so does a shell with no `-c` body (fed by a pipe, a here-string, `-s` or
`< file`, or given a script path), while its segments still meet the other doors; a run of punctuation such
as `<(` or `;>` is split into the operators sh reads, and every redirect (`<x`, `>&2`, `2>&1`, `{fd}>x`, `<<x`) is
read as one, so process substitution, glued separators and redirects reach their doors. The doors read a command
inside a loop, an if or a brace group, a shell's `-c` body after combined flags (`bash -lc`), and,
after a wrapper (env, timeout, nice, sudo, xargs), the first program a door reads.
Asked through the harness: terraform, tofu, pulumi, kubectl and helm writes.

A door that cannot read its evidence stays shut: an error while PreToolUse judges a door call (an edit
tool in `guards.DOORS` or a Codex apply_patch, any MCP tool, or a Bash command that names a door program
or a network program in `guards.NETWORK`, read with its quotes and backslashes removed) refuses
it, names the error and records `hook.error`. Every other hook fails open and records `hook.error`.
The launcher is the one exception: when the PreToolUse hook fails before it can judge (an import, its
arguments, the version read), `bin/wuwei` exits 2 and refuses every PreToolUse call, not only door calls.
An account with no password-database entry is not such a failure: the hook loads, its doors judge, and
answers and seat stops record as unconfirmed (section 8).
`wuwei doctor` reports each door's strength per repository: wall (code host or credentials), refused
(hook), detected (audit).

Andon: `wuwei andon owner/repo --reason` holds new builds in one repository until cleared; others
flow.

## 8. Hooks

| Hook | Role |
|---|---|
| SessionStart | under Claude Code's 10,000-character cap: the CLI path, the way of working, `_common.md` Decisions and Done, where the planner charter, goals and standards are, the board with how many items it left out |
| PreToolUse | the doors; the PR standard with a ready body once per session; a gate's verdict lint and attestation at its hand-back; outside auto mode a hand-back, which the harness refuses, is answered with the plain-text report rule so the seat ends instead of retrying |
| PostToolUse | traces; what a new PR lacks; prompts, rulings, exceptions, ADR notes, recorded only once the session transcript shows the answer (below) |
| SubagentStop | seat stops with tokens and confidence; verdict lint and attestation, or `verdict.missing` when a block can no longer reach the seat; all only when the session transcript shows the seat's launch, else `seat.unconfirmed`; outside auto mode a seat's report is kept for the planner, once per text |
| Stop | a reminder only when actionable work is new since the last one, naming only what changed; once, to arm the watch when only waiting work is left and no watch pass ran in the last hour, or to plan from the goals when the queue is empty; never a loop |

An owner answer and a seat stop count only when the harness wrote them (#962). The harness keeps
each session's transcript under the projects folder (`.claude/projects` in the account's home,
read from the password database, never from `HOME`). An answer counts when that transcript holds the
AskUserQuestion tool_use with the payload's `tool_use_id` and, in the last tool_result row for it,
the same answer to that question; each question in a batch counts on its own. Only the row's
`toolUseResult.answers` counts, never its text: model-written questions and labels and WUWEI's own deny
reasons fill that text, so a pair in it proves nothing. Claude Code
writes that row after PostToolUse returns, so PostToolUse records `answer.pending` and keeps the first
answer for its ids, and the planner's next hook call records it before any door reads the ledger. An
error in that step records `hook.error` and the doors still judge the call. A Stop rereads for up to
1.5 s for a row (not once the answer is 10 minutes old) and records an entry it can record whole; any other
entry waits for the next call, so it never blocks the Stop (#1231). `answer.unconfirmed` records what is not recorded, with the check that failed: a
transcript path outside the projects folder, no AskUserQuestion tool_use with the id, no
`toolUseResult` answers in the row, a question whose answer differs (both values
named, cut to 60 characters), or no tool_result row after 10 minutes. An `answer.pending` row that no
`prompt` or `answer.unconfirmed` row with its id follows (a session that ended before another hook
call) reads as unconfirmed. Each answer id is recorded once: a replay records nothing more. A seat stop counts when the meta file beside the seat's transcript names its
type and Agent tool_use and the session transcript holds that tool_use. Codex answers and stops, a
moved Claude Code folder (`CLAUDE_CONFIG_DIR`) and an account with no password-database entry are
recorded as unconfirmed until a reader for those transcripts exists. A process that writes the
transcript itself stays open (SECURITY.md).

## 9. Learning

At each checkpoint the steward writes the retro with at most three proposals: defect vaccines (a
regression test item and a gate standard per escaped defect), calibration and gate yield findings,
skills and memory lines for a repository (landed through a PR there), and rules to retire (a rule
that caught nothing in 30 days; a new rule is a note for its first five days). Charters shrink the
same way: a line nothing cited in 30 days, or one that names one repository's files, is proposed
for deletion or for a standards line, and a test holds each generated agent under a word ceiling.
A kind of owner question always answered with the recommendation becomes a rule.

## 10. Records, report, DORA

`.wuwei/`: `config.toml`, `plan.json`, `goals.md`, `standards.md`, `verdicts/`, `ledger/<clone>.jsonl`
(hash-chained, versioned rows, one file per clone, `wuwei verify`), `traces.jsonl`, `days/<date>/report.md`,
`retro/<date>.md`, `canary`, `cache/`. The state travels on the `wuwei/state` branch (`wuwei
sync`; pulled at a cloud session's start, pushed at its stops); `wuwei init --cloud` copies the
plugin into a repository's `.claude/` for cloud sessions, where repository plugins do not load.

The report: plan passes and checkpoints with the diff since the last, the board, merges through the
check or as exceptions, the doors, owner prompts, seats and verdicts, learning (escapes traced to
gates with confidence, change failure rate and raised tiers, unplanned PRs, gate yield, tokens by
role, each seat by model and effort, open exceptions, the weekly sample), telemetry, ledger integrity. DORA comes from the code
host alone. Replay cases (`wuwei evidence --record`) hold every future version to past answers.

## 11. Configuration and budgets

Six keys: `repos`, `owner_paths`, `prioritisation`, `tracker`, `telemetry`, `models`. Runtime at
most 3,600 lines of stdlib Python (a test holds it). A change that breaks a budget deletes something
first.

Codex: the same plugin loads in Codex (it reads `.claude-plugin/`, `skills/` and
`hooks/hooks.json`, with the same hook events and outputs). The hook entry maps Codex's tool shapes
(`apply_patch`, `spawn_agent`, `request_user_input`) onto the ones the guards read; `wuwei init
--codex` writes the role agents to `.codex/agents/` and the doors to `.codex/rules/wuwei.rules`.

## 12. Deferred

- Walls: an agent identity on the code host, rulesets, CODEOWNERS, a required `wuwei/evidence`
  status posted by CI (#918).
- Attestations read from the seat's own transcript (#962): a sentinel's SubagentHandback at
  PreToolUse still attests from its payload, and a SubagentStop that replays a real launch attests
  and keeps the report text its payload carries.
- A shared standards repository for teams; auditing human PRs as first-class items.

## 13. From 0.x

`wuwei init` upgrades a 0.34 workspace in place: it reads the old config shape and rewrites it
(keeping `.wuwei/config.0x.toml`), names each retired key, carries the goals forward, imports the
open items with their PR links and the latest proposal, and imports the gate verdicts as
attestations so in-flight PRs need one delta gate, not a full set. DORA reads the code host, so
no history is lost. The 0.x line stays on its tag (v0.34.0).
