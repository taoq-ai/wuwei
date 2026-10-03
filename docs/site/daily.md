---
layout: default
---

# The daily path

[Home](index.html)

One path for a solo owner through one day: install, configure, plan, build and review,
decide, close. Every command here is daily use. Anything else is in
[recovery](recovery.html). `bin/wuwei` below is the executable in the plugin
directory; the planner uses the one recorded in `.wuwei/executable`. Each Claude Code
session in the workspace gets the same flow as [what the session knows](agent.html).

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

Then set up the workspace in a [host terminal](concepts.html#host-terminal):

```sh
../wuwei-plugin/bin/wuwei setup --shadow
```

`setup` runs `init` when there is no workspace; `init` ends with `plugin integrity: clean`
for an intact signed release. A development checkout needs one host confirmation first; see
[recovery](recovery.html).

Then run `bin/wuwei doctor`. It checks the install, host, workspace, [gates](concepts.html#gate), day and guards in
one pass and prints the fix for anything that is not ok; `bin/wuwei doctor --fix` applies the
deterministic fixes after one confirmation. When something fails on the first day, see
[troubleshooting](recovery.html#troubleshooting).

## 2. Configure

`setup` does the configuration in one pass. It finds the git repositories in the project
directory (or under `--repos <dir>`), reads each one's GitHub name from its `origin` remote,
its default branch through `gh` when `gh` is signed in, and its commit identity from its git
config. It lists the host facts (platform, `claude`, `gh` and `ziran` on PATH, free memory),
then calibrates and interviews:

- the calibration is what `bin/wuwei calibrate` does: it reads each checkout and writes
  `.wuwei/days/<date>/calibration.md` with its checks, CI check names, conventions and deploy
  signals, each with the file and line it came from
  ([calibration](configuration.html#calibration));
- the owner interview is what `bin/wuwei calibrate --interview` asks: how much merge autonomy
  you want, your gate floor, quiet and working hours, how decisions reach you, words to avoid,
  which commands you run by hand, and which tracker, chat and review bot you use
  ([owner interview](configuration.html#owner-interview)); `config check` then names each
  credential variable those adapters need until you set it in `.wuwei/env`;
- your identity: with `gh` signed in, `owner.handles` gains your code-host login,
  `shepherd.lead_login` defaults to it, and `shepherd.authors` maps your repositories' git
  emails to it and each bot author seen on the last 50 merged pull requests to its `[bot]`
  login. Values you already set are kept.

It shows the `[[repos]]` tables, the calibration and the answers as one `config.toml` diff,
applies it after you type its [digest](concepts.html#digest) (the `bin/wuwei config promote` path), runs
applies it after you answer y (the `bin/wuwei config promote` path), runs
`bin/wuwei config check` and `bin/wuwei mcp check`, and prints what is still owed with the
exact command for each: a repository it could not measure, a credential variable,
`owner.name`, `bin/wuwei promote` for the charter proposals, an MCP decision. Run it again
any time; with nothing new it proposes nothing. For a solo owner then run
`bin/wuwei config set shepherd.min_reviewers 0`. You do not write goals by hand: the lead
proposes them at the first morning plan and the planner records the ones you approve. You
can change them later with
`bin/wuwei goals edit`. [Configuration](configuration.html) lists every key.

A clean first run for one repository looks like this, with the interview answered `1` each
time (cut where it shows `...`):

```text
Created <project>/.wuwei
{"statusLine": {"type": "command", "command": "<plugin>/bin/wuwei status --line"}}
Status line: put the "statusLine" key above in .claude/settings.json (this project) or ~/.claude/settings.json (every project).
Recommended publishing layout (design 4.5, 9.1):
  ...
Verify with: wuwei config check
plugin integrity: clean
Host: <platform>
claude: on PATH
gh: on PATH
ziran: missing
code host auth: set
code host login: <login>
free memory: <n> MiB

Merges: Who merges pull requests in acme/widget?
  1. Owner merges: You merge every pull request yourself.
  ...
> 1
...
--- config.toml
+++ config.toml (proposed)
...
+[[repos]]
+name = "acme/widget"
+path = "widget"
+default_branch = "main"
...
Interview answers:
- merge (acme/widget): Owner merges -> repos.0.merge.auto = false
...
- posture: Observe -> security.posture = "observe"
- tracker: None -> adapters.tracker = "none"
- chat: None -> adapters.chat = "none"
- review_bot: None -> adapters.review_bot = "none"
Approved calibration for .wuwei/calibration.json:
...
Review the setup above. To apply it, type:
<digest>
> <digest>
Applied the setup and recorded .wuwei/calibration.json
Credentials:
  ...
Owner:
  owner.name: not set; the outward lint refuses every outward message except replies in the owner DM
Posture: observe (from security.posture)
  ...
Host protections:
  ...
Seat credentials:
  ...
Still owed:
  bin/wuwei config set owner.name '"<your name>"'
  bin/wuwei promote
Next: /wuwei plan
```

It worked when you see `Applied the setup and recorded .wuwei/calibration.json` and
`Next: /wuwei plan`. On day one `owner.name` and `bin/wuwei promote` under `Still owed:` are
normal, and exit 1 with `missing` rows under `Host protections:` means the setup was applied
and the branch protections are still to set. It did not work when the `Applied` line is
missing (nothing was written; the reason is on the last line) or when `Still owed:` lists
`bin/wuwei config add-repo` (setup could not read a repository); see
[troubleshooting](recovery.html#troubleshooting).

`--shadow` starts a first week in the observe posture (on an existing workspace it proposes
`security.posture = "observe"`), as does the `Observe` answer in the interview. The guards
then record what they would refuse and let the call through; records and owner-only actions
(deploys, merges, approvals, messages that wait for your approval) still refuse. Read
`bin/wuwei shadow report` or the `## Shadow` section of the day report. When the [nudge](concepts.html#nudge) comes
after `guards.shadow_days`, run `bin/wuwei config set security.posture '"guarded"'` in a host
terminal, or keep watching with `bin/wuwei config set guards.shadow_days 14`. See [security posture](concepts.html#security-posture).

## 3. Plan and the morning gate

Run `/wuwei plan` in Claude Code. The planner registers its session
(`wuwei plan session`), sweeps live work, asks the lead for candidates, orders them with
`wuwei rank` and writes the proposal with `wuwei plan propose`. It then asks you one
`Morning gate` question per decision: goals, queue, [seat](concepts.html#seat) policy, [CAP](concepts.html#cap),
[envelope](concepts.html#envelope) and [carry-over](concepts.html#carry). Nothing is dispatched before your answers. While `memory/goals.md` has no goals,
the lead proposes them, `plan.md` shows them as provisional and the goals question shows the
blocks. On approval the planner records them with
`wuwei goals edit --file .wuwei/days/<date>/goals.md`; under the strict posture the hook
refuses that call and prints the command for a host terminal. It then records the gate with
`wuwei plan approve --items <ids> --goals-confirmed`.

The planner asks the morning gate as question cards. After you approve, it records the goals
and the plan, and you can run the last two commands yourself. A clean first plan with one
goal and one item looks like this:

```text
$ wuwei plan propose .wuwei/days/<date>/lead.json
<project>/.wuwei/days/<date>/plan.md
$ wuwei goals edit --file .wuwei/days/<date>/goals.md
goals: 1 goal saved (G-1)
$ wuwei plan approve --items DIV-1 --goals-confirmed
$ bin/wuwei status --line
WUWEI pages 0 | nudges 0 | observe | watch off | planned 1/1 | meeting unmeasured
$ bin/wuwei next
dispatch: 1 planned item(s) queued, 0 of CAP 1 building; create the worktree for DIV-1, then ...
```

It worked when `goals edit` says `saved`, the status line shows `planned 1/1` and
`bin/wuwei next` names the first item. `plan approve` prints nothing when it succeeds, and
`meeting unmeasured` only means no calendar is set up. It did not work when the status line
has no `planned` count after you approved, or when a command exits 1 or 2 with a reason; see
[troubleshooting](recovery.html#troubleshooting).

## 4. Through the day

Watch the status line and `bin/wuwei nudges`. The status line counts items per phase, for
example `implement 1/1`, and later `merged 1/1`. The planner runs one loop per item and
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
   `continue` action with the FIX verdict files as feedback. The planner runs the build
   loop again until `done`, which moves the item to `delta`.
5. [Delta](concepts.html#delta): `dispatch next` returns `gates` for the roles that said FIX, and `seats` holds a
   `continue` action per seat with `resume` (the seat's agent ID) and a `receive` call
   with `--round delta`. After the delta verdicts it returns `raise` with review notes,
   or `escalate`.
6. Pull request: `wuwei pr raise <owner/repo> --base main --title <title> --body-file
   <file> --item <item>` opens the PR and moves the item to `raised`. `wuwei pr state`
   reads the host; `wuwei pr act <ref>` returns the next PR action, including a post-PR fix
   round. When the host reports the PR merged, the item is `merged`, whatever round it
   was in.

Phases move by themselves: `planned`, `implement`, `gate`, `fix`, `delta`, `raised`,
`merged`. You never move one by hand on this path.

PR changes reach the planner without you. Every change on a raised or claimed PR is one
`pr.changed` event with a summary, for example
`PR owner/repo#12: 2 new review comments by alice on cli/x.py; check test (3.11) failed`.
The Stop hook message and `bin/wuwei nudges` list that summary first, and the status line
shows `prs <n> changed` until the planner has seen the wake. An idle interactive planner
learns of a change at its next turn (its next Stop or session start): Claude Code cannot
put input into an idle session. The listener covers the gap: it sends the summary to your
DM and, with `shepherd.autostart = true`, starts a headless [shepherd](concepts.html#shepherd) seat for the
mechanical PR actions ([remote](remote.html), section 5). For CI events in your own
session, the Claude Code desktop PR monitor is the complement.

## 5. Owner decisions

Some commands are yours alone and run in a host terminal, never through an agent:
`bin/wuwei decide D-<n> <option>` for any decision, MCP registry findings included (`proceed`
also re-runs the check), and `bin/wuwei drafts approve` or `drafts drop`. Under `observe` and
`guarded` the planner asks you a decision in the session and records your answer with the
same command; under `strict`, and for credentials, you run it in a host terminal and answer y. Nudges and the report name each pending decision.

`bin/wuwei decision show D-<n>` prints a decision at your `owner.verbosity` level: by default
the question, each option with its score, and the recommendation with one reason.
`bin/wuwei decision show D-<n> --full` prints every field.

To answer from your phone, run the planner session with Claude Code Remote Control
(`claude --remote-control`, or `/remote-control` inside the session) and turn on
"Push when actions required" in `/config`. Each decision question then reaches the Claude
mobile app and stays open until you answer. A phone answer is not yet your outcome: the planner
records it with `bin/wuwei decide`, or you run it in a host terminal. To command the workspace and
answer decisions from Slack as well, follow [remote operation](remote.html). A decision
answered in the Slack DM is recorded as evidence, and `status --line` counts it as
`phone answers 1` until you record it with `bin/wuwei decide`.

Seats do not ask what their [mandate](concepts.html#mandate) lets them decide. You see two more things here. An item
that goes back and forth shows as `loops N` on the status line and a `negotiation.loop`
nudge (a [page](concepts.html#page) when its goal date has passed), with the counts and the last two exchanges in
your DM when the listener runs. An external confirmation a seat routed with `--external`
waits `decisions.wait_hours` weekday hours for your answer; then the sweep confirms the
recommendation on a two-way door or [parks](concepts.html#park) the item for your `decision outcome`.
recommendation on a two-way door or parks the item for your `decide`.

### How you answer

In the Claude Code session (desktop app, terminal or IDE alike) each owner question shows up
as a question card: tap an option, the recommended one first. The planner records your pick
with the command printed beside the card. When that command needs your confirmation in a
host terminal, the planner shows you the line to run.

Away from the session, the same question reaches your phone through Remote Control, or as a
DM from the listener when the planner runs headless.

Use the host terminal for what a hook sends there: today the owner commands listed at the top
of this section, and under `strict` posture everything owner-only.

## Long sessions

The planner session is the one long-lived context of the day; seats are fresh per item.
Quality can drift as that context grows, so WUWEI measures it and lets you rotate the
planner on a schedule.

- Measured: `bin/wuwei report` has a `## Quality by band` section with gates, FIX rate,
  fix rounds, verdict lint rejections and your interventions per hour band (morning
  05-11, midday 11-14, afternoon 14-18, evening 18-05, in `owner.timezone`) and per
  planner session-age band (turns since it started today, or compacted). `bin/wuwei retro`
  compares the last 7 days, names the worst band when its FIX rate leads every other band
  by `metrics.band_margin`, and proposes a planner charter line for you to promote or
  reject.
- Rotation: set `sessions.rotate_after` (`turns`, `compactions` or a `clock` time; off by
  default). At the first turn past the limit with no running seat and no unanswered owner
  decision, the Stop hook tells the planner to end the session once. Start a fresh Claude
  Code session in the workspace and run
  `wuwei plan session "$WUWEI_SESSION_ID" --take-over` there. `bin/wuwei sessions` shows
  the old session as `rotated`, and the events record `session.rotated`. Nothing is lost:
  the day lives in `.wuwei/`, not in the transcript.
- Re-anchoring: every SessionStart payload, after a compaction or a rotation too, opens
  with the orientation block: what WUWEI is, the posture and the next step from
  `bin/wuwei next`. `Active constraints:` follows with the day's goals, the approved plan,
  open decisions and the briefs of running seats. The full day state is no longer pasted
  into the session; it is one command away, `bin/wuwei state get`.

Set them with `bin/wuwei config set` in a host terminal, for example
`bin/wuwei config set owner.timezone '"Europe/Lisbon"'`,
`bin/wuwei config set metrics.band_margin 0.3` or
`bin/wuwei config set sessions.rotate_after.turns 200`. Each shows a diff and applies it
after its digest ([configuration](configuration.html)).

## 6. Close

The planner runs `wuwei retro` and `wuwei close --check retro`, writes the report with
`wuwei report` (shipped, merged, pending decisions and [unmeasured](concepts.html#unmeasured) sources) and ends with
`wuwei close`. `close` refuses while an obligation is open and names it; the Stop hook
holds the session until close is clean. Check the day at any time with
`bin/wuwei status --line`.

Inside a session, ask Claude for the board, or call the plugin's `wuwei_board` tool. It
shows items by phase with gate verdicts, owned PRs and what they wait on, pending decisions
and pages and nudges as tables, and renders the cockpit inline where the host renders MCP
Apps. It is read-only: answering a decision or approving a draft stays a CLI owner action.

Anything not on this page is recovery, not daily use: see [recovery](recovery.html).
