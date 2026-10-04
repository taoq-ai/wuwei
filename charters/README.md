# Charters and generated agents

The files under agents/ are generated from these charters; edit the sources here instead. After a reviewed change
to a charter or `allowlist.json`, run these commands from the plugin repository
root (outside an initialized WUWEI workspace):

```sh
bin/wuwei agents build
bin/wuwei agents check
ziran audit agents/ --write-baseline agents/ziran-baseline.json
ziran audit agents/ --baseline agents/ziran-baseline.json --format json
```

Use ZIRAN **0.40.0**, installed as a dev-time tool in a disposable virtual
environment with `python -m pip install 'ziran==0.40.0'`. Review the generated
agents and baseline diff, then commit both with their source changes. Never
hand-edit the baseline or regenerate it just to silence an unreviewed widening.
It records declared tools and dangerous chains, never prompts or descriptions.

CI pins `taoq-ai/ziran@v0.40.0` and `ziran==0.40.0`, auditing `agents/` against
`ziran-baseline.json` on pull requests and main pushes. Existing Bash and Write
grants are accepted; widened tools/chains or new critical findings fail. Adding
WebFetch to the builder reports a new chain containing WebFetch. Audit exits
1 (findings) and 2 (could not run) both fail CI. SARIF uploads use the action's
default output; unavailable code-scanning permissions do not hide audit failures.

The default pytest suite checks generated-agent drift and baseline version,
agent names and tool lists without ZIRAN. When `ziran` is on PATH, it also audits
a clean copy and a copy with WebFetch added to the builder. Only those real-tool
cases skip when ZIRAN is absent; the audit job runs them with the pinned install.

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
