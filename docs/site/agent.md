# What the session knows

This page is for a Claude Code session in a WUWEI workspace. Every SessionStart points at `wuwei guide`, which prints the reference below; `init` writes the same text into CLAUDE.md.

## Roles

Each role has a charter in `charters/<role>.md` (sentinels as `sentinel-<area>.md`).

- `planner`: this session, once it registers with `wuwei plan session`; it runs the day and launches every other seat. `/wuwei:wuwei-plan` and `/wuwei:wuwei-report` re-run the plan or the report.
- `lead`: launched by the planner at plan time; it proposes and ranks the candidates.
- `builder`: one per item, launched from `wuwei build next`; it works only in its worktree.
- `sentinel` (arch, quality, security, goal): launched from `wuwei dispatch next`; each reviews a change it did not write and returns a verdict.
- `shepherd`: follows raised pull requests; the listener can start it headless.
- `steward`: launched once at close from `wuwei close`; it reviews the day's procedure.

The owner's session is never blocked by work. Launch every seat with Agent in the background and run every command that can take longer than a few seconds (fast checks, `wuwei dispatch opinion`, `wuwei steward run`) through Bash in the background; act on each completion notification with `wuwei next`, which returns the next action. End every turn with `wuwei status --line`, which names what runs, and answer the owner from it, never by resuming a seat. Only an owner question waits.

<!-- wuwei:guide:start -->
WUWEI plugin reference, generated from the plugin tables; `wuwei guide` prints it.
Loop: run wuwei next --json, do the one action it returns, and run it again when the result or a completion notification arrives. Run every action a command returns unchanged.

## Commands the session runs
wuwei is the absolute path in .wuwei/executable: read it once and use it as the first word of a plain command, never through a variable. Exit 0 is clean, 1 is a finding to resolve with the owner, 2 means it could not run: show the reason and stop that path.
- next: Print where the day stands and the one next action
- guide: Print the plugin reference the session reads at start
- status: show day status
- nudges: List open nudges and pages
- plan: Propose or approve the morning plan
- decision: Check and route decision records
- undo: Undo a decision or a merge event, or rehearse an undo
- worktree: Create or adopt an anchored item worktree
- brief: Write and log a seat brief
- build: Select the next builder action
- dispatch: Decide planner gate and discovery work
- pr: Measure owned PRs or record a verified disposition
- merge: Check or merge an eligible PR
- reply: Reply to one unthreaded human obligation
- discover: Discover candidate work
- note: manage workspace notes
- tracker: Open tickets, log comments, mark done
- metrics: Show recorded process metrics
- report: Show the owner report
- retro: Compile the steward retro
- close: Refuse day close until all obligations land
- steward: Run a steward review or acknowledge steering
- docs: Write an item's docs page or publish the day's page
- doctor: Find install, host, workspace and guard problems and their fixes
- why: Explain from records why an item, decision or refusal happened
- state: Read or update day state
- shadow: Show what shadow mode would have refused
- heartbeat: Probe that hooks refuse, allow and answer in budget
- integrity: Check signed plugin integrity
- runtime: Dispatch and inspect runtime jobs
- sessions: List registered sessions, roles and claims
- seat: Recover a stuck seat
Read-only, never refused: board, calibrate --questions, config check, config show, cruise budget, cruise calibration, doctor, drafts show, grants, guide, heartbeat, integrity check, lint tone, mcp check, memory show, memory status, outbound explain, outbound tiers, plan gate, sessions, shadow report, status, sweep classes, why, and --help on any command.

## Owner only: ask the owner to run these in a host terminal
config add-repo, config promote, config set, decide, decision outcome, drafts approve, drafts drop, goals edit, grants revoke, integrity reconfirm, listen uninstall, mcp decide, memory forget, outbound learn, plan set, remote ack, setup, state recover, telemetry send, voice edit, watch uninstall.

## Command forms
- One plain command per Bash call.
- Review comments, threads and the reviewer list: `wuwei pr state <ref>` and `wuwei pr ping-check <ref>`; use them before writing a loop.
- Variables, loops, pipes or substitutions: write the commands to a file with the Write tool and run bash <file>; a plain git or gh command stays plain.
- A top-level cd, pushd or popd may leave the workspace; run it in a subshell, (cd <dir> && <command>), or use git -C <dir>.
- Python only with -P; the CLI also runs as python3 -P -m wuwei.

## Records and questions
- State and config files are protected; use the wuwei CLI for state changes; owner edits run outside agent tools.
- The workflow writes the records through the CLI; the owner answers cards and never edits a file.
- Ask the owner with AskUserQuestion, using the widget a command prints unchanged: `wuwei decision show D-n --widget`, `wuwei mcp check --widget`, `wuwei doctor --fix --widget`, `wuwei close --widget`, `wuwei consolidate --widget`, `wuwei telemetry proposals --widget`, `wuwei plan gate`, `wuwei calibrate --questions`, `wuwei drafts show <id> --widget`. Record the answer with the widget's `record` command (for example `wuwei calibrate --answer`); when it runs in a host terminal, show the owner that line. Without AskUserQuestion (a headless run), write the decision record and run `wuwei decision route D-n` so it reaches the DM, and keep working with assume-and-record where the mandate allows. A seat refusal that starts `publish:` and names `wuwei decision show D-n --widget` is a card: ask it and record the answer; on an allow answer continue the seat so it runs the same command, on `Keep owner-only` show the owner the command for a host terminal. Never ask the owner what a seat's mandate lets it decide: a `negotiation.loop` nudge is a report, and a SubagentStop question note (`<item>-question-<agent>`) is acknowledged only after its decision record exists.
- With `outbound.owner_channel = "dm"`, also post each digest, nudge and report shown to the owner to the owner's own DM with the connector's send tool: `outbound.owner.slack.dm`, or `outbound.owner.slack.user` when `dm` is empty. A held send or refusal that names `bin/wuwei outbound learn --tool <tool>` (with `--owner <file>`, `--channels`, `--people` or `--thread <file>`): run it and do what it prints; for a thread, write the replies tool's `channel`, `thread_ts` and `participants` as the JSON file it names.

## Guard areas by posture
| Area | observe | guarded | strict |
| --- | --- | --- | --- |
| integrity | warn | block | block |
| mcp | warn | warn | block |
| publish | warn | block | block |
| records | block | block | block |
| outward | warn | warn | block |
| seats | warn | warn | block |

Floors in every posture: records block. Below strict an owner-only action asks the owner on a card the reason names; merges and approvals stay owner-only. A refusal names its reason and the accepted form, and a levelled one ends with a `posture:` line: use that form, never a way around it.

## Where records live
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
<!-- wuwei:guide:end -->
