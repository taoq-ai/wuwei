# The daily path

One path for a solo owner through one day: install, configure, plan, build and review,
decide, close. Every command here is daily use. Anything else is in
[recovery](recovery.md). `bin/wuwei` below is the executable in the plugin
directory; the planner uses the one recorded in `.wuwei/executable`. Each Claude Code
session in the workspace gets the same flow as [what the session knows](agent.md).

## 1. Install the signed release

Claude Code, Python 3.11 or newer, Git and `ssh-keygen` must be available. From your
project directory:

```sh
curl -fL https://github.com/taoq-ai/wuwei/releases/latest/download/wuwei.tar.gz -o ../wuwei.tar.gz
mkdir -p ../wuwei-plugin
tar -xzf ../wuwei.tar.gz -C ../wuwei-plugin --strip-components=1
```

In Claude Code:

```text
/plugin marketplace add ../wuwei-plugin
/plugin install wuwei@wuwei
```

Then create the workspace in your project directory:

```sh
../wuwei-plugin/bin/wuwei init --shadow
```

`init` ends with `plugin integrity: clean` for an intact signed release. A development
checkout needs one host confirmation first; see [recovery](recovery.md).

Then run `bin/wuwei doctor`. It checks the install, host, workspace, [gates](concepts.md#gate), day and guards in
one pass and prints the fix for anything that is not ok; `bin/wuwei doctor --fix` applies the
deterministic fixes after one confirmation. When something fails on the first day, see
[troubleshooting](recovery.md#troubleshooting).

Then open Claude Code in the workspace and say what you want; the session knows the rest.

## 2. Configure

Open Claude Code in the workspace. `wuwei next` asks for the repositories first: the planner
asks you which repositories WUWEI works on (owner/repo, path, default branch) and runs
`wuwei config add-repo --name <owner/repo> --path <path> --branch <branch>` for each one. Each
run shows the `config.toml` diff and asks its Owner step card; nothing is written until you
answer Yes.

Then the planner runs `wuwei config promote`. It surveys each checkout and proposes what the
repositories declare: fast checks, CI check names, deploy workflows and environments, each from
the file and line it came from ([calibration](configuration.md#calibration)). It prints the
diff and the calibration it will record in `.wuwei/calibration.json`, and asks its Owner step
card. `wuwei config promote --measure` also times each test runner once and proposes only the
fast ones.

Any other value is one `wuwei config set <key> <value>`, on its card too. Credentials go in
`.wuwei/env`; `bin/wuwei config check` names each variable the selected adapters still need.
You do not write goals by hand: the lead proposes them at the first morning plan and
`wuwei plan approve` records the ones you approve. A later change to `.wuwei/memory/goals.md` is
recorded by the next gate approval.
[Configuration](configuration.md) lists every key.

Then run `bin/wuwei doctor`. A missing calibration warns `never applied` with the fix
`wuwei config promote`. The branch protections and the watch service are the usual first-day
findings:

```text
$ bin/wuwei doctor
...
Gates and adapters
  fail       config check: exit 1
      fix: apply the fix each detail line names
      ...
      Host protections:
      acme/widget main: classic protection: none visible (404: unprotected or no admin)
      acme/widget main: required checks: missing (require status checks on main)
      acme/widget main: required reviews: ok (solo owner: shepherd.min_reviewers = 0)
      acme/widget main: force pushes: missing (block force pushes on main)
      acme/widget main: deletions: missing (block deletions of main)
      acme/widget main: fix in https://github.com/acme/widget/settings/branches
      ...
Day and sessions
  ...
  warn       watch: not installed
      fix: wuwei watch install
      ...
doctor: 1 fail, 1 warn, 0 unmeasured, 0 waiting
```

Set the protections when you are ready, and run `bin/wuwei watch install` when you want the
background supervisor. See [troubleshooting](recovery.md#troubleshooting) when a first-day
check fails.

`--shadow` starts a first week in the observe posture. The guards then record what they would
refuse and let the call through. Records still refuse. Deploys, releases and messages that wait
for your approval ask you on a card, and merges and approvals stay yours. Read the `## Shadow`
section of the day report. When `bin/wuwei doctor` asks after `guards.shadow_days`, run
`wuwei config set security.posture '"guarded"'`, or keep watching with
`wuwei config set guards.shadow_days 14`; each asks its card. See
[security posture](concepts.md#security-posture).

## 3. Plan and the morning gate

Run `/wuwei plan` in Claude Code. The planner registers its session
(`wuwei plan session`), sweeps live work, asks the lead for candidates, orders them with
`wuwei rank` and writes the proposal with `wuwei plan propose`. It then asks you one
`Morning gate` question, `Approve today's plan as proposed?`. Pick `Change something` to get
the separate questions on goals, queue, [seat](concepts.md#seat) policy, [CAP](concepts.md#cap),
[envelope](concepts.md#envelope) and [carry-over](concepts.md#carry). Nothing is dispatched before your answer. While `memory/goals.md` has no goals,
the lead proposes them, `plan.md` shows them as provisional and the approval question shows the
blocks. On approval the planner records the gate with
`wuwei plan approve --items <ids> --goals-confirmed [--note "<your words>"]`, which also writes
the approved goals to `memory/goals.md`.

When an item in the plan needs a deploy, a release or a merge you decide, the lead lists it and
the plan shows it as an `Owner-only: <action> <target> (owner step)` line. The gate does not
approve it ahead of time: when the seat gets there, the command asks you its own Owner step card
([owner-only actions](concepts.md#owner-only-actions)).

An item that comes up after the gate needs no second gate. Say what it is and which goal it
serves; the planner runs `wuwei plan add <item> --goal G-n --note "<your words>"` and the item
joins today's plan. Every builder and gate brief for it quotes your words under `Approved as:`,
and `wuwei why <item>` shows them. A candidate the discovery sweep found goes through
`wuwei plan add <item>` and the intraday start policy.

The planner asks the morning gate as question cards. After you approve, it records the goals
and the plan, and you can run the last command yourself. A clean first plan with one
goal and one item looks like this:

```text
$ wuwei plan propose .wuwei/days/<date>/lead.json
<project>/.wuwei/days/<date>/plan.md
$ wuwei plan approve --items DIV-1 --goals-confirmed
$ bin/wuwei status --line
WUWEI 1 planned · seats 0/1 | pages 0 · observe
$ bin/wuwei next
dispatch: 1 planned item(s) can start, 0 of CAP 1 building; run the launch set, brief each start and launch the set in one turn. Run: wuwei dispatch next --all
```

It worked when `memory/goals.md` holds your goal, the status line shows `1 planned` and
`bin/wuwei next` names the first item. `plan approve` prints nothing when it succeeds, and
`meeting unmeasured` only means no calendar is set up. It did not work when the status line
has no `planned` count after you approved, or when a command exits 1 or 2 with a reason; see
[troubleshooting](recovery.md#troubleshooting).

## Starting with work in progress

Your open pull requests, branches and worktrees stay as they are; nothing is recreated. The
morning sweep lists the open PRs you authored in the configured repositories (by
`owner.handles`) under `## Open PRs to claim` in the plan, and the gate card names them:
`Claims PR-12 (owner/repo#12)`. Approving the gate claims each one under the first goal.

Each claim creates an [adopted](concepts.md#adopted) item (`PR-12`, titled from the PR), links the PR and
makes it one of the day's owned PRs. When a clean worktree is already on the PR branch, the
claim adopts it too. A PR opened after the
gate is claimed with `bin/wuwei pr claim owner/repo#12 --goal G-1`; with one configured
repository a bare `12` works, and with one goal for the day `--goal` can go.

The [shepherd](concepts.md#shepherd) needs no checkout. `bin/wuwei pr act` pings reviewers, reads CI, answers review
threads and takes the merge decision through the code host. Only a fix round or a rebase needs a
checkout, and then `pr act` returns an `adopt` action with the exact command and `then` to run
after it:

- `bin/wuwei worktree adopt <path> --item <item>` registers a worktree you already have. It
  chains the hooks, writes the pre-push anchor at the current HEAD and records the path. It
  refuses a tree with uncommitted or untracked files and names them.
- `bin/wuwei worktree add <item> --branch <branch>` checks the existing branch out in
  `worktrees/<item>` and records it as the item's.

Run `bin/wuwei pr act <ref>` again and the fix round starts in that worktree.

## 4. Through the day

The day starts in parallel. After you approve, the planner runs `wuwei dispatch next --all`,
which lists every item that can move now: items at the gate first, then items building, then
planned items up to CAP, each goal's share first. It briefs the new items and launches the
whole set in one turn, so several builders, and an item's three gate seats, run at the same
time. An item that does not fit waits and says why. The status line shows
`seats 2 of CAP 3 (G-1 1, G-2 1)`, and `bin/wuwei next` names the waiting item and the seat
expected to free first.

Watch the status line and `bin/wuwei next`. The status line counts items in words, for
example `1 building`, and later `1 shipped`. The planner runs one loop per item and
executes each returned action unchanged:

1. Worktree and builder brief: `wuwei worktree add <item>`, then
   `wuwei brief builder <item> <name> --worktree <path> --file -`.
2. Build: `wuwei build next <item>` returns `launch`, `continue`, `check`, `park` or
   `done`. The planner runs `launch` and `continue` through Agent and a `check` through
   its `command` (`wuwei build check <item>`), then calls `build next` again. `done` means
   the checks passed and the item is in `gate`.
3. Gates: `wuwei dispatch next <item>` returns `gates` with the roles still needed. The
   planner writes one gate brief per role, for example
   `wuwei brief quality <item> quality-1 --gate --worktree <path> --file -`, and calls
   `dispatch next` again. Its `seats` list holds one ready action per brief: `launch`
   with `prompt` and `agent_type`, and `receive`, the exact
   `wuwei dispatch receive <item> <role> <seat>` call to run after the seat stops. At the
   first gate the action also carries the item's `tier`: `light` asks for the quality gate
   only, `standard` and `full` for all three.
4. Fix round: when a gate says FIX, `dispatch next` returns `fix` with `command`
   (`wuwei build next <item>`). The item is already in `fix` and the stopped builder has a
   `continue` action with the FIX verdict files as feedback. The planner launches a fresh
   Agent with its `prompt`; Claude Code's Agent takes no `resume`. Then it runs the build
   loop again until `done`, which moves the item to `delta`.
   A [PARK](concepts.md#park) verdict parks the item with its reason and no card. An
   ESCALATE verdict returns `escalate` with the Owner step card of `dispatch next <item>`
   and exits 1; the planner asks it. On Yes the next `dispatch next` opens the fix round;
   on No it parks the item. At the round cap it parks the item and names
   `wuwei plan resume <item>`, which asks you its own card. `build next` prints the same
   answer.
5. [Delta](concepts.md#delta): `dispatch next` returns `gates` for the roles that did not pass, and `seats` holds a
   `continue` action per seat with its `prompt`, `resume` (the seat's agent ID) and a
   `receive` call with `--round delta`. The planner launches it as a fresh Agent, which
   continues the same seat. `dispatch next` records the head the fix round left on the
   reviewer's seat, and the `continue` feedback names it. The delta verdict's `Head:` is that
   head, whether the planner continues the seat in its session or as a fresh Agent. After
   the delta verdicts it returns `raise` with review notes,
   the next fix round, or `escalate`. `raise` carries the shepherd's brief command in `commands` (its body
   carries the review notes), then the shepherd launch in `seats`; `build next` returns the same. With no round left the item parks with its reason,
   and `escalate` names `wuwei plan resume <item>` as its `command`. A
   light item has no delta review: its `continue` feedback starts
   `Re-read:` and the same [sentinel](concepts.md#sentinel) rewrites its `Verdict:` and `Head:` lines.
6. Pull request: `wuwei pr raise <owner/repo> --base main --title <title> --body-file
   <file> --item <item>` opens the PR, links it to the item and moves the item to `raised`.
   The shepherd opens it this way. A `gh pr create` for a recorded item that links no PR
   warns naming `wuwei pr raise ... --item <item>` below strict and is refused under strict. `wuwei pr state`
   reads the host; `wuwei pr act <ref>` returns the next PR action, including a post-PR fix
   round. When the host reports the PR merged, the item is `merged`, whatever round it
   was in.

Process depth follows the [tier](concepts.md#tier). A light item skips the class sweep, gate step zero and
the long verdict rows. A standard item sweeps only the classes `wuwei sweep classes
<worktree>` lists and mutates only when its diff touches guard code or a trust path, or the lead flagged it
trust_surface or boundary_relevant. Each
brief's `Depth:` line says which. The report's `## Cycle time` section shows how long each
merged item took and the median per tier against the targets (light 60, standard 180
minutes).

On a non-trivial item the builder first runs every step of the configured [spec engine](concepts.md#spec-engine)
(spec-kit by default: specify, clarify, plan, tasks, analyze, checklist, then implement) in
the item's worktree. Under [strict mode](concepts.md#strict-mode) the hooks refuse source edits until the
steps before implementation are done, and the build loop keeps the item from the gates
until all of them are. An item the lead marks `tier: light` skips the spec. To skip one
item yourself, run `bin/wuwei plan set <item> spec=skipped --reason <why>` in a host
terminal; `spec=required` turns the check back on.

Phases move by themselves: `planned`, `implement`, `gate`, `fix`, `delta`, `raised`,
`merged`. You never move one by hand on this path.

With a [docs system](concepts.md#docs-system) configured, an item tiered standard or full
carries a [docs obligation](concepts.md#docs-obligation): before its quality gate passes the
builder records `bin/wuwei plan set <item> docs=<page>|new|none --reason "<why>"`, or under
markdown writes the file with `bin/wuwei docs page <item>`. `wuwei next` shows a `docs` row
until it does, and `close` names any merged item whose docs were never written.

To keep an item's merge for yourself, tell the planner (or name it under `Change something` on
the morning card); it records `bin/wuwei plan set <item> owner_merge=true`. From then on
`wuwei merge`, `merge check`, `pr act`, the PR guard and the overnight shepherd refuse that
PR, whatever the merge policy says, with `owner merges: owner_merge set by <who> on <date>`. The PR carries
the `owner-merge` label and, when raised after the flag, an `Owner merges:` line in its body.
Only you clear it, with `bin/wuwei plan set <item> owner_merge=false` in a host terminal; the
next pass then follows the normal merge policy. If you merge it by hand instead, the item
moves to `merged` with the flag still set, so the record shows which way it went.

With a tracker set up, every item has a [ticket](concepts.md#ticket). The plan proposes one
per item and Approve opens or links them. An item still without one stops with a line naming
its card; under strict the line names `bin/wuwei tracker create <item>` for a host terminal. `wuwei next` and the loop DM show the
ticket id beside the item, and WUWEI comments the item's phases, pull request and merge on it.
Decisions and review results wait in `bin/wuwei drafts` until you send them.

A draft is one card away from being sent. The refusal names the draft id and the rule that
held it; the planner asks you its card (`bin/wuwei drafts show <id> --widget`) and records
your answer with `bin/wuwei drafts approve <id>` or `drafts drop <id>`. Under strict you run
that line in a host terminal. A draft from a connector goes out when the seat repeats its
call, once.

PR changes reach the planner without you. Every change on a raised or claimed PR that
needs an action is one `pr.changed` event with a summary, for example
`PR owner/repo#12: 2 new review comments by alice on cli/x.py; check test (3.11) failed`.
Each part is delivered once. A passed check, a resolved conflict, a reviewer request, a
timestamp, or a PR starting or stopping being owned does not wake the planner;
`bin/wuwei watch why <pr>` says what the last change fired and what it suppressed.
The Stop hook message lists that summary first, and the status line
shows `prs <n> changed` until the planner has seen the wake. An idle interactive planner
learns of a change at its next turn (its next Stop or session start): Claude Code cannot
put input into an idle session. For CI events in your own
session, the Claude Code desktop PR monitor is the complement.

## 5. Owner decisions

What reaches you comes from `bin/wuwei next`, one decision at a time: the morning gate, a
merge the policy does not clear or one you keep, an ESCALATE verdict, a parked item to
resume and a scope change a reviewer asks on a PR. The command that needs your answer
prints its Owner step card; the planner asks it in the session and runs the command again on
Yes. A [PARK](concepts.md#park) verdict parks the item without asking you; the report and
`bin/wuwei why <item>` show its reason. `bin/wuwei drafts approve` or `drafts drop` answers a
held draft.

To answer from your phone, run the planner session with Claude Code Remote Control
(`claude --remote-control`, or `/remote-control` inside the session) and turn on
"Push when actions required" in `/config`. Each question then reaches the Claude
mobile app and stays open until you answer.

Seats do not ask what their mandate lets them decide: they record two-way choices under
`Assumptions:` and name a one-way question in their result.

### How you answer

In the Claude Code session (desktop app, terminal or IDE alike) each owner question shows up
as a question card: tap an option, the recommended one first. The planner records your pick
with the command printed beside the card. When that command needs your confirmation in a
host terminal, the planner shows you the line to run.

Away from the session, the same question reaches your phone through Remote Control.

Use the host terminal for what a hook sends there: today your commands listed at the top
of this section, and under `strict` posture everything owner-only.

## Long sessions

The planner session is the one long-lived context of the day; seats are fresh per item.
Quality can drift as that context grows, so WUWEI measures it and lets you rotate the
planner on a schedule.

- Measured: `bin/wuwei report` has a `## Quality by band` section with gates, FIX rate,
  fix rounds, verdict lint rejections and your interventions. It splits them per hour band (morning
  05-11, midday 11-14, afternoon 14-18, evening 18-05, in `owner.timezone`) and per
  planner session-age band (turns since it started today, or compacted). `bin/wuwei retro`
  compares the last 7 days, names the worst band when its FIX rate leads every other band
  by `metrics.band_margin`, and proposes a planner charter line for you to promote or
  reject.
- Rotation: set `sessions.rotate_after` (`turns`, `compactions` or a `clock` time; off by
  default). At the first turn past the limit with no running seat, the Stop hook tells the planner to end the session once. Start a fresh Claude
  Code session in the workspace and run
  `wuwei plan session "$WUWEI_SESSION_ID" --take-over` there. `bin/wuwei sessions` shows
  the old session as `rotated`, and the events record `session.rotated`. Nothing is lost:
  the day lives in `.wuwei/`, not in the transcript.
- Re-anchoring: every SessionStart payload, after a compaction or a rotation too, opens
  with the orientation block: what WUWEI is, the posture and the next step from
  `bin/wuwei next`. `Active constraints:` follows with the day's goals, the approved plan
  and the briefs of running seats. The full day state is no longer pasted
  into the session; it is one command away, `bin/wuwei state get`.

Set them with `bin/wuwei config set` in a host terminal, for example
`bin/wuwei config set owner.timezone '"Europe/Lisbon"'`,
`bin/wuwei config set metrics.band_margin 0.3` or
`bin/wuwei config set sessions.rotate_after.turns 200`. Each shows a diff and applies it
after its [digest](concepts.md#digest) ([configuration](configuration.md)).

## 6. Close

The planner runs `wuwei retro` and `wuwei close --check retro`, writes the report with
`wuwei report` (shipped, merged, parked with its reason and [unmeasured](concepts.md#unmeasured) sources) and ends with
`wuwei close`. Its `## Steward runs` section counts today's [steward](concepts.md#steward) runs by trigger and
names the setting that drives the sweep, `watch.sweep_seconds`. `close` refuses while an obligation is open and names it; the Stop hook
holds the session until close is clean. For each open item close asks: carry it to
tomorrow (recommended), park it, or keep working, and records the answer with
`wuwei plan carry ITEM` or `wuwei plan park ITEM`. Check the day at any time with
`bin/wuwei status --line`.

Anything not on this page is recovery, not daily use: see [recovery](recovery.md).
