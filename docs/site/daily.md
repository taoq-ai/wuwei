---
layout: default
---

# The daily path

[Home](index.html)

One path for a solo owner through one day: install, configure, plan, build and review,
decide, close. Every command on this page is daily use. Anything else is on the
[recovery](recovery.html) page. `bin/wuwei` below is the executable in the plugin
directory; the planner uses the one recorded in `.wuwei/executable`.

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

Then initialize the workspace:

```sh
../wuwei-plugin/bin/wuwei init .
```

`init` ends with `plugin integrity: clean` for an intact signed release. A development
checkout needs one host confirmation first; see [recovery](recovery.html).

## 2. Configure

Edit `.wuwei/config.toml`: your repositories (`path`, `default_branch`, `fast_checks`) and
adapters. For a solo owner set `[shepherd] min_reviewers = 0` and `[adapters] chat = "none"`.
Check the file with `bin/wuwei config check`. Edit your goals in a host terminal with
`bin/wuwei goals edit`. [Configuration](configuration.html) lists every key.

Then calibrate: `bin/wuwei calibrate` reads each configured checkout and writes
`.wuwei/days/<date>/calibration.md` with its checks, CI check names, conventions and deploy
signals, each with the file and line it came from. It changes nothing else. Read the report,
then run `bin/wuwei config promote` in a host terminal to apply the proposed `config.toml`
additions, and `bin/wuwei promote` to land the proposed charter blocks. See
[calibration](configuration.html#calibration).

Then answer the owner interview once: `bin/wuwei calibrate --interview` in a host terminal
asks how much merge autonomy you want, your gate floor, quiet and working hours, how
decisions reach you, words to avoid and which commands you run by hand. Promote the answers
the same way. If you skip it, `/wuwei plan` asks the same questions on the first day. See
[owner interview](configuration.html#owner-interview).

## 3. Plan and the morning gate

Run `/wuwei plan` in Claude Code. The planner registers its session
(`wuwei plan session`), sweeps live work, asks the lead for candidates, orders them with
`wuwei rank` and writes the proposal with `wuwei plan propose`. It then asks you one
`Morning gate` question per decision: goals, queue, seat policy, CAP, envelope and
carry-over. Nothing is dispatched before your answers. On approval it records them with
`wuwei plan approve --items <ids> --goals-confirmed`.

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
   `wuwei dispatch receive <item> <role> <seat>` call to run after the seat stops.
4. Fix round: when a gate says FIX, `dispatch next` returns `fix` with `command`
   (`wuwei build next <item>`). The item is already in `fix` and the stopped builder has a
   `continue` action with the FIX verdict files as feedback. The planner runs the build
   loop again until `done`, which moves the item to `delta`.
5. Delta: `dispatch next` returns `gates` for the roles that said FIX, and `seats` holds a
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

## 5. Owner decisions

Some commands are yours alone and run in a host terminal, never through an agent:
`bin/wuwei decision outcome <id> <option>`, `bin/wuwei drafts approve` or `drafts drop`,
and `bin/wuwei mcp decide`. Nudges and the report name each pending decision.

To answer from your phone, run the planner session with Claude Code Remote Control
(`claude --remote-control`, or `/remote-control` inside the session) and turn on
"Push when actions required" in `/config`. Each decision question then reaches the Claude
mobile app and stays open until you answer. A phone answer is not yet your outcome: run
`bin/wuwei decision outcome` in a host terminal to record it. To command the workspace and
answer decisions from Slack as well, follow [remote operation](remote.html).

## 6. Close

The planner runs `wuwei retro` and `wuwei close --check retro`, writes the report with
`wuwei report` (shipped, merged, pending decisions and unmeasured sources) and ends with
`wuwei close`. `close` refuses while an obligation is open and names it; the Stop hook
holds the session until close is clean. Check the day at any time with
`bin/wuwei status --line`.

Inside a session, ask Claude for the board, or call the plugin's `wuwei_board` tool. It
shows items by phase with gate verdicts, owned PRs and what they wait on, pending decisions
and pages and nudges as tables, and renders the cockpit inline where the host renders MCP
Apps. It is read-only: answering a decision or approving a draft stays a CLI owner action.

Anything not on this page is recovery, not daily use: see [recovery](recovery.html).
