# Real Claude Code headless day

The `headless-e2e` job in `.github/workflows/tests.yml` runs on pushes to main
with `ANTHROPIC_API_KEY`, matching skill-evals. Pull requests skip the paid run.
Without the secret it prints `ANTHROPIC_API_KEY is not set; skipping headless e2e`.
The ordinary pytest suite stays offline.

From the repository root, with Python 3.11+, Git, ssh-keygen and Claude Code on
PATH, run:

```sh
python3 scripts/headless_e2e.py
```

This uses the exported API key; without one it prints
`headless e2e unmeasured: ANTHROPIC_API_KEY is not set` and exits 2. To use your existing Claude login:

```sh
claude auth login
python3 scripts/headless_e2e.py --local-login
```

The local option copies a file-based OAuth credential into a private temporary
HOME when present. On macOS Claude can use its existing OS keychain. No user
settings, installed plugins, MCP servers or workspace environment are inherited.
The temporary credential copy and all fixture files are removed on exit. The
runner does not print credentials or upload transcripts.

The runner copies the release inputs, generates a throwaway signing key, invokes
`scripts/build-release.py`, and loads the signed staged plugin with `--plugin-dir`
under a scratch HOME. It initializes a WUWEI workspace and clones this local
repository as the demo, then removes the clone's remote. The fixture item checks
README presence without tracked edits or commits.

The actual invocation is constructed in `scripts/headless_adapter.py`:

```text
claude -p --plugin-dir <scratch-plugin> --model sonnet --max-turns 48
  --max-budget-usd 3 --output-format json --setting-sources project
  --strict-mcp-config --mcp-config '{"mcpServers":{}}'
  --tools Bash,Read,Write,Edit,Glob,Grep,Agent,Skill
  --allowedTools Bash,Read,Write,Edit,Glob,Grep,Agent,Skill
```

The prompt arrives on stdin. The process tree has a 300-second deadline and no
paid retries. The CI job has an eight-minute outer deadline including installation.
The USD 3 limit applies to this Claude session, including its subagents.

The fixture supplies a lead proposal and explicit owner approval. Claude invokes
the real plan skill, records the proposal and approval, probes an unbriefed Agent
refusal, then uses the real builder step loop and three real sentinel seats. It
parks the unpublished item with a valid seat decision, requests close before the
retro to exercise a blocking Stop, then compiles the retro and closes cleanly.
No remote PR, tracker or chat action occurs. PR creation, a fix round and merge
remain covered by `tests/test_e2e_day.py` with recorded adapters, and live by the
release rehearsal in `docs/site/rehearsal.md`.

A temporary python3 shim observes the unmodified signed `bin/wuwei`: hook input,
exit codes and CLI calls go into `headless-hooks.jsonl` in the scratch workspace.
The runner checks that log plus producer-written day events and state. Assistant
prose is never completion evidence. This telemetry is a test oracle, not a new
production trust record or an owner authorization mechanism.

Exit 0 means measured success only. Exit 1 means recorded lifecycle evidence
failed assertions. Exit 2 means unmeasured: a missing credential, missing tools,
unreadable evidence, runtime errors, exhausted bounds or expired OAuth. An expired session prints `expired OAuth session; run claude auth login
and retry`; it is never reported as a generic failed assertion or a clean run.
