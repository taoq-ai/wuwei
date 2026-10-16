# Feature Specification: the routes seats run and the payloads the harness sends are fixtures the suite reads

**Feature branch**: `claude/route-fixtures`
**Item**: route-fixtures, tier standard, goal G-2
**Input**: guard changes are tested on hand-picked commands. Nothing shows, in a guard change's
diff, which real routes it moves from pass to a door or back. The hook is tested on payloads typed
into each test, not on the shapes the harness sends.

## The promise in my words

Two fixture sets, read by the suite, with no runtime change.

`tests/fixtures/routes.json` lists every gh and git command the charters, skills, the PR standard
and the docs site tell a seat to run, and the gh api commands seats ran in this workspace today,
with local paths dropped. Each route names its source and the verdict main gives it today: `pass`,
or the door it reaches (`merge`, `create`, `push`, `refusal`). `tests/test_guards.py` reads every
route through `guards.bash` with the code host stubbed and asserts that verdict. A guard change that
moves a verdict fails the test until the fixture is edited, so the fixture diff shows the move.

`tests/fixtures/payloads/` keeps harness payloads with secrets and workspace content removed: an
Agent PreToolUse and PostToolUse for an accepted and a rejected launch, a Codex `spawn_agent`, a
PreToolUse fired inside a subagent (with `agent_id` and `agent_type`) and a SubagentStop.
`tests/test_hook.py` replays each through `hook.handle` and asserts no error and the seat rows it
writes.

Outside: changing any verdict, and the SECURITY.md deny-list gaps.

The acceptance scenarios, restated:

1. On main, every route reads as recorded and every payload replays without a `hook.error`.
2. A guard that refuses `gh api repos/o/r/pulls/5/ccr/review_threads` fails a test whose id names
   that route.
3. The shepherd's review ping `gh api -X POST repos/o/r/issues/5/comments -F body=@ping.md` passes,
   and the fixture records it as `pass`.
4. No file under `tests/fixtures/` matches `guards.SECRETS` or the workspace canary.

## Requirements

- FR-001: `routes.json` holds `routes`, each with `command`, `source` and `verdict`; commands are
  unique and verdicts come from the five named values.
- FR-002: The stub plays repository `o/r`, branch `i-1-change`, and PR 5 and the branch with a
  safety gap (no test), so every merge and create route meets its door.
- FR-003: Each route is its own parametrized case, its id the command.
- FR-004: Each payload carries `hook_event_name`; the replay uses it as the event.
- FR-005: A fixture file holds no secret pattern, no workspace canary and no local path
  (`/home/`, `/tmp/`, `/root/`, `/Users/`).
- FR-006: No runtime line changes (cli/wuwei stays at 2,999).

## Assumptions

- The verdict is read from the decision: `None` is pass; a note or the create door's refusal is
  `create`; the merge door's refusal (gaps, or no PR named) is `merge`; a force or default-branch
  push is `push`; any other deny is `refusal`. Overturned by a door whose reason text changes; the
  test then fails and names the route, which is the intent.
- Routes the sources describe without a literal command (request reviewers, the evidence comment,
  merge the base, push the branch) are filled with the plain command for that duty, and the source
  names the line. Overturned by a charter that names a different command; the route is then edited.
- The workspace commands come from `.wuwei/traces.jsonl` rows of 2026-10-16, whose targets the hook
  cuts at 160 characters. Each route keeps the gh api segment and its neighbours where whole, closes
  a cut jq expression, and drops pipes into local scripts. Overturned by a need for the exact text;
  the trace does not keep it.
- The accepted Agent payloads take their field names and values from this session's transcript (the
  tool input and `toolUseResult` of a real launch), with the prompt, output path and session id
  replaced. No rejected launch, Codex call or hook stdin was recorded in the workspace, so the rejected
  PostToolUse (a string error response), the Codex `spawn_agent` (the shape tests/test_codex.py
  uses), the subagent PreToolUse and the SubagentStop follow the documented hook fields and the
  ledger rows (`seat.stopped` with agent ids, traces with an `agent` field). Overturned by a captured
  payload with a different shape; replace the file and the test shows what moves.
- The canary check uses `.wuwei/canary` at the repository root when present, and otherwise the
  prefix `wuwei-canary-` every canary starts with (setup.py).
