# Feature Specification: the workflow writes its own records: lead-proposed goals run the first plan, the planner records them on gate approval, and no step asks the owner to edit a file by hand

**Feature Branch**: `357-records-by-workflow`

**Created**: 2026-10-03

**Status**: Draft

**Input**: GitHub issue #357, "feat(plan): the workflow writes its own records: lead-proposed
goals run the first plan, the planner records them on gate approval, and no step asks the
owner to edit a file by hand". Owner, 2026-10-03, third stop on the first day: "Wuwei expects
me to fill up markdowns, and this is not practical, this should all be done automatically.
The files are the record to guide the workflow itself, not for me to type everything."

## Root cause (read and reproduced on main, ed28ab4)

The lead proposed two well formed goals; the planner could not use them and asked the owner
to paste two blocks into `.wuwei/memory/goals.md` by hand. Three code paths force that:

- `cli/wuwei/plan.py:93-94` (`propose`) reads `memory/goals.md` and calls `goals.parse`,
  which raises `goals line 1: no goals` at `cli/wuwei/goals.py:57` for the shipped template
  (`templates/workspace/memory/goals.md` has only an indented example block). `_proposal`
  (`plan.py:41-44`) then accepts only `G-n` strings that already exist in that file, so a
  lead JSON cannot carry a goal of its own.
- `cli/wuwei/commands/rank.py:32` parses `memory/goals.md` before it reads its input, so
  `rank lead.json` fails the same way.
- `cli/wuwei/guards/protect_state.py:55-56` lists `('goals', 'edit')` and `('voice', 'edit')`
  as owner-only actions and `_owner_action` (`protect_state.py:158`) refuses them for every
  session, the planner included, so the planner cannot record what the owner approved.
  The template itself says "Owner: replace this guide with one block per goal before the
  morning plan" (`templates/workspace/memory/goals.md:3`), `docs/site/daily.md:66` says
  "Edit your goals in a host terminal", and `skills/wuwei-plan/SKILL.md` step 4 has no
  path for proposed goals.

Reproduced read-only in a scratch workspace (template `goals.md`, empty `config.toml`, a lead
JSON citing `G-1`): `plan.propose` raises `ValueError: goals line 1: no goals` from
`goals.py:57` via `plan.py:94`; `wuwei plan propose lead.json` and `wuwei rank lead.json`
both exit 2 with that reason.

## User Scenarios & Testing

### User Story 1 - The first plan runs on the lead's proposed goals (Priority: P1)

On a workspace whose `goals.md` has no `## G-n` block, the lead's JSON carries its goals as
objects (`id`, `outcome`, `measure`, `target`, `date`, `priority`). `plan propose` validates
them with the same parser as `goals.md`, shows them in `plan.md` marked provisional, writes
the exact `goals.md` text as today's draft `days/<date>/goals.md`, and ranks the queue on
them. `rank` on the same lead JSON orders the candidates on them too.

**Why this priority**: it is the stop the owner hit; nothing else in the day can start
until it passes.

**Independent Test**: `python -m pytest -q tests/test_plan.py -k provisional` and
`tests/test_goals_rank.py -k provisional`.

**Acceptance Scenarios**:

1. **Given** an empty-template `goals.md` and a lead JSON with two goal objects (`G-1`,
   `G-2`) and a candidate citing `G-1`, **When** `wuwei plan propose lead.json` runs,
   **Then** it exits 0, `plan.md` lists both blocks under its goals section marked
   provisional, `days/<date>/goals.md` holds both blocks and parses with `goals.parse`,
   `proposal.json` stores `goals` as `["G-1", "G-2"]`, and `memory/goals.md` is unchanged.
2. **Given** the same workspace and lead JSON, **When** `wuwei rank lead.json` runs,
   **Then** it exits 0 and prints the ranked candidates.
3. **Given** a goal object with a missing field, a bad date, a value with a newline or an
   unknown key, **When** `plan propose` runs, **Then** it exits 2 with a `proposed goals`
   reason and writes nothing.
4. **Given** a `goals.md` that already has `## G-n` blocks, **When** the lead JSON carries
   goal objects, **Then** `plan propose` refuses as today (`goals must cite identifiers in
   memory/goals.md`); confirmed goals are never replaced by a proposal.

---

### User Story 2 - The planner records approved goals and voice (Priority: P1)

The planner asks the goals question at the morning gate as today (AskUserQuestion,
`Morning gate`, citing `days/<date>/plan.md`, the proposed blocks shown). When that question
is answered, the PostToolUse hook records on the planner's session row that this session
asked the `goals` gate question today. On approval the planner runs
`wuwei goals edit --file .wuwei/days/<date>/goals.md`; the protect_state guard lets that one
call through from the registered planner session (not a subagent) under `observe` and
`guarded`. Under `strict` it refuses and prints the exact command for a host terminal. The
same path covers `voice edit --file` when a gate or interview question named `voice`.

**Why this priority**: without it the gate approval still ends in a hand edit.

**Independent Test**: `python -m pytest -q tests/test_owner_edits.py -k gate`.

**Acceptance Scenarios**:

1. **Given** the registered planner session answered a `Morning gate` question naming
   goals that cites today's `plan.md`, **When** that session (no `agent_id`) runs
   `wuwei goals edit --file <draft>` under `observe` or `guarded`, **Then** the guard returns
   0, the command exits 0, `memory/goals.md` holds the blocks, and
   `plan approve --items <ids> --goals-confirmed` succeeds.
2. **Given** the same under `strict`, **When** the planner session runs the command,
   **Then** the guard returns 1 with today's owner-action reason followed by
   `Run it in a host terminal: <the command as typed>`.
3. **Given** a seat (a call with `agent_id`, or a seat session from `trace_sessions`, or an
   unregistered session), **When** it runs `goals edit` or `voice edit`, **Then** it is
   refused exactly as today.
4. **Given** the planner session that has not asked a goals gate question today, or that
   runs `goals edit` without `--file`, **When** the guard checks the call, **Then** it is
   refused (with the host-terminal line, since the caller is the planner).
5. **Given** `plan approve --goals-confirmed` before the draft is recorded, **Then** it
   still exits 2 because `memory/goals.md` does not parse.

---

### User Story 3 - No owner-facing text asks for a hand edit (Priority: P2)

A lint test walks `skills/**/SKILL.md`, every string literal under `cli/wuwei/`,
`docs/site/**/*.md` and `templates/**` for owner-facing instructions to edit a record by
hand and fails with file, line and sentence. Legitimate mentions are whitelisted by exact
sentence. The planner skill, the goals template and the docs say the lead proposes goals,
the gate shows them and the planner records them.

**Why this priority**: it keeps the rule true after this issue; the code change alone does
not stop the next text from asking for a paste.

**Independent Test**: `python -m pytest -q tests/test_owner_records_lint.py`.

**Acceptance Scenarios**:

1. **Given** the repository, **When** the lint test runs, **Then** it passes: no
   owner-facing instruction to paste or edit a record by hand remains outside the
   whitelist.
2. **Given** a fixture string "Paste these blocks into goals.md", **When** the lint's
   matcher sees it, **Then** it reports it.

### Edge Cases

- Day rollover: the gate record lives on today's session row, so yesterday's question does
  not allow today's edit.
- The planner session takes over (`plan session --take-over`): the new session must ask
  the gate question itself; the old row's record does not transfer.
- The owner edits a proposed goal in the gate: the skill already says update the lead JSON
  and rerun `plan propose`; the draft is rewritten with it.
- A seat tampering with the draft before the planner records it: `days/<date>/goals.md` is
  added to the protected day files in `protect_state._protected_name`.
- A goal object whose values would inject a second `## G-n` block (a newline in a value) is
  refused before parsing.
- `goals edit` inside a script file, through `xargs` or with a non-literal verb stays
  refused (the allowance applies only to a literal argv).

## Requirements

### Functional Requirements

- **FR-001**: `plan propose` MUST accept lead `goals` as goal objects when `memory/goals.md`
  has no `## G-n` heading, render them to `goals.md` text and validate that text with
  `goals.parse`.
- **FR-002**: `plan propose` MUST then write `plan.md` with the blocks marked provisional,
  the draft `days/<date>/goals.md`, and `proposal.json` with `goals` as the identifiers; it
  MUST NOT write `memory/goals.md`.
- **FR-003**: `rank` MUST rank a lead JSON's candidates on its goal objects under the same
  condition.
- **FR-004**: `plan approve` MUST keep validating against `memory/goals.md` only.
- **FR-005**: The PostToolUse hook for AskUserQuestion MUST record, on the session row of
  the registered planner session, the topics (`goals`, `voice`) named by each answered
  `Morning gate` question that passes the existing citation check; calls with `agent_id`
  and other sessions record nothing.
- **FR-006**: protect_state MUST allow a literal `goals edit --file` or `voice edit --file`
  from the planner session (no `agent_id`) when that topic is recorded for it today and the
  posture is not `strict`; otherwise it refuses as today, and for the planner session it
  appends `Run it in a host terminal: <command>`.
- **FR-007**: `days/<date>/goals.md` MUST be a protected day file.
- **FR-008**: A lint test MUST fail on owner-facing hand-edit instructions in the four
  scopes, naming file, line and sentence, with an exact-sentence whitelist.
- **FR-009**: The design spec (5.2, 5.7), the planner skill (steps 2 and 4), the lead
  charter step 3, the goals template and the site docs MUST describe the new flow.
- **FR-010**: `plan template` MUST print a provisional goal object instead of refusing
  when `memory/goals.md` has no goals.

### Key Entities

- **Goal object (lead JSON)**: `{"id": "G-n", "outcome", "measure", "target", "date",
  "priority"}`; exactly these keys; values are single-line strings, `priority` an integer.
- **Goals draft**: `.wuwei/days/<date>/goals.md`, the exact text `goals edit --file` takes.
- **Gate record**: `sessions[<planner session>].gate_asked`, a sorted list of topics.
  Producer: `wuwei hook PostToolUse` (event `gate.asked`).

## Success Criteria

- **SC-001**: On a fresh workspace, the first plan runs from lead JSON to `plan approve`
  without the owner creating or editing any file.
- **SC-002**: The lint test passes on the repository and fails on a planted instruction.
- **SC-003**: Every existing test that pins the seat refusal of `goals edit` passes
  unchanged.

## Assumptions

- `plan propose` does the proposal itself; a separate `wuwei goals propose` command is not
  added (the issue offers either; one path is less code).
- Lead goal objects carry their own `id`; candidates cite those ids. Proposals are accepted
  only while `memory/goals.md` has no `## G-n` heading; changing confirmed goals stays a
  `goals edit` the owner may do later.
- "Asked in this session" is recorded at PostToolUse (the question was shown and answered),
  not PreToolUse. The topic is found by the words `goal`/`goals` and `voice` in the question
  text or header. The answer itself is not parsed; the planner acts on it (spec 9.1: the
  hook is a friction boundary, not proof).
- The planner is `planner_session_id` in today's state and the call has no `agent_id`.
  A seat that took over the planner registration is out of scope (9.1).
- #354 is not on main (its worktree has no changes). This issue implements the allowance
  for `goals edit` and `voice edit` only, as one helper #354 can extend with `D-n` topics.
  The decision texts #354 removes (`skills/wuwei-plan/SKILL.md` step 1,
  `docs/site/configuration.md` "sets `Decided-by: owner`", `cli/wuwei/commands/doctor.py`
  "set Outcome: proceed") are listed in the lint test under a `PENDING_354` set with a
  comment; if #354 is on main at build time, that set is empty and deleted.
- Config layout fallbacks ("Config differs; edit by hand") are reports about keys the owner
  set and the CLI cannot rewrite safely (#343); the lint patterns do not include "edit by
  hand".
- `docs/site/adapters.md` (credentials in `.wuwei/env`) and `docs/site/remote.md` ("Never
  paste the secret") are legitimate and whitelisted by exact sentence: the host terminal
  remains for credentials.
- `rank template` keeps requiring confirmed goals; only `plan template` (the documented
  lead skeleton) prints a provisional goal object.
- Neutral fixture goals only; never the owner's goal text.

### Found at build time

- #354 is not on main (ed28ab4), so `PENDING_354` holds the three decision sentences.
- `_STATE_HINT` keeps the words "owner" and "outside agent tools" because existing
  protect_state tests assert them; the new text names the planner's `--file` recording.
- The day draft protection test extends the existing
  `tests/test_goals_rank.py::test_plan_producer_files_are_protected` parametrization
  instead of adding one to `tests/test_protect_state.py`.
- `tests/test_guard_mutation.py` pins a probe per registered guard, so `record_gate` gained
  a probe row (malformed question from the planner session, exit 2).
- The lint's sentence splitter also ends a sentence at a period before a newline, so a
  template line reports alone.
- The skill's own rule reads "Never ask the owner to write a record by hand" because the
  word paste is a lint pattern.
- `signal.SILENT` and its pinned table in `tests/test_signal_status.py` gain `gate.asked`
  (silent: a record, not a nudge).
- The gate allowance tests record `.wuwei/executable` as the planner's CLI, as the skill
  does: a `bin/wuwei` that is not the workspace launcher is checked like any other program,
  so its `--file` operand under `.wuwei/days/` (now protected) is refused.
