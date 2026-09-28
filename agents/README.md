# Generated agents

Run `bin/wuwei agents build` after changing a charter or `allowlist.json`. Run
`bin/wuwei agents check` to detect drift. CI runs the same check as a pytest
golden test. Agent files are generated; edit their sources instead.

| Role | Tool rationale |
|---|---|
| planner | Reads plans and evidence, writes the day plan, runs the CLI, and dispatches seats with `Agent`. |
| lead | Reads sources and writes ranked discovery; `Bash` reaches configured CLI adapters. No dispatch. |
| builder | Reads and edits the assigned worktree, runs tests and the CLI. No network or dispatch tools. |
| sentinel-arch | Reads and probes changes, then writes its architecture verdict. No edit or dispatch tool. |
| sentinel-quality | Reads and probes changes, then writes its quality verdict. No edit or dispatch tool. |
| sentinel-security | Reads and probes changes, invokes the configured scanner through the CLI, then writes its security verdict. No edit or dispatch tool. |
| sentinel-goal | Reads and probes documents, then writes its goal verdict. No edit or dispatch tool. |
| shepherd | Reads PR evidence, runs the CLI and configured adapters, and writes PR artifacts. No `Agent` tool. |
| steward | Reads day evidence, runs the CLI, and writes steering notes, retro and proposals. No dispatch. |

`Read`, `Glob` and `Grep` support inspection. `Bash` is necessary for the CLI,
tests and configured adapters. Workspace guards and seat briefs constrain actions
and write paths; the tool list alone does not constrain `Bash` or `Write` paths.
