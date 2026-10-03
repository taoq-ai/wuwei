# What the session knows

This page is for a Claude Code session that starts in a WUWEI workspace with no prior
context. Every SessionStart in the workspace points here.

## What WUWEI is

WUWEI runs a coding day the way a careful engineering team works. The planner session
ranks the work with the owner, seats build and review each change in their own worktree,
and merges follow a policy. The day lives in `.wuwei/`, not in the transcript, so any
session can pick it up.

The first rule: run `wuwei next` and do the step it names. It reads the day's files and
prints one line, `<state>: <step> Run: <command>` (`--json` gives `state`, `step` and
`command`). `wuwei` means the absolute path in `.wuwei/executable`: read it once with
the Read tool and use it as the first word of a plain command, never through a variable or
a command substitution; or `python3 -P -m wuwei`. Never run Python without `-P`.

## Roles

Each role has a charter in `charters/<role>.md` (sentinels as `sentinel-<area>.md`).

- `planner`: this session, once it registers with `/wuwei:wuwei-plan`. It runs the day and
  launches every other seat.
- `lead`: launched by the planner at plan time; it proposes and ranks the candidates.
- `builder`: one per item, launched from `wuwei build next`; it works only in its worktree.
- `sentinel` (arch, quality, security, goal): launched from `wuwei dispatch next`;
  each reviews a change it did not write and returns a verdict.
- `shepherd`: follows raised pull requests; the listener can start it headless.
- `steward`: launched once at close from `wuwei close`; it reviews the day's procedure.

## The day in order

1. Setup, by the owner in a host terminal: `bin/wuwei setup --shadow` creates the
   workspace, finds the repositories, calibrates them and asks the interview.
2. Plan: `/wuwei:wuwei-plan` registers the planner (`wuwei plan session`), runs
   `wuwei mcp check`, launches the lead, orders its JSON with `wuwei rank` and writes
   `days/<date>/plan.md` with `wuwei plan propose`.
3. Morning gate: one AskUserQuestion per decision, each starting with `Morning gate`.
   Only on the owner's answers, `wuwei plan approve --items <ids> --goals-confirmed`.
4. Build, per item: `wuwei worktree add <item>`, `wuwei brief builder <item> <name>
   --worktree <path> --file -`, then `wuwei build next <item>` until it returns `done`.
5. Gates: `wuwei dispatch next <item>` names the gate briefs to write and the seats to
   launch; after each seat stops, run the `wuwei dispatch receive` call it gave you.
6. Pull request: `wuwei pr raise`, then `wuwei pr act <ref>` for each next action;
   `wuwei merge check` shows whether the merge policy allows it.
7. Close: `/wuwei:wuwei-report` runs `wuwei close`, `wuwei retro`, `wuwei promote`,
   `wuwei report` and `wuwei close` again until it exits 0.

Run every action a command returns unchanged. Exit 0 is clean, 1 is a finding to resolve
with the owner, 2 means it could not run: show the reason and stop that path.

## What the hooks refuse

- Records under `.wuwei/` (state, events, config, verdicts, decisions) change only through
  the CLI, never through Edit, Write or a shell redirect. Reading them (Read, Grep, `cat`,
  `grep`, `jq`, `ls`) is always allowed.
- Item worktrees come only from `wuwei worktree add`.
- A seat launches only from a logged brief, with the returned prompt unchanged.
- No deploys, no merge outside `wuwei merge`, no pull request approvals.
- Python only with `-P`.

A refusal names its reason and ends with a `posture:` line. Use the accepted form it
names; never look for a way around it.

## Where each record lives

Paths are under `.wuwei/`; `<date>` is today.

| Record | Written by |
| --- | --- |
| `config.toml` | `setup`, `config set`, `config add-repo` (owner) |
| `days/<date>/state.json`, `events.jsonl` | the CLI |
| `days/<date>/plan.md` | `plan propose` |
| `days/<date>/briefs/` | `brief` |
| gate verdicts, in `state.json` | `dispatch receive` |
| `days/<date>/decisions/` | `decision` |
| `days/<date>/report.md` | `report` |
| `days/<date>/retro/` | `retro` |
| `memory/` | `note`, `promote` |

## How the owner answers

Ask with AskUserQuestion in this session. The owner can also answer from the phone
through Remote Control or the Slack DM. Some commands are the owner's alone and run in a
host terminal in every posture: `decide`, `decision outcome`, `drafts approve`, `mcp decide`,
`config set` and `setup`. Name the exact command; never ask the owner to edit a file.

## First day

The owner runs `bin/wuwei setup --shadow` in a host terminal, then you run
`/wuwei:wuwei-plan`. On the first day the plan skill also asks the calibration questions
after the morning gate. The owner's guide to the same day is the [daily path](daily.md).
