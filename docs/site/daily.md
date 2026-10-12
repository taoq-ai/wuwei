# The daily path

One day for a solo owner, walked through `wuwei next`. Install is on the [home](index.md) page;
anything else is in [recovery](recovery.md). `wuwei` below is the executable recorded in
`.wuwei/executable`, and every command runs in the Claude Code session.

The loop is the same all day. The planner runs `wuwei next --json` and does what it returns:
every ready launch, every due duty, and at most one owner decision, asked on its card. When a
seat stops, its completion notification brings the planner back, and it calls `wuwei next`
again. You answer cards; you never edit a file or move a phase by hand.

## 1. Start

In a project with no workspace, `wuwei next` names `bin/wuwei init --shadow`. That creates
`.wuwei/` with the guards logging only, so your first week shows what they would refuse
without refusing it. `wuwei doctor` then checks the install, host, workspace, gates and
guards in one pass, and prints the fix for anything not ok.

Each session starts with an orientation block from the SessionStart hook: the next action,
the guard switch, the goals and memory. A plugin integrity problem shows there as a warning.

## 2. Configure

With no repository configured, `wuwei next` returns the `setup` row. The planner asks you
which repositories WUWEI works on and runs
`wuwei config add-repo --name <owner/repo> --path <path> --branch <branch>` for each. Each
run prints the `config.toml` diff and its Owner step card; nothing is written before your Yes.

`wuwei config promote` proposes what each checkout declares: fast checks, CI check names,
deploy workflows and environments, each from the file and line it came from. It asks its
card too. Any other value is one `wuwei config set <key> <value>`, on its own card
([configuration](configuration.md)).

When your first week is up, `wuwei config set guards.enforce true` turns the guards on.

## 3. Plan and the morning gate

Run `/wuwei plan`. `wuwei next` then walks the morning in order:

1. `wuwei plan session <session id>` registers this session as the day's planner.
2. `wuwei doctor --section pr-flow` checks the PR flow settings once.
3. `wuwei seat brief lead day lead` briefs the lead, and the planner launches it. The lead
   proposes goals, the ordered candidates with their tickets, seats, the envelope, and any
   open PRs of yours to claim.
4. `wuwei plan propose .wuwei/days/<date>/lead.json` orders the queue and writes `plan.md`.
5. `wuwei plan gate` prints the morning gate card: `Approve today's plan as proposed?`

Pick Approve and the planner runs the card's command,
`wuwei plan approve --items <ids> --goals-confirmed`. That records the plan and writes any
new goal blocks to `memory/goals.md`. Pick `Change something` to change goals, queue,
tickets, seat policy, CAP, envelope or carry-over; the lead's answer is edited and proposed
again. Nothing launches before your answer.

An item that comes up later needs no second gate. Say what it is and which goal it serves;
the planner runs `wuwei plan add <item> --goal G-n --note "<your words>"`. Every brief for it
quotes your words under `Approved as:`, and `wuwei why <item>` shows them. With several
repositories it adds `--repo <name>`. Say FULL, a flag or a governing document, and it adds
`--track FULL`, `--trust-surface` and the like, or `--governed-by <path>`.

To keep an item's merge for yourself, say so at the gate or later. The planner records
`wuwei plan set <item> owner_merge=true`, and that PR then always comes to you.

## Starting with work in progress

Your open PRs, branches and worktrees stay as they are. The gate card names the open PRs you
authored, for example `Claims PR-12 (owner/repo#12)`, or `PR-owner_repo-12` with several
repositories. Approving claims each one as an [adopted](concepts.md#adopted) item. A PR opened after the gate is claimed with
`wuwei pr claim owner/repo#12 --goal G-1`.

The claim gives the item a checkout of the PR branch: a clean worktree you have on it, or
`worktrees/<item>`, fetched when the branch is only on the remote. A conflict, red checks or
a fix asked in review then comes back from `wuwei next` as a fix-round builder.

Work on a plan item that was done outside WUWEI, by hand or by a seat that ran unregistered,
comes back with `wuwei build reconcile <item> --worktree <path>` (or `--repo <name> --branch
<branch>`, or `--pr owner/repo#12`). It records the worktree as it is, runs the fast checks and
leaves the gates to `wuwei next`. Uncommitted files go to a builder to commit first. Running it
again changes nothing. Nothing done outside counts as tested or approved.

## 4. Through the day

After the gate, each `wuwei next` returns a set: the launches ready now, the duties due, and
one decision when there is one. A short example:

```text
$ wuwei next
set: Ready now: 2 launch(es). Do every launch and every duty now: ...
build A: wuwei dispatch next --all
build B: wuwei dispatch next --all
```

The planner runs the whole set in one turn, so builders and an item's gate seats run at the
same time, up to [CAP](concepts.md#cap). An item waiting on another, or past CAP, takes no seat.

**Build.** For a planned item the planner adds its worktree (`wuwei worktree add <item>`) and
writes the brief (`wuwei seat brief builder <item> <name> --worktree <path> --file -`). Then
`wuwei build next <item>` returns `launch`, `continue`, `check`, `park` or `done`. A `check` is
`wuwei build check <item>`, which runs the fast checks. On a non-trivial item the builder
first runs every step of the [spec engine](concepts.md#spec-engine). `done` moves the item to
`gate`.

**Gates.** `wuwei dispatch next <item>` sets the [tier](concepts.md#tier) and names the gate
roles. The planner writes one brief per role, for example
`wuwei seat brief quality <item> quality-1 --gate --worktree <path> --file -`, and launches
the ones that fit the free seats together; `next` offers the rest after those verdicts. After
each seat stops, `wuwei dispatch receive <item> <role> <seat>` records its verdict at the item's
head.

**Fix and delta.** A FIX opens a fix round: the builder continues as a fresh Agent with the
verdicts as feedback. Then the gates that asked for the fix review again, the
[delta](concepts.md#delta). A light item has no delta; the same sentinel re-reads it.
A [PARK](concepts.md#park) verdict parks the item with its reason and no card. An ESCALATE,
or a blocker at the round cap, comes to you as the day's decision.

**Raise.** Once every gate passed at the head, `wuwei next` launches the shepherd. It runs
`wuwei pr raise <owner/repo> --base main --title <title> --body-file <file> --item <item>`,
which opens the PR and moves the item to `raised`. `wuwei pr state` reads the PRs from the
code host. Red checks, a conflict or a moved head come back from `wuwei next` as `wuwei pr
act <pr>` or a new gate pass.

**Duties.** With a review channel set, a raised PR brings the `ping` duty: post the review
request. With a tracker or an owner page, a merge brings the `tracker` duty. The planner writes
each one and records it with `wuwei duty <item> <duty> --evidence <link>`. New review activity
brings the `shepherd` duty, which `wuwei next` returns as a seat launch, once per activity. The
seat answers each owed thread with `wuwei pr act <pr> --thread <id>` and `--reply`, `--fix` or
`--scope` (your card). A PR read that finds no reply owed records it. See
[duties](concepts.md#duties).

**PR loop.** While only PRs wait on people, `wuwei next` returns `wuwei pr wait`, which the planner
runs in the background. It exits on the first change `wuwei next` acts on (a review thread, red
checks, a conflict, a moved head, a merge) with one line naming the item, and the planner runs
`wuwei next`. You do not have to ask for it.

**Merge.** When the checks are green, `wuwei next` offers `wuwei merge <pr>`. It applies the
merge policy: gates at head, required checks, approvals, threads, the soak and the merge
method. When a rule that is yours to decide stands in the way, it prints its Owner step card.
When the code host reports the PR merged, the item is `merged`.

Watch the day with `wuwei status --line`, for example `WUWEI 1 building · seats 1/3`.

## 5. Owner decisions

What reaches you comes from `wuwei next`, one decision at a time: the morning gate, a round
cap spent, an ESCALATE verdict, a merge the policy does not clear or one you keep, and a PR
closed unmerged. The command that needs your answer prints its Owner step card. The planner
asks it as a question card in the session, the recommended option first. On Yes the same
command runs again ([owner decisions](concepts.md#owner-decisions)).

Seats do not ask what their mandate lets them decide. They record two-way choices under
`Assumptions:` and name a one-way question in their result.

## 6. Close

When every approved item is merged, parked, carried or escalated, `wuwei next` returns
`wuwei close`. It refuses while an item, a decision or a duty is open, and asks one question
per open item: carry it to tomorrow (recommended), park it, or keep working. The planner
records your answer with `wuwei plan carry ITEM` or `wuwei plan park ITEM`.

Once nothing is open, `close` runs the steward's close review. `wuwei next` then returns, in
order:

1. `wuwei retro` compiles the steward retro.
2. `wuwei retro --promote` lands the supported charter proposals and writes the memory index.
3. `wuwei retro` again records what promote applied.
4. `wuwei report` writes the day report: merged, parked with its reason, carried, cycle time,
   skipped duties and [unmeasured](concepts.md#unmeasured) sources. The planner shows it to
   you, and the `summary` duty posts it to your DM when that channel is set.
5. `wuwei close` closes the day.

`wuwei close --check retro` checks the retro preconditions on its own. Tomorrow starts with
`wuwei next`, and carried items come back on the next morning gate.
