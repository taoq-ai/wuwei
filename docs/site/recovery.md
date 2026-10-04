# Recovery

The [daily path](daily.md) needs none of these commands. Each one here is recovery, not
daily use: reach for it when evidence and state disagree, a seat is lost, or the
installation changed. Before a release, the [release rehearsal](rehearsal.md) drives a
real day; its failures point back here.

## Troubleshooting

Start with `bin/wuwei doctor`: it names each problem with its fix, and
`bin/wuwei doctor --fix` applies the deterministic ones after one confirmation. See
[doctor](reference.md#doctor). The entries below are first-day recovery: what a first run
on 0.11.0 showed, what changed in 0.12.0, and the command for each.

### Every tool call is refused with plugin integrity

The refusal names a file under `.in_use/`. Claude Code writes one marker there per running
Claude process, and 0.11.0 counted each marker as tampering. From 0.12.0 the check skips
files named by a process id directly in the install root's `.in_use/`; any other name, a
directory, a symlink or a deeper `.in_use` is still a finding. Install the new release and
run `bin/wuwei init --upgrade`. If it still refuses, `bin/wuwei integrity check` names the
files. Doctor's `in_use` row counts the markers.

### The MCP gate blocks, or names a server unmeasured

`bin/wuwei mcp check` reports each server on its own. A project server you never approved is
`not attached (unapproved)` and is never started; an `unpinned launcher` is not run; an
unreachable or slow server is unmeasured by name. Under `guarded` only a critical finding or
a check that could not run blocks, and an unmeasured server is a nudge. Accept one with
`bin/wuwei mcp decide proceed-unmeasured <server>`, or give a slow one more time with
`scanner.mcp.timeout_seconds` ([MCP registry checks](configuration.md#mcp-registry-checks-s3)).

### config.toml does not load

Every tool is refused with the parse error, except `ToolSearch` and a `Read`, `Grep` or
`Glob` of `.wuwei/config.toml` or its charters, so the session can still show the line. Run
`bin/wuwei config check`: it names the key, the line and the fix.

### repos = [] next to [[repos]] tables

The load error ends with "repos is assigned on line N; delete that line before using
[[repos]] tables". `bin/wuwei init --upgrade` removes the line, and `doctor --fix` offers it.
The template no longer ships `repos = []`.

### Changing one value

Do not edit `config.toml` by hand for a single value. `bin/wuwei config set <key> <value>`
and `bin/wuwei config add-repo --name <owner/repo> --path <dir> --branch <branch>` show a
diff and apply it after its digest. Edit the file yourself only for a table or a value that
spans lines.

### fast_checks stays empty after promote

0.11.0 left an explicit `fast_checks = []` alone. From 0.12.0 a one-line empty list is
filled by `bin/wuwei config promote`, like the deploy lists.

### A test suite is proposed as a fast check

A test runner is CI only unless measured. `setup` offers to run it once and proposes it only
when it is fast enough; later, `bin/wuwei calibrate --measure` times each one
against `calibrate.fast_check_seconds` and proposes only the fast ones
([calibration](configuration.md#calibration)).

### Branch protection reads as unmeasured

A 404 on the classic endpoint means the branch is unprotected or you lack admin.
`bin/wuwei config check` now prints `classic protection: none visible (404: unprotected or
no admin)` and reads the rulesets as well.

### A read-only shell command was refused

From 0.12.0 a `for` loop, `$(...)` or `git symbolic-ref` that only reads is not refused, and
outside a workspace every hook allows. If a refusal remains, `bin/wuwei why last refusal`
prints the guard, the rule, the command and the fix. Under `observe`,
`bin/wuwei shadow report` lists what would have been refused.

## state transition

`bin/wuwei state transition <item> <phase>` moves an item's phase by hand. It is recovery,
not daily use: on the daily path `build next`, `dispatch next`, `pr raise` and an observed
merge move every phase. Use it only when the recorded phase disagrees with the evidence,
for example to resume a parked item. It accepts only the moves in the
[item phase order](reference.md#item-phase-order).

## runtime dispatch

`bin/wuwei runtime dispatch <role> <brief> <worktree>` returns launch instructions for a
logged brief. The planner uses it for lead and shepherd seats. By hand it is recovery,
not daily use: relaunch a lost sentinel from a fresh brief, or launch a Codex seat.

## runtime continue

`bin/wuwei runtime continue <job-json> <feedback>` returns the same seat's instructions
with feedback. It is recovery, not daily use: return a rejected or unmeasured verdict to
its seat, or continue a Codex sentinel with the job `runtime dispatch` printed. Claude
delta continuations come from the `seats` list of `dispatch next`.

## integrity reconfirm

`bin/wuwei integrity reconfirm` records your confirmation of a development
checkout or a changed installation. It is recovery, not daily use: an intact signed
release needs no reconfirmation. Run it in a host terminal and answer y
after reviewing the contents. See the [index](index.md#development-checkouts) for what
it records.

## Other recovery

`bin/wuwei state recover` restores an unreadable `state.json` from its snapshot; see
[state recovery](reference.md#state-recovery). Owner-only commands are listed under
[host terminal actions](reference.md#host-terminal-actions).

### An MCP finding on a server you installed yourself

Under `guarded` the day proceeds and the finding stays on the board until
`bin/wuwei mcp decide D-<n> proceed` (or `defer`). Under `strict` seats wait for that
command; the decision holds the findings table. A `tool_redirect`
hit on a description that points to a sibling tool of the same server is a known
scanner heuristic issue, https://github.com/taoq-ai/ziran/issues/447. WUWEI reports
the severity the scanner gives.

## Seat launch contract

Write and log a brief with `wuwei brief <role> <item> <name> --body TEXT` (or
`--file PATH`, where `--file -` reads stdin), then obtain launch
instructions with `wuwei runtime dispatch <role> <brief> <worktree>`. With the Claude
runtime, pass the returned `prompt` unchanged to Agent and use its `agent_type`
(`wuwei:<role>`) as Agent's `subagent_type`. Supply an Agent description and launch
from the workspace root, which is the hook payload's `cwd`.

The exact first line is `WUWEI brief: <relative brief path>`. The path is relative
to the workspace root, for example `.wuwei/days/2026-09-29/briefs/builder-1.md`,
not relative to the item's worktree. Do not prepend instructions to the prompt.
The guard still requires the logged, unchanged brief and matching role, fresh
evidence and available capacity; a missing first line is refused with the required format.

The core function `wuwei.brief.launch_prompt` generates these instructions for all
Claude roles, including the actions `build next` and `dispatch next` return.
`wuwei runtime continue <job-json> <feedback>` preserves the reference
and includes feedback for the same seat. It does not authorize a second launch
with a consumed brief. `wuwei steward run --trigger close` returns the same contract
inside `steward_launch`, through the configured runtime adapter.
