# Implementation Plan: session orientation (`wuwei next`, SessionStart block, agent guide)

**Branch**: `358-session-orientation` | **Date**: 2026-10-03 | **Spec**: spec.md

## Summary

One new command module, `cli/wuwei/commands/next.py`, holds the whole derivation
(`step(root)`) and the orientation text (`orientation(row, posture)`). SessionStart calls
both in process from `lifecycle.session_start`; the hook puts the block first. One new doc,
`docs/site/agent.md`, plus one line in each skill and links in the owner docs.

Reused, not copied: `workspace.find_workspace`, `workspace.load_config`,
`workspace.day_dir`, `workspace.posture`, `workspace.now`, `calibrate.approved` (the same
"calibration never applied" test `doctor` uses), `state.read_state`, `state.BUILD_PHASES`,
`brief.seats` (validated seat reader), `decision.answered` (the same pending test
`status.scan` uses), `status.scan` (watch and heartbeat health, read only when reaching
the `doctor` row), `integrity.PLUGIN` (plugin root), `watch.ERRORS`, and the existing
`WUWEI_SEAT_ROLE` variable (`merge.py`, `outward.py`, `shepherd.py`).

## Technical Context

Python 3.11+ stdlib only; pytest for tests. No subprocess, no adapter, no write. Tests are
in process: `main(['next', ...])` from `wuwei.__main__`, `lifecycle.session_start`, and
`hook.run` with the recorded `tests/payloads/SessionStart/recorded.json`. Workspaces are
built in `tmp_path` with `WUWEI_WORKSPACE` and `WUWEI_NOW` (pattern: `tests/test_sessions.py`
fixture `root`), state through `state._write_state(..., reserved=False)`.

## Constitution Check

- I stdlib only: yes. II three-state: `next` exits 0 with a row, 2 with the reason when an
  input is unreadable; never 1. SessionStart keeps its existing codes; an unreadable row
  sets 2 and still prints the block. III one behaviour, one function: `step` is the only
  place that maps day state to a next step; skills, SessionStart and docs point at it.
  IV test first: tasks.md orders every test before its code. V ponytail: no new state, no
  event, no config key, no doctor run, no board or DM wiring, no eval fixture. VII
  security: the row is display text; nothing trusts it, so no `state.RESERVED` change;
  `WUWEI_SEAT_ROLE` only selects text and is checked against the shipped charter files
  before a path is built from it. Scope: outside a workspace SessionStart stays silent
  (#323) because `hook.run` returns before guards run and `lifecycle.scoped` returns None.

## Design

### 1. `cli/wuwei/commands/next.py` (new)

```python
"""Where the day stands and the one next step, read from the day's files only."""

HEADER = 'WUWEI orientation'
TERMINAL = ('merged', 'parked', 'escalated')
POSTURES = {
    'observe': <the current lifecycle.SHADOW_LINE text, unchanged>,
    'guarded': 'Posture guarded: records, publishing and plugin integrity block; seat '
               'launches, outward text and MCP findings below the floor warn. A refusal '
               'names its reason and the accepted form: use that form, never a way around it.',
    'strict': 'Posture strict: every guard area blocks. A refusal names its reason and the '
              'accepted form: use that form, never a way around it.',
}

def register(subparsers)   # 'next', help, --json flag, func=run
def step(root)             # -> {'state', 'step', 'command'}; root None means no workspace
def line(row)              # f"{state}: {step} Run: {command}"
def orientation(row, posture)  # the block, as one string
def run(args)
```

`step(root)`, first match wins (spec FR-002):

| state | condition | command |
| --- | --- | --- |
| `no-workspace` | `root is None` | `bin/wuwei setup --shadow` |
| `setup` | `not config['repos'] or not calibrate.approved(root)` | `bin/wuwei setup` |
| `plan` | `day_dir / 'plan.md'` not a file | `/wuwei:wuwei-plan` |
| `gate` | `not data['gate_approved']` | `/wuwei:wuwei-plan` |
| `decision` | first id in `data.get('decision_routes', {})` with `answered(data, id) is None` | `wuwei decision show <id>` |
| `build` | first approved item, not running, phase in `state.BUILD_PHASES` | `wuwei build next <item>` |
| `verdicts` | same, phase in `('gate', 'delta')` | `wuwei dispatch next <item>` |
| `pr` | same, phase `raised` | `wuwei pr act <items[item]['pr']>` |
| `dispatch` | same, phase `planned` and `building < data['cap']` | `wuwei worktree add <item>` |
| `wait` | any seat with `status == 'running'` | `wuwei status --line` |
| `doctor` | `status.scan` gives watch `dead` or heartbeat `degraded` | `wuwei doctor` |
| `closed` | `report.md` is a file and `data.get('close_requested')` | `wuwei close` |
| `close` | otherwise (every approved item merged, parked or escalated) | `/wuwei:wuwei-report` |

Details:

- `data = state.read_state(directory=day_dir)`; `running` is the set of `seat['item']` over
  `brief.seats(data)` with `status == 'running'`; `building` counts approved items whose
  phase is in `state.BUILD_PHASES`. Items are walked in `data['approved_items']` order;
  an id missing from `data['items']`, a terminal phase or a running item is skipped; a
  `planned` item with `building >= cap` is skipped.
- Step texts are one sentence each and say who acts. Required content: `setup` says the
  owner runs it in a host terminal and that it finishes the repositories, calibration and
  interview; `plan` says "start the day"; `gate` names
  `days/<date>/plan.md`, the `Morning gate` questions and "approve only on the owner's
  answers"; `dispatch` names the queue count, CAP, and the brief
  (`wuwei brief builder <item> <name> --worktree <path>`) and `wuwei build next <item>`
  that follow; `wait` lists the running seat names and says SubagentStop records each
  result; `closed` says tomorrow starts with `/wuwei:wuwei-plan`.
- `status.scan(directory, {**data, 'now': workspace.now().isoformat()})` is imported and
  called only when the walk reaches the `doctor` row (keeps SessionStart cheap on busy
  days).
- `run`: `root = workspace.find_workspace()`, `FileNotFoundError` gives `None`;
  `(OSError, ValueError, KeyError, TypeError, UnicodeError)` from `step` gives
  `{'state': 'unmeasured', 'step': str(exc), 'command': 'wuwei doctor'}`, the reason on
  stderr as `wuwei next: <reason>`, exit 2. Output: `json.dumps(row)` with `--json`, else
  `line(row)`.
- `orientation(row, posture)` returns these lines joined by `\n` (eight lines; the builder
  may tighten wording with the humanizer checklist but keeps every named token):

  ```
  WUWEI orientation
  WUWEI runs this workspace's coding day the way a careful engineering team works: the planner session ranks the work, seats build and review each change in their own worktree, and merges follow a policy.
  The owner answers questions and decisions; the session runs the commands (wuwei is the executable recorded in .wuwei/executable) and never asks the owner to edit a file.
  Day loop: plan, morning gate, dispatch builders, gates verify, PR and merge, report and close.
  <POSTURES[posture]>
  Next: <line(row)>
  <entry>
  Guide: <PLUGIN>/docs/site/agent.md (the whole flow for a session); owner guide: <PLUGIN>/docs/site/daily.md
  ```

  `<PLUGIN>` is `integrity.PLUGIN` (an absolute path computed at run time, never written to
  a file). `<entry>` is
  `Start or resume the day with /wuwei:wuwei-plan (steps: <PLUGIN>/skills/wuwei-plan/SKILL.md); run wuwei next whenever the next step is unclear.`
  unless `role = os.environ.get('WUWEI_SEAT_ROLE')` is a string with
  `(PLUGIN / 'charters' / f'{role}.md').is_file()` and `role` has no `/` and does not
  start with `_` or `.`; then it is
  `You are the <role> seat: follow <PLUGIN>/charters/<role>.md and your brief; the planner session runs the day.`
  No file is read to build the block.

### 2. `cli/wuwei/guards/lifecycle.py::session_start`

- Delete `SHADOW_LINE` (its text moves to `next.POSTURES['observe']`) and the two lines
  that append it (lines 40-41).
- In its place, first thing after `root, config = context`:

  ```python
  from wuwei.commands import next as next_command
  try:
      row = next_command.step(root)
  except watch.ERRORS as exc:
      code, row = 2, {'state': 'unmeasured', 'step': str(exc), 'command': 'wuwei doctor'}
  lines.append(next_command.orientation(row, workspace.posture(config)[0]))
  ```

  (`code, lines = 0, []` stays above it.) Everything else in the function is unchanged and
  follows the block, so `Active constraints:` is at line index 8 or 9.

### 3. `cli/wuwei/commands/hook.py` (SessionStart branch, lines 100-102)

Integrity's SessionStart guard runs first (module order) and can return a code-0 line
(`plugin integrity: owner-confirmed content (local evidence)` on a development checkout).
Put the orientation first:

```python
from wuwei.commands.next import HEADER
parts = sorted(context + reasons, key=lambda text: not text.startswith(HEADER))
```

and use `'\n'.join(parts)` as `additionalContext`. The stable sort keeps every other
order; the stderr line for reasons is unchanged. Import from `commands`, not from
`guards.lifecycle`: the hook tests replace `wuwei.guards.__path__`.

### 4. `docs/site/agent.md` (new, at most 100 lines)

Front matter `---\nlayout: default\n---\n`, `[Home](index.html)`, then, written for an
agent with no prior context, humanizer checklist (`charters/_common-authoring.md`,
"Writing for a person"), no em dash, no emoji:

1. What WUWEI is (two or three sentences) and the first rule: run `wuwei next` and follow
   it; `wuwei` means the executable in `.wuwei/executable`, or `python3 -P -m wuwei`.
2. Roles: planner session (this session, `/wuwei:wuwei-plan`), lead, builder, gate
   sentinels (arch, quality, security, goal), shepherd, steward; one line each with who
   launches it.
3. The day in order, one line per step with its command: setup (owner, host terminal,
   `bin/wuwei setup --shadow`), plan (`/wuwei:wuwei-plan`: `plan session`, `mcp check`,
   lead, `rank`, `plan propose`), morning gate (AskUserQuestion, `plan approve`), build
   (`worktree add`, `brief builder`, `build next`), gates (`dispatch next`,
   `dispatch receive`), PR (`pr raise`, `pr act`, `merge check`), close
   (`/wuwei:wuwei-report`: `close`, `retro`, `promote`, `report`).
4. What the hooks refuse and the accepted forms: records under `.wuwei/` are written only
   through the CLI; item worktrees only through `wuwei worktree add`; seats launch only
   from a logged brief with the returned prompt unchanged; no deploy, no merge outside
   `wuwei merge`, no PR approval; Python only with `-P`; a refusal ends with a `posture:`
   line; follow the reason, never route around it.
5. Where each record lives and which command writes it: `config.toml` (`setup`,
   `config set`), `days/<date>/state.json` and `events.jsonl` (the CLI), `plan.md`
   (`plan propose`), `briefs/` (`brief`), verdicts (`dispatch receive`), `decisions/`
   (`decision`), `report.md` (`report`), `retro/` (`retro`), `memory/` (`note`,
   `promote`).
6. How the owner answers: AskUserQuestion in the session, the phone through Remote Control
   or the Slack DM, and owner-only commands in a host terminal in every posture
   (`decision outcome`, `drafts approve`, `mcp decide`, `config set`, `setup`).
7. First day: `bin/wuwei setup --shadow` (init, repositories, calibration, interview),
   then `/wuwei:wuwei-plan`; the plan skill asks the calibration questions on the first
   day.

### 5. Skills (`skills/wuwei-plan`, `wuwei-report`, `wuwei-retro`, `wuwei-consolidate`)

First paragraph under the `# /wuwei ...` heading gains, as its first sentence:
`Run wuwei next first and follow the step it names; run the steps below when it names this skill or the owner asked for it.`
(with `wuwei next` in backticks). Nothing is deleted (no skill restates the day order);
phrases pinned by `tests/test_docs.py`, `tests/test_charters.py` and
`tests/test_records_after_dryrun4.py` stay.

### 6. Owner docs

- `docs/site/reference.md` commands table: row between `metrics` and `note`:
  ``| `bin/wuwei next` | Prints where the day stands and the one next step with its command; `--json` prints `{state, step, command}`. | [What the session knows](agent.html) |``
- `docs/site/index.md`: list item `- [What the session knows](agent.html): the guide every session in the workspace is pointed at on start`.
- `docs/site/daily.md`: in the intro paragraph, one sentence linking
  `[what the session knows](agent.html)`; the "Re-anchoring" bullet says every
  SessionStart opens with the orientation block (what WUWEI is, the posture, the
  `wuwei next` step) followed by `Active constraints:` and the rest. Keep the phrase
  `Active constraints`.
- `README.md` Quick start, after "Run `/wuwei plan` ...": one sentence that every Claude
  Code session in the workspace orients itself on start (what WUWEI is, where the day
  stands, the next step from `bin/wuwei next`), linking `docs/site/agent.md`.

### What must not change

- SessionStart outside a workspace: no output, exit 0 (#323).
- `memory.session_payload` text and every other line `session_start` emits, in order,
  after the block. `status.scan`, `status.attention`, `doctor`, `closing` untouched.
- No new state key, event kind, config key or reserved producer.
- `hook.run` behaviour for every event other than SessionStart, and SessionStart's exit
  codes and stderr.

### Existing tests the change touches

- `tests/test_sessions.py::test_issue_acceptance_payload_after_compaction` asserts
  `text.startswith('Active constraints:\n')`: change it to assert the text starts with
  `next.HEADER` and contains `'\nActive constraints:\n'`.
- `tests/test_shadow.py:123` reads `Observe posture is on` from `session_start`: still
  true (observe posture line).
- `tests/test_listen.py:591-599` compares two `session_start` outputs: the row is the same
  in both calls, so it should hold; rerun it.
- `tests/test_docs.py::test_reference_lists_every_cli_command` and
  `test_site_pages_and_links` fail until the reference row and the index link exist;
  they are the red tests for those docs edits.

## Project Structure

```text
cli/wuwei/commands/next.py        new: step, line, orientation, run
cli/wuwei/guards/lifecycle.py     orientation first; SHADOW_LINE moved
cli/wuwei/commands/hook.py        SessionStart: orientation first
docs/site/agent.md                new
docs/site/{index,daily,reference}.md, README.md, skills/*/SKILL.md   links and one line each
tests/test_next.py                new
tests/test_docs.py, tests/test_sessions.py   updated
```

## Complexity Tracking

None. Deliberate limits, each a `ponytail:` comment in `next.py`: one row, not a list (the
first due item wins; `wuwei status --line` and the board show the rest); health is read
from recorded events, not a doctor run (latency budget).
