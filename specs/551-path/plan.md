# Implementation Plan: The CLI owns the path and the model walks it

**Branch**: `551-path` | **Spec**: `spec.md`

## Summary

`wuwei next` becomes the one entry point of the day. `step(root)` (the hook-safe reader)
keeps its one-row shape and grows the missing day states as rows that carry `action`,
`command`, `why` and `then`. A new `resolve(row, root)`, called only by the `next` command,
turns a delegated row into the delegate's own action (`build.next_action`,
`dispatch.next_step`, `dispatch.launch_set`, the widget commands, `brief.seat_action`), and
`run()` appends one reserved `next.action` event naming what it returned. Two shared spots
lose their placeholders (`dispatch._seats` adds brief and receive `commands`, `launch_set`'s
`start` entry gets exact commands), `close` records `day.closed`, and `metrics.collect`
derives `planner_turns`, `planner_asks` and `off_path` from the events and traces. The plan
and report skills shrink to the loop; the planner charter keeps judgement only.

## Technical Context

Python 3.11+ stdlib only; pytest dev-only. Tests in process on neutral fixtures
(`tests/test_next.py` helpers, `fakes.day.Day`). No new dependency, no new state key.

## Constitution Check

- III one behaviour one function: ordering in `next.step`, delegation in `next.resolve`,
  gate seat steps in `dispatch._seats`, start commands in `dispatch.launch_set`, path
  metrics in `metrics.path`. Nothing is copied from a delegate. Pass.
- II exits: next exits 0, 1 when a delegate it ran reports a finding, 2 on unreadable input,
  as today. Pass.
- No forgeable trust: `off_path` and the once-per-day rule trust `next.action`, and
  `done` trusts `day.closed`; both kinds are reserved in `EVENT_PRODUCERS`
  (`cli/wuwei/commands/event.py`) to `wuwei next` and `wuwei close`. No state key added.
  Pass.
- Hook latency (10.6) and #346: `step()` adds no module import and no write; events are read
  once, json-parsing only lines that name a kind `step()` needs. `next.py` must not import
  `sessions` at module level: `cli/wuwei/commands/hook.py:125` imports `next.HEADER` on every
  hook event. Pass.
- #530: next never refuses; no guard changes. Pass.
- #477 availability: every `then` for a seat or a long command says background; `wait` ends
  the turn with `wuwei status --line`. Pass.

## Action shape and `then` lines

`_row(state, why, command=None, action='run', then=THEN['run'], **extra)` returns
`{'state', 'action', 'command'?, 'why', 'then', 'item'?}`. The key `step` is renamed `why`
everywhere (`next.py`, `guards/lifecycle.py:55` fallback row, tests).

`THEN` constants in `next.py` (one line each, no skill reference):

| Key | Text |
|-----|------|
| `run` | `Run the command, then run wuwei next.` |
| `background` | `Run the command through Bash in the background; run wuwei next when it exits.` |
| `agent` | `Pass it to Agent in the background, then run wuwei next; its completion notification brings this item back.` |
| `set` | `Do every entry now: run each command in order, pass every launch and continue to Agent in the background in one message, run each run entry through Bash in the background; then run wuwei next.` |
| `card` | `Ask the widget list with AskUserQuestion, record each answer with its record command, then run wuwei next.` |
| `owner` | `Show the owner the why and the command in one line; run wuwei next when they say it is done.` |
| `wait` | `End the turn with the output of wuwei status --line; run wuwei next when a completion notification arrives.` |
| `done` | `The day is closed; tomorrow starts with wuwei next.` |

`LOOP = 'Loop: run wuwei next --json, do the one action it returns, and run it again when the
result or a completion notification arrives.'`

## State table (`step` order; first due row wins)

`<d>` is today's day directory name; `once` means: skipped when today's `next.action` events
already returned (or passed) this state with this key. Rows marked R are filled by
`resolve`.

| # | state | Due when | action | command | then |
|---|-------|----------|--------|---------|------|
| 1 | `no-workspace` | root is None | `card` | `bin/wuwei setup --shadow` | `owner` |
| 2 | `setup` | no repos or no calibration (as today) | `card` | `bin/wuwei setup` | `owner` |
| 3 | `session` | today's state has no `planner_session_id` | `run` | `wuwei plan session <id>`: `os.environ['WUWEI_SESSION_ID']` (inline `sessions.current()`), else the literal `<session id>` | `run` |
| 4 | `pr-flow` | no `plan.md`; once | `run` | `wuwei doctor --section pr-flow` | `On exit 1 show its output to the owner unchanged, once; then run wuwei next.` |
| 5 | `mcp` | no `plan.md`; once | `run` | `wuwei mcp check` | `On exit 1 or 2 show the owner its one-line reason; then run wuwei next.` |
| 6 | `lead` | no `plan.md`, no `lead.json`, no `briefs/lead.md` | `run` | `wuwei brief lead day lead --body <LEAD_BODY>` (shlex-quoted) | `run` |
| 7 | `lead` R | `briefs/lead.md` and no seat `lead` | `launch` | from `brief.seat_action('lead', <brief>, root, root)` | `Pass it to Agent in the background. When its completion notification arrives, save the lead's JSON answer to .wuwei/days/<d>/lead.json with the Write tool, then run wuwei next.` |
| 8 | `wait` | seat `lead` running | `wait` | `wuwei status --line` | `wait` |
| 9 | `propose` | no `plan.md`, and `lead.json` exists or seat `lead` stopped | `run` | `wuwei plan propose .wuwei/days/<d>/lead.json` | `If that file is missing, first save the lead's JSON answer there with the Write tool. On exit 1 or 2 show the owner the reason; then run wuwei next.` |
| 10 | `gate` R | `plan.md`, gate not approved (never once) | `card` | `wuwei plan gate`; `widget` = its printed list + `mcp.widget(root)` | `Ask the widget list with AskUserQuestion. On Approve run its record command; on Change something ask the owner what to change, edit .wuwei/days/<d>/lead.json and run wuwei plan propose .wuwei/days/<d>/lead.json again; then run wuwei next.` |
| 11 | `goals` | approved, `days/<d>/goals.md` exists; once | `run` | `wuwei goals edit --file .wuwei/days/<d>/goals.md` | `Under strict the hook refuses and prints the command: show that line to the owner for a host terminal; then run wuwei next.` |
| 12 | `calibrate` R | approved, no earlier day directory under `.wuwei/days/`; once | `card` | `wuwei calibrate --questions` | `card`, plus `then show the owner bin/wuwei config promote for a host terminal.` |
| 13 | `telemetry` R | approved; once | `card` | `wuwei telemetry proposals --widget` | `card` |
| 14 | `decision` R | unanswered route (as today); once per D-n | `card` | `wuwei decision show <D-n> --widget` | `card` |
| 15 | `stuck` | as today | `run` | `wuwei seat stop <name> --unmeasured "seat ended with no recorded result"` | `run` |
| 16 | `build` R | as today | delegate | `build.next_action(item)` | `check`: `background`; `launch`, `continue`: `agent`; `done`, `park`: ask `step` again |
| 17 | `docs` | as today | `run` | `docs.command(...)` (unchanged; Deferred) | `Choose the value it names, record it, then run wuwei next.` |
| 18 | `verdicts` R | as today | delegate | `dispatch.next_step(item)` | `gates`: `set`; `fix`: ask `step` again; `raise`: the shepherd rows below; `escalate`: `run` `wuwei plan park <item> --reason "<reason>"` |
| 19 | `pr` | as today | `run` | `wuwei pr act <pr>` | `Run it and do any action it prints; when it prints nothing the PR waits on people: end the turn with wuwei status --line, the watch wakes you when it changes.` |
| 20 | `dispatch` R | as today | `set` | `dispatch.launch_set(root)` passed through | `set` |
| 21 | `steward` | a `steward.due` event newer than the last `steward.run` | `run` | `wuwei steward run --trigger tool-calls` | `background` |
| 22 | `steward` R | a `steward.run` event whose brief stem has no seat | `launch` | `brief.seat_action('steward', root / <brief>, root, root)` | `agent` |
| 23 | `wait` | as today (two rows) | `wait` | `wuwei status --line` | `wait` |
| 24 | `doctor` | as today; once | `run` | `wuwei doctor` | `run` |
| 25 | `close` | all approved items terminal, not `close_requested` | `run` | `wuwei close` | `run` |
| 26 | `close` R | `close_requested`, no `steward.run` with `trigger: close` today, an unanswered owner route | `card` | `wuwei decision show <D-n> --widget` (not once) | `card` |
| 27 | `close` | `close_requested`, no close steward run, no pending decision | `run` | `wuwei close` | `On exit 1 show the owner what it names and end the turn; then run wuwei next.` |
| 28 | `retro` | `close_requested`, no `retro/<d>.md` | `run` | `wuwei retro` | `run` |
| 29 | `promote` | `close_requested`; once | `run` | `wuwei promote` | `run` |
| 30 | `retro-applied` | `close_requested`; once | `run` | `wuwei retro` | `run` |
| 31 | `report` | `close_requested`, no `report.md` | `run` | `wuwei report` | `Present the report to the owner in one short message, then run wuwei next.`; with `outbound.owner_channel = "dm"` it adds `Also post it to the owner's DM <outbound.owner.slack.dm or .user> with the connector's send tool.` |
| 32 | `closed` | `report.md`, no `day.closed` event | `run` | `wuwei close` | `Exit 0 closes the day; on exit 1 show the owner what it names and end the turn; then run wuwei next.` |
| 33 | `done` | a `day.closed` event today | `done` | none | `done` |

Shepherd rows (resolve, when `dispatch.next_step` returns `raise` for an item):

- no `briefs/shepherd-<item>.md`: `run` `wuwei brief shepherd <item> shepherd-<item>
  --worktree <items[item].worktree> --body <SHEPHERD_BODY>`, the body ending with one
  `Review note: <note>` line per returned note; `then` `run`.
- brief logged, no seat `shepherd-<item>`: `launch` from
  `brief.seat_action('shepherd', <brief>, <worktree>, root)`; `then` `agent`.
- seat `shepherd-<item>` stopped while the item is still at `gate` or `delta`: `card` with
  command `wuwei why <item>`, `why` `shepherd-<item> stopped without raising the PR`, `then`
  `owner`.

Body constants (short, plain, no `decisions/gate-` path, no inline-verdict wording):
`LEAD_BODY` (next.py) asks for one JSON proposal with `goals`, `seat_policy`, `envelope`,
`sweep`, ordered `candidates` and optional `seats`, each candidate with `id`, `goal`,
`evidence`, `scope`, `overlap`, `track`, the three flags, `score` and `evidence_lines`, goal
blocks while `memory/goals.md` has none (the text of today's skill step 2, moved);
`SHEPHERD_BODY` (next.py): `Raise the PR for <item> and own it until merged.`;
`GATE_BODY` (dispatch.py): `Review <item> at its HEAD against its spec and acceptance
criteria.`; the builder body (dispatch.py) from today's `proposal.json` candidate:
`Implement <item>: <scope>. Evidence: <evidence>.`, falling back to `Implement <item> as
today's plan records it.`

## Changes

### `cli/wuwei/commands/next.py`

- `_row` as above; `THEN`, `LOOP`, `LEAD_BODY`, `SHEPHERD_BODY` constants.
- `_seen(directory)`: one read of `events.jsonl`; json-parse only lines containing
  `"next.action"`, `"steward.` or `"day.closed"`; returns `(returned, stewards, due, closed)`
  where `returned` is the set of `(state, key)` from `next.action` payloads (`state`, `item`
  or D-n) plus their `passed` states. Called lazily, at most once per `step` call.
- `step(root)`: rows 1 to 33 in the table order. Existing rows keep their conditions and
  texts (now `why`); `plan`, `gate` and `close`/`closed` rows are replaced by rows 3 to 10
  and 25 to 33. No new module-level import; nothing written.
- `resolve(row, root)` (command path only; imports inside): for rows marked R, call the
  delegate and return the action as `{'state': row['state'], **delegate_action, 'why':
  row['why'], 'then': <THEN for the action>}`, keeping `item`. Widgets come from
  `_widget(argv)`, which runs `wuwei.__main__.main(argv)` in process with stdout captured and
  parses the JSON list (the same code the planner would run). Return `None` when the step
  must be asked again: a widget list is `[]` (the state is passed), or the build loop
  returned `done` or `park`, or the gate returned `fix`.
- `named(action)`: the exact commands an action names: `command`, each widget `record`, each
  entry's `command` and `commands`, each seat's `receive` and `command`, `commands`, plus a
  command a row's `then` names (the gate row's `wuwei plan propose
  .wuwei/days/<d>/lead.json`), so following `then` is never off the path.
- `run(args)`: `row = step(root)`; up to 8 times: `action = resolve(row, root)`; on `None`
  append `next.action` with `passed` and ask `step` again. Then, when today's `state.json`
  exists, append `next.action` `{state, action, item, named, traces}` where `traces` is the
  line count of `traces.jsonl` (0 when absent). A delegate's `dispatch.Refused` or
  `PortExit` 1 prints the coarse row with the reason as `why` and exits 1; `ERRORS` keep
  exit 2 with the `unmeasured` row.
- `text(row)`: `f"{state}: {why} {then}"`, then the command on its own line when present
  (`Agent <agent_type>` for `launch` and `continue`). `run` prints `text` without `--json`.
- `orientation(row, posture, spec, session)`: `Next: ` + `text(row)` with `<session id>`
  replaced by `session` when known; the planner entry is `[LOOP]` for every non-seat
  session. Delete `steps()` and the `re` import if unused.

### `cli/wuwei/dispatch.py`

- `_seats`: for the initial round, a role (no `@`) with no logged first-model brief adds
  `wuwei brief <role> <item> <role>-<item> --gate --worktree <items[item].worktree> --body
  <GATE_BODY>` to a `commands` list; a logged brief whose seat is `stopped` and whose
  initial verdict is not recorded adds its `receive` command. For the delta round, a role
  whose seat has stopped with a head that no longer matches the initial verdict head and
  whose delta verdict is not recorded adds its `receive ... --round delta`. Return the
  commands beside the seat actions; `next_step` puts them on the `gates` action as
  `commands` only when non-empty. Launch counting in `launch_set` stays `len(seats)`.
- `launch_set`: the `start` entry is `{'action': 'start', 'commands': [...]}` with
  `wuwei worktree add <name>` only while `root / 'worktrees' / name` is missing, then
  `wuwei brief builder <name> builder-<name> --worktree worktrees/<name> --body <builder
  body>` (shlex-quoted).

### `cli/wuwei/commands/close.py`

- Plain `close`: when the final `code == 0` after `closing.check`, append `day.closed`.

### `cli/wuwei/commands/event.py`

- `EVENT_PRODUCERS['next.action'] = 'wuwei next'`, `EVENT_PRODUCERS['day.closed'] =
  'wuwei close'`.

### `cli/wuwei/metrics.py`

- `path(events, traces, planner)`: `planner_turns` = `session.seen` events with `hook ==
  'Stop'` and `session_id == planner`; `planner_asks` = planner spans named
  `AskUserQuestion`; `off_path` = the list of planner Bash commands (from
  `gen_ai.tool.arguments`) not matched by the `named` list of the governing `next.action`
  (the last one whose `traces` count is at most the span's line index). Matching: shlex
  argv, a first word whose basename is `wuwei` becomes `wuwei`, the value after `--body` is
  ignored, a `<label>` token matches any token; `wuwei next ...` and `wuwei status --line`
  are exempt. Any value is `UNMEASURED` without a planner, or (asks, off_path) without
  traces.
- `collect`: adds `planner_turns`, `planner_asks` and `off_path` (the list's length). The
  report's process metrics carry them with no report change.

### `cli/wuwei/guards/lifecycle.py`

- Fallback row (`:55`): `{'state': 'unmeasured', 'action': 'run', 'why': str(exc),
  'command': 'wuwei doctor', 'then': ...}` (use `next_command._row`).

### `cli/wuwei/guide.py`

- First line after the title becomes `LOOP` (from `next_command`).
- Records and questions gains one line: with `outbound.owner_channel = "dm"` post each
  digest, nudge and report shown to the owner to the owner's own DM
  (`outbound.owner.slack.dm`, or `outbound.owner.slack.user` when `dm` is empty); a held
  send or refusal that names `bin/wuwei outbound learn --tool <tool>` (with `--owner <file>`
  or `--thread <file>`): run it and do what it prints.
- Regenerate the block in `docs/site/agent.md` (the test pins it to `guide.text()`).

### Skills and charter

- `skills/wuwei-plan/SKILL.md` (under 25 lines): frontmatter and heading unchanged; body:
  1. "Loop on `wuwei next`: run `wuwei next --json`, do the one action it returns, and run
     it again when the result or a completion notification arrives; read
     `.wuwei/executable` once with the Read tool and use the absolute path it holds as the
     first word of a plain command, never through a shell variable or a command
     substitution; never invoke Python without `-P`." plus the owner preferences file
     `.wuwei/charters/planner.md` and the `wuwei_board` line.
  2. "Each action has a `why` and a `then`; do what `then` says. `wuwei guide` holds every
     command and rule."
  3. Bullets: `run`, `check` (one plain Bash call, in the background when `then` says so);
     `launch` (Agent in the background, `prompt` unchanged, `agent_type` as
     `subagent_type`, a short description); `continue` (the same with `resume`); `set`,
     `gates` (every entry this turn, every launch and continue to Agent in the background in
     one message so they run concurrently); `card` (AskUserQuestion with the `widget` list,
     at most four per call, `question`, `header`, `options`, `multiSelect` unchanged,
     `record` with `<label>` replaced, labels joined by commas, `Skip` records nothing; a
     card without a widget is a line to show the owner; headless: `wuwei decision route
     D-n` for the DM; Seats never ask the owner; `wuwei decision show D-n --widget` is asked
     only when next returns it); `wait` (end the turn with `wuwei status --line`); `done`.
  4. "Never resume or interrupt a seat to answer the owner; answer from `wuwei status
     --line`." and the one `humanizer` sentence with tracker comments, docs pages, DMs, PR
     comments, review pings and `charters/_common-authoring.md` under Writing for a person.
  It must pass `BLOCKING` in `tests/test_charters.py` (write "Agent in the background",
  "through Bash in the background", "as one plain Bash call").
- `skills/wuwei-report/SKILL.md`: the same body (no board line), its own frontmatter and
  heading.
- `charters/planner.md` (version 2.0.0): rules of judgement only, three sections: what the
  planner decides (brief text and its contents; seat policy at the gate: "model and runtime
  for each role"; intraday admission with `wuwei plan add <item>` and `wuwei plan add <item>
  --goal G-n`, never finishing an owner's item outside the plan; a missing ticket with
  `bin/wuwei tracker create <item>`; a missing spec step is relayed, never skipped), what it
  records (decisions batched by record id, a denied or unmeasured action stays pending with
  its reason; follow-ups with `bin/wuwei tracker create --follow-up <item> "<title>"
  --evidence "<line>"`), what goes to the owner (only the cards next returns; answer from
  the board, "never by resuming or interrupting a seat"; the report). Regenerate `agents/`
  with `bin/wuwei agents build`.

### Docs

- `docs/site/reference.md:46`: the `next` row names the action shape
  `{state, action, command or prompt and agent_type, why, then}` and the loop.

## Existing tests that change (and only these)

- `tests/test_next.py`: shape asserts (`step` to `why`, keys), `plan`, `gate`, `close`,
  `closed` rows become the new rows; `test_steps_come_from_the_skill_file` is deleted with
  `steps()`; orientation tests assert `LOOP` and the action instead of the step list.
- `tests/test_e2e_day.py:29`, `:202` and `tests/test_dispatch.py` exact `gates` dicts where
  no brief is logged or a stopped seat awaits `receive`: add the exact `commands`.
- `tests/test_dispatch.py:1473`: the exact `start` commands.
- Skill pins moved: `tests/test_docs.py:471` (`wuwei worktree add`: covered by the
  `start` test), `:486` (`wuwei rank`: removed, propose ranks), `:561-563` (keep
  `.wuwei/charters/planner.md` in the skill; `calibrate --questions` asserted on next's
  `calibrate` row), `:567` (asserted on next's `pr-flow` row), `:677-679` (`` `seats` `` and
  `` `receive` `` asserted on the `gates` commands), `:903-907` (owner channel words asserted
  in `guide.text()`; report DM on next's `report` row), `:1082-1083` (`wuwei mcp check
  --widget` and `calibrate --answer` asserted in `guide.text()`'s widget list; `record` and
  `wuwei_board` stay in the skill); `tests/test_charters.py:271` (the verdict-order sentence
  is enforced by dispatch, removed from the skill pin); `tests/test_parallel_dispatch.py:140`
  (`wuwei dispatch next --all` asserted on next's `dispatch` row; `in one message` and
  `concurrently` stay); `tests/test_intraday_intake.py:278` (drop the skill path; the
  charter and daily page keep it).

## What must not change

- `build.next_action`, `dispatch.next_step` decisions (roles, rounds, tier, fix, raise,
  escalate), `launch_set` ordering and CAP logic, every guard and posture, the exit codes.
- `step()` stays hook-safe: no write, no new import (`tests/test_hooks.py` module pins) and
  the SessionStart budget test (4096 bytes).
- `approved()` keeps its signature (`dispatch.launch_set` imports it).
- The design spec (owner-amended only).

## Fixture day (`tests/test_path_day.py`)

- `tests/fakes/day.py`: `Runtime.finish` handles role `lead` (the message is the fixture's
  one-candidate proposal JSON) and `shepherd` (calls `day.raise_pr()`); everything else as
  today.
- The test sets `WUWEI_SESSION_ID=planner`, stubs `workspace.create_worktree` to link
  `worktrees/<item>` to the fixture repository (the VCS boundary; the existing check fake
  asserts the repository path), and runs the loop: `next --json`; for each named command
  `day.run(...)` then a `PostToolUse` Bash span for the planner; `launch` and `continue`
  through `day.execute`; `card` answers each widget's first option through its `record`
  command with a `PostToolUse` AskUserQuestion span; on the lead's `launch`, writes the
  lead JSON to `lead.json` as the `then` says; on `pr`, flips the code host PR to merged
  after the first run; `wait` sends a `Stop` and continues; stops on `done`. Quality FIX in
  the initial round and PASS elsewhere exercise the fix and delta rounds.
- Asserts: `done` reached within a bound, A `merged`, `day.closed`, retro and report exist,
  `metrics.collect` gives `off_path == 0`, `planner_asks` equal to the cards answered and
  `planner_turns > 0`.

## Headless eval

- `scripts/headless_adapter.py`: `claude_command(plugin, *, model='sonnet', ...)`.
- `scripts/headless_e2e.py`: `--model` (default `sonnet`); `exercise` passes it and loads
  `traces.jsonl`; `start_prompt` is unchanged (its no-command pin stays); `validate(...,
  start=True, traces=...)` adds a finding per `metrics.path(...)['off_path']` command other than
  the fixture's park forms (`PARK`), importing `wuwei.metrics` from the repository's `cli`
  directory. (Changed in build: the prompt may not name a command.)
- `docs/headless-e2e.md`: the `--model haiku` run and the off-path rule.
