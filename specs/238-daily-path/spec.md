# Feature Specification: The daily path runs without operator repairs

**Feature Branch**: `238-daily-path`

**Created**: 2026-09-30

**Status**: Draft

**Input**: GitHub issue #238, "fix(team): the daily path runs without operator repairs and
is documented as one path". Design spec sections 3.4, 4.2.1, 5.2, 5.3, 5.8 and 10.
Depends on #225 (merged on `main` as e9e7fd9). Evidence: the whole-system review of
2026-09-30, point 1.

## Evidence (v0.6.0 operator dry run, 2026-09-30, read against `main` after #225)

Reproduced read-only from the dry run's step log, its day `events.jsonl` and `state.json`,
and by reading the current code. #225 already removed the `runtime dispatch arch` alias
failure, the state-guard refusal of `runtime continue '<json>'`, the manual `raised` and
`merged` transitions for a raised item, and the unrouted `pr act` decision. What remains:

1. **Manual `gate -> fix`.** Step `dnext-fix` returned `{"action": "fix", "roles":
   ["quality"]}` and the operator had to run `state transition DIVIDE-1 fix` (step
   `trans-fix`, a `state.transition` event in the day log). Root cause:
   `cli/wuwei/dispatch.py` lines 101 to 103 return `fix` without moving the phase, and
   `skills/wuwei-plan/SKILL.md` line 48 tells the planner to transition by hand. The
   scripted day repeats the repair (`tests/test_e2e_day.py` line 34, `day.transition('fix')`).
   The operator then had to author a second builder brief with the worktree path and the
   finding copied from the verdict file (step `brief-builder2`), although the stopped
   builder's agent id is on the build record (`builds.DIVIDE-1.agent_id`) and
   `build.open_fix` (`cli/wuwei/commands/build.py` lines 157 to 208) already resumes a
   builder with measured feedback, but only from `raised` (line 180).
2. **Job JSON reconstruction for the delta.** Step `dnext-delta` returned only
   `{"action": "gates", "roles": ["quality"]}`. The operator had saved the output of the
   initial `runtime dispatch` to a scratch file and rebuilt the continuation from it
   (step `rt-continue2`, `runtime continue "$(cat .../rtd-quality.json)" ...`), then had to
   find the seat's agent id for Agent `resume`. Root cause: `cli/wuwei/dispatch.py` lines
   95 to 97 return role names only; nothing stores the job, although everything in it is
   derivable from state: the initial verdict record names its file (`gate-quality-1.md`,
   so the seat is `quality-1`), the seat record holds its brief and `agent_id`
   (`agent-quality-1`), and the prompt is `brief.launch_prompt` of that brief plus the
   feedback, exactly what `adapters/runtime/claude.py` `continue_job` returns.
3. **Initial gates need a low-level launch.** Gate launches go through
   `runtime dispatch <role> <brief> <worktree>` (steps `rtd-*`), a generic seat command the
   issue moves to recovery. `build next` already turns a logged builder brief into a
   `launch` action (`cli/wuwei/commands/build.py` lines 115 to 142); the gate flow has no
   equivalent.
4. **Merged but not merged.** `pr_actions.observe` (`cli/wuwei/pr_actions.py` lines 219 to
   222) moves only `raised` items to `merged`, and `state.PHASES` (`cli/wuwei/state.py`
   lines 31 and 32) has no `fix -> merged` or `delta -> merged`. After a post-PR fix round
   (`raised -> fix -> delta`) the owner can merge the PR; `pr state` then reports
   `merged` while `report` prints `## Merged` / `none` and the status line shows
   `delta 1/1`, the same disagreement as dry-run step `report-end`.
5. **Docs.** `docs/site/concepts.md` lines 11 and 58 call `/wuwei plan` orchestration
   "Planned"; `docs/site/security.md` line 50 calls the signed manifest, workspace
   integrity, prompt canary and honeytoken "planned" although `cli/wuwei/integrity.py` and
   `cli/wuwei/security.py` implement them. No page gives the owner one path through the
   day; `state transition`, `runtime dispatch` and `integrity reconfirm` sit beside daily
   commands.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The gate flow hands out every seat action (Priority: P1)

As the planner, after `build next` returns `done` I call `wuwei dispatch next <item>`. For
the initial round it tells me which gate briefs to write and, once written, returns a
`launch` action per brief in the builder action format with the exact `dispatch receive`
call. When it returns `fix` it has already moved the item to `fix` and opened the builder's
fix round, and gives me the exact `wuwei build next <item>` call. For the delta round it
returns a `continue` action per sentinel (resume id, prompt with feedback) and the exact
`dispatch receive ... --round delta` call. I never run `state transition`,
`runtime dispatch` or `runtime continue`, and never rebuild job JSON.

**Why this priority**: these are the two repairs left in the dry run and the reason a
planner needs an expert.

**Independent Test**: in process with the `tests/test_dispatch.py` fixture plus a
completed build record: FIX verdicts, `next_step`, then read the phase, the build record,
the returned `command`, and the `seats` actions.

**Acceptance Scenarios**:

1. **Given** an item in `gate` with all three initial verdicts and one FIX, **When**
   `dispatch next` runs, **Then** it returns `{"action": "fix", "roles": [...], "command":
   "wuwei build next <item>"}`, the item is in `fix`, the build record holds a ready
   `continue` action that resumes the stopped builder with feedback naming each FIX
   verdict file, and a second `dispatch next` returns the same result with no new write.
2. **Given** the item in `gate` with a logged, unlaunched gate brief for `arch`, **When**
   `dispatch next` runs, **Then** `seats` holds one `launch` action with `brief`,
   `worktree`, `runtime`, `agent_type` `wuwei:sentinel-arch`, the `launch_prompt` of that
   brief, and `receive` `wuwei dispatch receive <item> arch <name>`; after the seat is
   launched the entry is gone.
3. **Given** the item in `delta` after the fix build and the stopped initial quality seat
   with a recorded agent id, **When** `dispatch next` runs, **Then** `seats` holds one
   `continue` action with `resume` set to that agent id, the same brief's prompt followed
   by delta feedback naming the first verdict HEAD and verdict file, and `receive`
   `... quality <seat> --round delta`; once the continuation is launched the entry is gone.
4. **Given** a delta role whose initial seat has no recorded agent id, **When**
   `dispatch next` runs, **Then** the role is still listed in `roles` with no `seats`
   entry (a lost seat is a recovery case).

---

### User Story 2 - A merged PR is merged everywhere (Priority: P1)

When `pr state`, `pr act` or the watch observes a linked PR merged, the item is `merged` in
the same write, whether it was `raised` or in a post-PR `fix` or `delta`. `report` lists it
under Merged with its PR, and the status line counts it as merged.

**Why this priority**: the owner must not recheck the host; "Merged: none" after a verified
merge is the failure the review names.

**Independent Test**: the `tests/test_pr_actions.py` `linked` fixture with the item in
`delta`, the fake PR merged, `pr state`, then `report.build` and `status --line`.

**Acceptance Scenarios**:

1. **Given** a merged PR observed by `pr state` for an item in `raised`, **When** `report`
   and `status --line` run, **Then** the report's Merged section lists
   `- <item> (<ref>)` and the status line shows `merged 1/<cap>` and no other phase.
2. **Given** the same for an item in `fix` or `delta`, **Then** the same outcome, and the
   `pr.action` event carries `phase_changes: {<item>: merged}`.
3. **Given** a PR that is not merged, **Then** no phase moves.

---

### User Story 3 - One documented daily path, tested (Priority: P1)

A solo owner reads one page, `docs/site/daily.md`: signed install, configuration,
`/wuwei plan` and the morning gate, progress through the day (status line, nudges, the
planner's `build next` and `dispatch next` loop, PR raise and `pr state`), owner decisions
in a host terminal, and close. `state transition`, `runtime dispatch`, `runtime continue`
and `integrity reconfirm` are on `docs/site/recovery.md`, named as recovery, not daily use.

**Why this priority**: the review's "worked when": one item completes with no manual
`state transition`, role translation, undocumented command or source-code consultation.

**Independent Test**: the fourth dry run: a scripted solo operator (the existing
`tests/fakes/day.py` driver) completes one item from plan to merged and close, and the
test checks every command it ran against the daily page.

**Acceptance Scenarios**:

1. **Given** a fresh workspace and only the daily path page, **When** the scripted solo
   operator plans, approves, builds, gates with one FIX, runs the fix and delta rounds,
   raises, observes the merge and closes, **Then** it never runs `state transition` or
   any `runtime` command, every CLI command it ran is
   named on `docs/site/daily.md`, and the phase sequence from `phase_changes` is
   `implement, gate, fix, delta, raised, merged`. Its findings are recorded in
   `specs/238-daily-path/quickstart.md`.
2. **Given** that run after `pr state` observes the merge, **When** `report` and
   `status --line` run, **Then** Merged lists the item and the status line agrees.
3. **Given** the docs, **When** searched, **Then** no line says "planned" about the
   manifest, canaries or honeytoken, and `concepts.md` has no "Planned" for `/wuwei plan`.

### Edge Cases

- `dispatch next` in `fix` (fix already opened) returns the same `fix` result and does not
  call `open_fix` again; `build next` keeps returning the recorded builder action.
- A FIX from `gate` whose build record is missing or unfinished: `open_fix` raises and
  `dispatch next` exits 2 with the reason (fail closed); the phase does not move.
- The fix round budget stays one: `open_fix` sets `fix_rounds` 1 and `pr raise`
  (`delta -> raised`) resets it, so one post-PR fix round remains available, as today.
- A Claude builder with no recorded agent id (or a Codex builder with no job) gets a
  `launch` of a feedback brief named `<item>-gate-fix`, so it never collides with the
  post-PR `<item>-pr-fix` brief.
- A gate brief whose seat was already launched gets no new launch action; a used brief
  can never be offered twice (the launch guard would refuse it anyway).
- Two logged unlaunched briefs for one role: the latest is offered, as `build next` picks
  the latest builder brief.
- A PR merged while a post-PR fix builder is still running: the item moves to `merged`;
  the later SubagentStop and `build check` record results and move no phase (the
  `implement/fix` map in `complete_checks` has no entry for `merged`).
- Items in `parked`, `escalated`, `planned`, `spec`, `implement` or `gate` whose linked PR
  merges keep their phase (see Assumptions).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: When `dispatch next` decides `fix` from the `gate` phase, it MUST open the fix
  round through `build.open_fix` in the same call: the item moves `gate -> fix` and the
  build record gets the resume (or feedback-brief launch) action. The feedback names each
  FIX verdict file and asks for its blocking findings only.
- **FR-002**: Every `fix` result (from `gate` or `fix`) MUST carry
  `"command": "wuwei build next <item>"`.
- **FR-003**: `build.open_fix` MUST accept `gate` as well as `raised`; everything else in it
  is unchanged.
- **FR-004**: Every `gates` result MUST carry `seats`, a list of builder-format actions:
  a `launch` for each missing initial-round role with a logged gate brief not yet
  launched, and a `continue` for each missing delta-round role whose initial seat is
  stopped with a recorded agent id and has not been continued yet. Each action carries `receive`,
  the exact `wuwei dispatch receive` call (with `--round delta` for the delta).
- **FR-005**: `launch` and `continue` actions MUST come from one shared formatter, the one
  `build next` uses for the builder launch, so prompt, agent type and runtime cannot drift.
- **FR-006**: A merged PR observation (`pr_actions.observe`) MUST move each linked item in
  `raised`, `fix` or `delta` to `merged` in the same write; `state.PHASES` MUST allow
  `fix -> merged` and `delta -> merged`.
- **FR-007**: `docs/site/daily.md` MUST give one solo-owner path: signed install,
  configuration, plan approval, progress, owner decisions, close. It MUST NOT name
  `state transition`, `runtime dispatch`, `runtime continue` or `integrity reconfirm`.
- **FR-008**: `docs/site/recovery.md` MUST name `state transition`, `runtime dispatch`,
  `runtime continue` and `integrity reconfirm` as recovery, with when to use each.
- **FR-009**: `concepts.md` and `security.md` MUST NOT call implemented features planned:
  `/wuwei plan`, the signed manifest, workspace integrity, prompt canary and honeytoken.
- **FR-010**: The planner skill and charter MUST follow the new actions: no manual `fix`
  transition, gates launched and continued from `seats`.

### Key Entities

- **`dispatch next` result**: `gates` gains `seats` (list of actions); `fix` gains
  `command`. `raise` and `escalate` are unchanged.
- **Gate seat action**: `{action: launch|continue, brief, worktree, runtime, agent_type,
  prompt, receive}`; `continue` adds `resume` and `feedback`. Same keys as the builder
  `launch` from `build next`, plus `receive`.
- **Item phase**: `fix` and `delta` gain `merged` as a legal next phase.

## Success Criteria *(mandatory)*

- **SC-001**: The three acceptance scenarios of issue #238 pass as automated tests.
- **SC-002**: The scripted day (`tests/test_e2e_day.py`) runs with no `state transition`
  and no `runtime` call, and the new solo daily-path run uses only commands named on
  `docs/site/daily.md`.
- **SC-003**: The full suite passes. Existing tests edited: the scripted day and its
  driver, exact-dict asserts on `dispatch next` in `tests/test_dispatch.py`, and the
  transition-edge table in `tests/test_state.py` (for `fix`/`delta -> merged`).
- **SC-004**: No new module, state key, event kind, config key or dependency.

## Assumptions

- "The exact `runtime continue` call" is satisfied by returning what that call prints for
  the Claude runtime (prompt, agent type, brief, worktree) plus the `resume` id, so the
  planner makes no intermediate call. The prompt comes from the same `launch_prompt` the
  Claude adapter uses. Codex-runtime sentinels are out of scope: nothing stores their job
  handle, so they keep `runtime continue` with the job from `runtime dispatch` (recovery
  page). Claude subagents are the primary runtime (spec 5.3).
- The pre-PR fix round resumes the stopped builder with the FIX findings as feedback
  (reusing `open_fix`) instead of a second planner-written brief. Spec 5.3 asks for the
  fix round and one delta; a resumed builder keeps its context, and `open_fix` already
  implements this for the post-PR round. The feedback names the verdict files; the builder
  reads them (as the dry-run fix brief asked).
- Initial gate briefs stay planner-written (`wuwei brief <gate role> ... --gate`): the body
  is the planner's judgement. `dispatch next` turns the logged brief into the launch, as
  `build next` does for the builder brief.
- "Not yet launched" and "not yet continued" are read from the seat record the launch guard
  writes: an initial gate brief is offered while no seat of its name exists; a delta
  continuation is offered while the stopped seat's `head` is still the first verdict's
  HEAD (every reservation, continuation included, records the worktree HEAD). In the dry
  run `quality-1` ended at `f1feffb` after its continuation, against a first verdict at
  `4e732e5`.
- A rejected or unmeasured verdict that must return to its seat, and a lost sentinel that
  needs a fresh seat, are recovery cases: `runtime continue` or a fresh brief, on the
  recovery page.
- Lead, shepherd and steward launches stay as the planner skill describes them (the
  steward through `steward run`); they are planner internals, not owner commands, so the
  daily page does not name `runtime dispatch`. The recovery page states that the planner
  uses it for those seats.
- Only `raised`, `fix` and `delta` move to `merged` on observation: those are the phases a
  raised PR's item can be in. A claimed PR whose item is earlier in the lifecycle keeps
  its phase (as #225 decided); widening `merged` to every phase would make a manual
  `planned -> merged` legal. Close already requires merge evidence for a merged phase.
- The post-PR return from `delta` to `raised` after a post-PR fix round (the arch-delta
  flow `pr act` names) is not part of this issue; the merge move above keeps report and
  status right if the owner merges during that round.
- The fourth dry run is the scripted solo run in `tests/test_e2e_day.py` on the existing
  driver (`tests/fakes/day.py`), per the orchestrator notes; no third driver.
  `scripts/headless_e2e.py` keeps its prompt (its scenario has no fix round).
- `docs/site/charter-overrides.md` line 15 ("Planned: the full steward-led daily proposal
  cycle") is outside this issue's list (manifests, canaries, `/wuwei plan`) and stays.
- No config key is added, so `templates/workspace/config.toml` and
  `docs/site/configuration.md` are unchanged.
