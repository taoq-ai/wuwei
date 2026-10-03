# Feature Specification: every owner question is an AskUserQuestion widget in the session, with its recording command printed next to it, and the DM when no widget exists

**Feature Branch**: `359-ask-widgets`

**Created**: 2026-10-03

**Status**: Draft

**Input**: GitHub issue #359, "feat(owner): every owner question is an AskUserQuestion
widget in the session, with its recording command printed next to it, and the DM when no
widget exists". Owner, 2026-10-03: "Since it is a plugin for Claude Code, if the tool is
running in the Desktop app, it should guide Claude to use the Ask widget and such, for easy
use." Orchestrator notes (binding): one widget printer, lifted from `calibrate --questions`
into a shared module and used by every command, no per-command JSON. #354 (owner confirm,
`decide`, session allowance), #357 (records by the workflow, goals) and #358 (`wuwei next`,
orientation) are built in parallel: build the printers and the skill text on main, hook into
whichever of them landed at rebase time; if none landed, ship the printers and the skill
text and leave the TODO in the PR body, not in code.

## Root cause (read and reproduced on main, ed28ab4)

Only two owner questions reach the session as widgets today. Everything else ends in a file
to edit or a command to paste:

- `cli/wuwei/interview.py:401-408` (`widgets`) is the only widget printer. It builds the
  AskUserQuestion shape inline (`question`, `header`, `options` of `label` and
  `description`, `multiSelect`, plus `id` and `repo`) and the
  `Morning gate (days/<date>/plan.md): ` prefix inline. `cli/wuwei/commands/calibrate.py:103-105`
  prints it. No other command can reuse it, and it prints no recording command: the skill
  spells the `--answer` form by hand (`skills/wuwei-plan/SKILL.md:17`).
- `cli/wuwei/commands/decision.py:28-31` gives `decision show` only `--full`. Reproduced in
  this worktree: `bin/wuwei decision show D-1 --widget` exits 2 with
  `unrecognized arguments: --widget`. The planner composes each D-n question by hand.
- `cli/wuwei/commands/mcp.py:10-13` has no widget form. The skill tells the owner to
  "record `Decided-by: owner` and `Outcome: proceed` in the decision", a hand edit of a
  Markdown record (`skills/wuwei-plan/SKILL.md:14`), then run `mcp decide` at the host.
  The per-server findings exist only as `mcp.finding` events (`cli/wuwei/mcp.py:438-440`).
- `cli/wuwei/commands/doctor.py:574-579` has `--fix` and `--json` only; the batch is
  confirmed with a typed digest at the host (`doctor.py:549-554`). Reproduced:
  `bin/wuwei doctor --fix --widget` exits 2 with `unrecognized arguments: --widget`.
- `docs/site/daily.md:134-157` says the owner's commands "run in a host terminal, never
  through an agent" and does not say how a question reaches the owner in the session.
- Hard constraint, unchanged by this issue: `cli/wuwei/guards/decision.py:99-139`
  (`check_question`) refuses any `AskUserQuestion` in a workspace that does not cite a
  D-n or C-n whose record exists today and passes the lint, or is marked `Morning gate` and
  cites today's `plan.md`. Its area is `records`, a floor that blocks in every posture
  (`cli/wuwei/workspace.py:47`, `cli/wuwei/guards/__init__.py:37-38`). Every printed widget
  must therefore carry its citation in `question`.
- The headless path already exists: `cli/wuwei/remote.py:34-38` tells a headless planner
  that nobody can answer AskUserQuestion and to write the record and run
  `wuwei decision route <id>`. The skills do not say the same for a session without the
  widget, and do not say to prefer the widget when it is there.

So the fix is one shared printer next to the decision evaluator, a `--widget` flag on the
three commands that ask the owner something, the recording command in every widget, and
one rule in the four skills and in `daily.md`.

## User Scenarios & Testing

### User Story 1 - A pending decision is one widget and one recording command (Priority: P1)

The planner runs `wuwei decision show D-3 --widget` and passes the printed question to
AskUserQuestion. The owner taps an option. The planner runs the printed `record` command
with the chosen label.

**Why this priority**: decisions are the most frequent owner question and the one the owner
complained about.

**Independent Test**: `python -m pytest -q tests/test_decision.py -k widget`.

**Acceptance Scenarios**:

1. **Given** a valid pending `D-3` today, **When** `decision show D-3 --widget` runs,
   **Then** it exits 0 and prints a JSON list with one widget whose `question` is `D-3: `
   followed by the record's `Question`, whose `header` is `D-3`, whose `options` are the
   record's options (label the option id, description the record's description), the
   recommended option first with its description starting `Recommended. `, `multiSelect`
   false, and `record` `wuwei decision outcome D-3 <label>`.
2. **Given** that widget, **When** its `question`, `header`, `options` and `multiSelect`
   are passed to `check_question` as an AskUserQuestion payload, **Then** it returns
   `(0, '')`.
3. **Given** an invalid record, **When** `decision show D-3 --widget` runs, **Then** it
   exits 1 with the lint reason; an unreadable record exits 2; `--widget` with `--full` is
   a usage error (exit 2).
4. **Given** a record with five options, **When** the widget prints, **Then** it carries
   four options, the recommended one first.

### User Story 2 - The MCP accept question carries its findings (Priority: P1)

The planner runs `wuwei mcp check --widget`. Besides the usual check and reason, it prints
the pending MCP decision as a widget whose accept option describes the findings per server.

**Why this priority**: the MCP accept was the first-day stop that needed a hand edit.

**Independent Test**: `python -m pytest -q tests/test_mcp.py -k widget`.

**Acceptance Scenarios**:

1. **Given** MCP findings pending in today's `D-n` (one high and one critical finding on
   server `alpha`, one medium on `beta`), **When** `mcp check --widget` runs, **Then** it
   exits as `mcp check` does (1) and prints one widget for `D-n` with `defer` first (the
   record's recommendation) and the `proceed` description ending with one line per server,
   highest severity first: `alpha: 1 critical, 1 high` and `beta: 1 medium`.
2. **Given** an earlier `mcp.decided` event with outcome `proceed` today, **Then**
   findings before it are not counted.
3. **Given** no pending decision, or a pending decision recorded on an earlier day, **When**
   `mcp check --widget` runs, **Then** it prints `[]` and the usual reason.
4. **Given** a finding event whose `server_name` or `severity` is not a valid name or
   severity, **Then** the line reads `unnamed server` or `unknown`, never the raw value.

### User Story 3 - The doctor batch is one multi-select (Priority: P2)

The planner runs `wuwei doctor --fix --widget`, asks the printed multi-select and records
the owner's picks with `wuwei doctor --fix --apply <ids>`.

**Why this priority**: doctor runs less often than decisions, but its batch today needs a
typed digest.

**Independent Test**: `python -m pytest -q tests/test_doctor.py -k widget`.

**Acceptance Scenarios**:

1. **Given** today's `plan.md` and two allow-listed fixes due, **When**
   `doctor --fix --widget` runs, **Then** it applies nothing, asks nothing on the terminal,
   and prints one widget with `header` `Fixes`, `multiSelect` true, one option per fix
   (label the fix id, description its command and first preview line), a `question`
   starting `Morning gate (days/<date>/plan.md): ` that passes `check_question`, and
   `record` `wuwei doctor --fix --apply <labels>`.
2. **Given** one fix due, **Then** the widget adds a `Skip` option so it has two; **given**
   five or six fixes due, **Then** it prints two widgets of at most four options each.
3. **Given** no `plan.md` today, **When** `doctor --fix --widget` runs, **Then** it prints
   no widget, names `wuwei doctor --fix` for a host terminal on stderr, and exits 1.
4. **Given** `doctor --fix --apply calibrate` with two fixes due, **When** it runs with an
   accepting confirm, **Then** only `calibrate` is previewed, confirmed and applied; an
   unknown id exits 2 naming it; `--widget` or `--apply` without `--fix`, or both
   together, is a usage error (exit 2).

### User Story 4 - The interview widgets carry their recording command (Priority: P2)

`wuwei calibrate --questions` keeps its output and adds `record` to each widget, built by
the shared printer.

**Independent Test**: `python -m pytest -q tests/test_interview.py -k widget`.

**Acceptance Scenarios**:

1. **Given** two configured repositories, **When** `calibrate --questions` runs, **Then**
   the widgets are unchanged in `id`, `repo`, `question`, `header`, `options` and
   `multiSelect`, every one passes `check_question` once `plan.md` exists (existing test),
   and each has `record` `wuwei calibrate --answer "<id>=<label>"`, with ` --repo <repo>`
   appended for a repository question.

### User Story 5 - The skills and docs say: widget when available, DM otherwise (Priority: P1)

Every skill tells the session to ask each owner question with the widget a command prints
when AskUserQuestion is available, at most four per call, and to record the answer with
the printed command; to route the question to the DM with `wuwei decision route` and
continue with assume-and-record where the mandate allows when it is not; and that seats
never ask.

**Independent Test**: `python -m pytest -q tests/test_docs.py -k widget`.

**Acceptance Scenarios**:

1. **Given** each `skills/*/SKILL.md`, **Then** it contains `AskUserQuestion`,
   `decision route` and `--widget`, and neither `Decided-by: owner` nor `Outcome: proceed`.
2. **Given** `skills/wuwei-plan/SKILL.md`, **Then** step 1 uses `wuwei mcp check --widget`
   and the widget's `record`, step 4 uses the `record` of `calibrate --questions`, and it
   says to show the `wuwei_board` tool once at the start of the day when it is available
   and that nothing depends on it.
3. **Given** `docs/site/daily.md`, **Then** section 5 has a `### How you answer` part: in
   the session a question card, on the phone the DM, the host terminal for what a hook
   sends there.

### Deferred to rebase (issue acceptance that needs a parallel issue on main)

- **#358 `wuwei next`**: given a pending D-n as the next step, `wuwei next --widget` prints
  the same JSON as `decision show D-n --widget`; given headless mode, `wuwei next` (without
  `--widget`) names `wuwei decision route D-n`; a step that asks nothing prints `[]`. The
  orientation block states the same rule as the skills. Built at rebase if #358 landed.
- **#354 / #357 session allowance**: given the planner asked the widget this session and
  the owner answered, the recording command from that session exits 0 under observe and
  guarded, and strict prints the host-terminal command. The allowance is theirs; at rebase
  the `record` strings switch to `wuwei decide D-n <label>` and
  `wuwei mcp decide D-n <label>`.
- **#357 goals**: #357's plan adds no `goals propose`; the goals question stays the
  morning gate question citing `plan.md`, recorded with `wuwei goals edit --file <draft>`.
  A goals printer is added at rebase only if #357 ships a command to hang it on.

### Edge Cases

- A decision Question that names another D-n: the guard checks every id in `question`;
  the widget passes only when that record is valid today too (unchanged guard rule).
- The pending MCP decision lies in an earlier day: the guard cannot accept it today, so no
  widget is printed; the existing reason names the record.
- Free text from scanner events never reaches the widget: only validated server names and
  severities.
- Outside a workspace, `mcp check` returns 0 before any widget logic (unchanged); `doctor
  --fix --widget` without a workspace has no `plan.md` and takes the host-terminal path.

## Requirements

### Functional Requirements

- **FR-001**: One shared printer, `decision.widget`, builds every widget in the
  AskUserQuestion question form: `question`, `header` (at most 12 characters), `options`
  (2 to 4, each `label` and `description`), `multiSelect`, and `record`, the one command
  that records the answer, with `<label>` standing for the chosen label (comma-separated
  labels for a multi-select, or the Other text). It raises `ValueError` on a longer header
  or an option count outside 2 to 4. `calibrate --questions`, `decision show --widget`,
  `mcp check --widget` and `doctor --fix --widget` use it; no command builds widget JSON
  itself.
- **FR-002**: `decision.gate(root)` returns the `Morning gate (days/<date>/plan.md): `
  prefix; the interview and doctor widgets use it.
- **FR-003**: Every printed widget's `question` passes `check_question` when its record or
  `plan.md` exists today.
- **FR-004**: The commands print a JSON list of widgets on stdout (`[]` when nothing is
  asked) and keep their exit codes and stderr reasons.
- **FR-005**: `doctor --fix --apply <ids>` limits the batch to those allow-listed ids and
  keeps the existing confirmation.
- **FR-006**: The four skills and `daily.md` carry the widget-or-DM rule; the plan skill
  drops the hand edit of the MCP record.
- **FR-007**: Nothing new detects the host surface. The session chooses `--widget` because
  AskUserQuestion is in its tools; the CLI never guesses.

### Key Entities

- **Widget**: `{question, header, options: [{label, description}], multiSelect, record}`,
  plus `id` and `repo` for interview widgets. The session passes the first four keys to
  AskUserQuestion unchanged and runs `record` with the answer.

## Success Criteria

- **SC-001**: A pending decision, the MCP accept, the doctor batch and the interview each
  reach the owner as a widget from one command, with no Markdown edit asked of the owner.
- **SC-002**: Every printed widget passes the existing question guard unchanged.
- **SC-003**: The full suite passes; `tests/test_docs.py` pins the skill rule.

## Assumptions

- The issue's `interview --widget` and `interview --answer` are the existing
  `calibrate --questions` and `calibrate --answer`; no `interview` command is added.
- The output stays a JSON list of question objects, as `calibrate --questions` prints it
  today, so the existing skill instruction (pass four keys unchanged) and test hold. The
  extra `record` key is never passed to AskUserQuestion.
- The recommended option is marked by order and a `Recommended. ` description prefix; the
  label stays the bare option id so the recording command accepts it.
- A decision with more than four options shows the recommended option and the next three
  in record order; the owner can type any other id through Other. A `ponytail:` comment
  names the ceiling.
- On main the recording commands are the ones main has: `wuwei decision outcome D-n
  <label>` (host terminal), and for MCP the chain `wuwei decision route D-n && wuwei
  decision outcome D-n <label> && wuwei mcp decide` (host terminal). They become one
  command each when #354 lands; each string lives in one constant.
- The doctor widget cites today's `plan.md` because the question guard accepts only a
  record or the morning gate citation. Before the day's plan exists, doctor's fixes stay a
  host-terminal batch. Weakening the guard to accept an uncited question is out of scope.
- The MCP finding summary counts findings by severity per server since today's last
  `proceed` decision; tool names and drift types are left out because they are scanner
  output, untrusted text.
- Reason texts that still describe hand edits outside the skills and `daily.md`
  (`docs/site/configuration.md:407`, the MCP row fix in `cli/wuwei/commands/doctor.py:335`)
  belong to #354, which owns those texts; this issue does not touch them.
- No session allowance for `doctor --fix --apply` is added here; if #354's allowance is
  extended to it at rebase, `integrity-reconfirm` should stay host-only.
