# Tasks: a launch the planner makes itself is registered

**Input**: `specs/660-register-own-launch/spec.md`, `specs/660-register-own-launch/plan.md`

**Tests**: required (constitution IV). Each behaviour's test task comes before its
implementation task; run the test and see it fail for the expected reason before the code.
Launch tests build payloads in-process on the `launch` and `day` fixtures of
`tests/test_agent_launch.py` and `tests/test_brief.py` (set a posture with
`[security]\nposture = "..."` appended to the fixture's `config.toml`; patch
`agent_launch.free_memory` as the existing tests do). WUWEI's prompt for a logged brief is
`brief.launch_prompt(<brief>, security.agent_path(root, role), root=root)`.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Shared marker reader

- [X] T001 [US1] In `tests/test_brief.py`, test `brief.reference`: marker on line 1, on line
  3 after a note, absent (None), two marker lines (the first path), a line that only contains
  the marker mid-line (None). Test `brief.transcript_reference` on a transcript whose first
  user message is a note paragraph followed by the marker line: it returns the path. Run;
  fails (AttributeError, and None for the transcript).
- [X] T002 [US1] In `cli/wuwei/brief.py`, add `reference` and make `transcript_reference`
  use it per user message (plan.md). T001 passes.

## Phase 2: User Story 1, a planner note keeps the launch registered (P1)

### Tests first

- [X] T003 [US1] In `tests/test_agent_launch.py`, parametrize on a logged gate brief:
  WUWEI's prompt plus `\n\nPlanner note: watch the cache.` (appended), the note plus
  `\n\n` plus WUWEI's prompt (prepended), a prompt the planner wrote with the marker line in
  the middle, and the bare WUWEI prompt. Each returns `(0, '')`, registers seat `gate`, and
  its `planner_note` is `Planner note: watch the cache.`, the planner's prompt without the marker
  line, and absent for the bare prompt. One more case: a note of 600 characters with a
  credential-shaped token is redacted and cut to 500. Run; prepended and middle fail
  (refused), appended fails (no `planner_note`).
- [X] T004 [US1] In `tests/test_agent_launch.py`, with `brief.launch_prompt` patched to raise
  `ValueError`, an appended-note launch still returns `(0, '')` and its note is the prompt
  without the marker line. Run; fails.
- [X] T005 [US1] In `tests/test_agent_launch.py`, update `test_guard_table`: `nested-marker`
  now expects `(0, '')`. Run; fails.
- [X] T006 [US1] In `tests/test_agent_launch.py`, a seat registered from a prepended-note
  prompt: its SubagentStop (transcript first user message is that prompt, `agent_type`
  `sentinel-arch`) stops seat `gate` through `stopping_seat` (status `stopped`, no
  `seat stop unmatched`). Run; fails (unmatched).
- [X] T007 [US1] In `tests/test_why.py`, an item whose day holds a `seat launched` event for a
  seat with a `planner_note` prints `seat <name> (<role>): planner note: <note>` in
  `wuwei why <item>`; a seat with no note adds no line (the existing chain tests stay
  unchanged). Run; fails.

### Implementation

- [X] T008 [US1] In `cli/wuwei/guards/agent_launch.py` `_check`, read the marker with
  `brief.reference` (plan.md step 2; the None branch arrives in T016). T005 and T006 pass.
- [X] T009 [US1] In `cli/wuwei/guards/agent_launch.py`, add `_note` and store `planner_note` on the
  seat in `reserve` (plan.md steps 3 and 4). T003 and T004 pass.
- [X] T010 [US1] In `cli/wuwei/commands/why.py`, add the `seat` group and its line for a noted
  seat (plan.md). T007 passes.

## Phase 3: User Story 2, a launch without a marker is never silent (P1)

### Tests first

- [X] T011 [US2] In `tests/test_agent_launch.py`, under observe and guarded, a
  `wuwei:sentinel-arch` launch with no marker, description `Gate X` and a prompt of its own:
  returns exit 1, the reason starts with `unbriefed launch registered as adhoc seat adhoc-1
  for X` and names `bin/wuwei brief sentinel-arch X`; seat `adhoc-1` has `role adhoc`,
  `item X`, `label sentinel-arch`, `type wuwei:sentinel-arch`, `prompt_sha256`, status
  `running`; the last event is `seat launched` with `item X`. With no item named, `item` is
  `adhoc-1`, the reason reads `for no item of today's plan` and names
  `bin/wuwei brief sentinel-arch <item>`. With two items named, the same as none. Run; fails
  (refused, no seat).
- [X] T012 [US2] In `tests/test_agent_launch.py`, under strict the same launch returns exit 1
  naming `bin/wuwei brief sentinel-arch X`, writes no seat and no event, and a
  `seat start --adhoc` record of that prompt does not change it. Run; fails (reason text).
- [X] T013 [US2] In `tests/test_agent_launch.py`, every `brief.Refused` from `check` starts
  with `seat not registered: ` (an unlogged brief path and the second-opinion case); update
  the exact assertion at line 542. Run; fails.
- [X] T014 [US2] In `tests/test_posture.py`, with `hook_call` and `fixed('agent_launch', 1,
  'launch reason')` under guarded: exit 0, stdout is one JSON line whose
  `hookSpecificOutput.additionalContext` is `launch reason` plus the `posture: seats = warn`
  line, and a `guard.would_refuse` event is recorded; the same with `fixed('outward', 1, ...)`
  prints nothing to stdout; with the agent_launch refusal plus `fixed('deploy', 2, ...)` the
  call is denied with the deploy reason only (one JSON object); under strict the
  agent_launch refusal is denied as today. Run; the first case fails (empty stdout).
- [X] T015 [US2] In `tests/test_agent_launch.py`, an unbriefed seat's SubagentStop
  (`agent_type wuwei:sentinel-arch`, transcript first user message is the launch prompt, no
  marker) stops `adhoc-1` and returns `(0, '')`; a typed stop whose transcript file is
  missing still records `seat stop unmatched` (today's path). In `tests/test_traces.py` (or
  beside the #676 binding test), a PostToolUse with `agent_id` and `agent_type
  wuwei:sentinel-arch` from that subagent binds its session to `adhoc-1`. Run; the stop fails
  (unmatched); the trace binding may already pass (existing digest path), which confirms
  plan.md.

### Implementation

- [X] T016 [US2] In `cli/wuwei/guards/agent_launch.py`, add `_named_item`, `_unbriefed`,
  the `role` parameter of `_adhoc` and `UNBRIEFED`, and route `_check`'s None marker to
  `_unbriefed` (plan.md steps 5 to 7). T011 and T012 pass.
- [X] T017 [US2] In `cli/wuwei/guards/agent_launch.py` `check`, prefix `brief.Refused`
  reasons with `seat not registered: ` (plan.md step 1). T013 passes.
- [X] T018 [US2] In `cli/wuwei/commands/hook.py`, add the `warned` list to `posture` and print
  it from `run` (plan.md). T014 passes.
- [X] T019 [US2] In `cli/wuwei/guards/agent_launch.py`, add `_unbriefed_stop` and route it in
  `stop` (plan.md step 8). T015 passes.
- [X] T020 [US2] In `tests/test_why.py` first, then `cli/wuwei/commands/why.py`: an
  unbriefed seat for item X adds `seat adhoc-1 (wuwei:sentinel-arch, unbriefed): prompt:
  <first line>` to `wuwei why X`. Run the test, see it fail, then add the adhoc branch of the
  `seat` line.

## Phase 4: User Story 3, a finished seat gets the next round (P1)

- [X] T021 [US3] In `tests/test_dispatch.py` (beside
  `test_logged_gate_brief_becomes_launch_action`), log the arch gate brief, launch it through
  `agent_launch.check` with a note before WUWEI's prompt, stop the seat with
  `state.stop_seat`, then `dispatch.next_step('A')`: its `seats` hold no launch for that
  brief and its `commands` include `wuwei dispatch receive A arch arch-1`. A second case:
  an unbriefed seat running for A makes `dispatch.launch_set` leave A out (busy). Run on the
  T008 code: passes; run with T008 reverted locally: the first case fails (the launch is
  offered again). No production change in `dispatch.py`.

## Phase 5: Invariant, docs and the suite

- [X] T022 In `tests/test_invariants.py`, add `i47` (spec SC-002): per posture, a typed launch
  with no marker and a launch whose marker names an unlogged brief, each through
  `agent_launch.check` and levelled with `hook.posture(payload, rows, root, warned)`. Below
  strict: the no-marker case leaves a seat with its prompt digest and `warned` names
  `wuwei brief`; the unlogged case leaves `warned` naming `seat not registered`. Under
  strict: both are enforced refusals, the no-marker one naming `wuwei brief`, and no seat.
  Register it in `INVARIANTS` and `READS` (`'I47': (0,)`). Run; passes on the new code.
- [X] T023 In `docs/specs/2026-09-24-wuwei-design.md`, amend the 4.1 `Agent` launch row and
  add row I47 to 9.2 (plan.md, Docs).
- [X] T024 In `docs/site/recovery.md`, rewrite the Seat launch contract paragraph on the
  marker (plan.md, Docs).
- [X] T025 Run `python -m pytest -q` from the repository root with the task's interpreter;
  everything passes. Check every file written for em-dashes and emojis.
- [X] T026 Review fix round: a no-marker launch with no `state.json` is refused (exit 1, as
  before #660); the seat key is `planner_note` (`items.<item>.note` is generically
  writable); the refusal literal names its next step; the recovery paragraph splits its long
  sentence; the invariant is I47.

## Dependencies

- T002 before T008 and T019. T008 before T009 and T016. T016 before T020 and T021's second
  case. T017 and T018 before T022.
- Each implementation task needs its test task first (listed under it).
