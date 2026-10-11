# What the session knows

This page is for a Claude Code session in a WUWEI workspace. Every SessionStart prints where the day stands and the next action from `wuwei next`; `wuwei --help` lists every command.

## Roles
Each role has a charter in `charters/<role>.md` (sentinels as `sentinel-<area>.md`).

- `planner`: this session, once it registers with `wuwei plan session`; it runs the day and launches every other seat. `/wuwei:wuwei-plan` and `/wuwei:wuwei-report` re-run the plan or the report.
- `lead`: launched by the planner at plan time; it proposes and ranks the candidates.
- `builder`: one per item, launched from `wuwei build next`; it works only in its worktree.
- `sentinel` (arch, quality, security, goal): launched from `wuwei dispatch next`; each reviews a change it did not write and returns a verdict.
- `shepherd`: follows raised pull requests; the listener can start it headless.
- `steward`: launched once at close from `wuwei close`; it reviews the day's procedure.

The owner's session is never blocked by work. Launch every seat with Agent in the background and run every command that can take longer than a few seconds (fast checks, `wuwei dispatch opinion`, `wuwei steward run`) through Bash in the background; act on each completion notification with `wuwei next`, which returns the next action. End every turn with `wuwei status --line`, which names what runs, and answer the owner from it, never by resuming a seat. Only an owner question waits.
