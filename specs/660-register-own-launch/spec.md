# Feature Specification: a launch the planner makes itself is registered

**Feature Branch**: `660-register-own-launch`
**Created**: 2026-10-10
**Status**: Draft
**Input**: GitHub issue #660 (owner, 2026-10-10, items 17, 31 and 39): a seat launched with a
prompt the planner wrote was never registered, and when it finished WUWEI offered to launch
the item again from scratch. A second launch with WUWEI's prompt plus a note also did not
register, while continue rounds with appended notes did. The planner relaunched with the bare
prompt and lost its notes. Item 39: a builder launch for an item of the second configured
repository was not recorded and nothing said so. Deliver: the launch guard registers a seat
when the prompt carries the brief marker anywhere; the surrounding text is the seat's planner
note and `wuwei why` shows it; a launch with no marker registers as an unbriefed seat with a
warning naming the brief command below strict, and strict refuses it; every launch the guard
does not register prints a warning naming the reason and the command that registers it;
`dispatch` never offers a fresh launch for an item with a seat it registered.

## Root cause

Reproduced in-process on a test day (scratch test, not in the repository): a gate brief
logged with `wuwei brief sentinel-arch X gate --worktree tree`, then the real
`wuwei hook PreToolUse` on an `Agent` payload of type `wuwei:sentinel-arch`.

- `cli/wuwei/guards/agent_launch.py:125-129` (`_check`) requires the marker to be the first
  line: `inputs['prompt'].startswith(brief.REFERENCE_PREFIX)`, then `splitlines()[0]`. A
  prompt with a planner note before the marker line, or a prompt the planner wrote that
  quotes the marker lower down, is refused with
  `no logged brief reference at start of Agent prompt`. A note after WUWEI's prompt passes,
  which is why continue rounds with appended feedback registered.
- `cli/wuwei/workspace.py:42-44`: the `seats` area is `warn` under observe and guarded (the
  default). `cli/wuwei/commands/hook.py:305-322` (`posture`) turns a `warn` refusal into a
  `guard.would_refuse` event and lets the call through; `hook.run` (`hook.py:119-139`) prints
  only enforced refusals. Measured under guarded with a note before the marker: exit 0, empty
  stdout and stderr, `seats` empty, one `guard.would_refuse` event. The Agent ran
  unregistered and the planner was told nothing. Under strict the same launch is denied with
  the first-line message.
- Because nothing registered, `dispatch._seats` (`cli/wuwei/dispatch.py:537`) still finds the
  logged gate brief unused and offers its launch again, and `build.next_action`
  (`cli/wuwei/commands/build.py:141`) keeps returning the ready build's `launch` action (the
  record is bound only by `build.started` inside a registered launch). That is the "launch the
  item again from scratch" the owner saw.
- `cli/wuwei/brief.py:158-163` (`transcript_reference`) has the same first-line rule, so even
  a registered seat whose prompt did not start with the marker could not bind its stop or its
  traces.
- A typed launch with no marker at all is refused the same way, so below strict it also runs
  unregistered and silent.
- Item 39 (second repository) was not reproducible from the code: no orchestrator notes file
  or dry-run workspace was available, and `_check` has no repository-specific branch. Every
  launch refusal and every could-not-run below strict goes through the same silent `warn`
  path above, so whatever the reason was there, it was swallowed there.

## Clarifications

### Session 2026-10-10

Answered with the recommendation (AGENTS.md: no clarifying questions).

- Q: What is the marker? A: the existing line `WUWEI brief: <relative brief path>`
  (`brief.REFERENCE_PREFIX`), which `brief.launch_prompt` writes and every stop, trace and
  scratch binding reads. The issue's `wuwei-brief: <item> <role> <id>` describes the same
  thing: the path names the day and the brief name (the seat id), and the logged
  `brief written` event gives item and role. The format does not change.
- Q: Where may the marker be? A: on any line of the prompt, at the start of that line. The
  first such line is the reference. All the existing checks (logged brief, unchanged hash,
  role, name, unused, fresh evidence, capacity) still apply to it.
- Q: What is the planner note? A: the prompt without WUWEI's own launch prompt for that brief
  (`brief.launch_prompt(<brief>, security.agent_path(root, role), root=root)`), stripped.
  When the prompt does not contain WUWEI's prompt verbatim (the planner wrote its own), the
  note is the prompt without the marker line. It is redacted, capped at 500 characters and
  stored on the seat as `planner_note`; an empty note is not stored.
- Q: What does `wuwei why <item>` show? A: one line per `seat launched` event of the item whose
  seat has a note or is an adhoc seat:
  `seat <name> (<role>): planner note: <note>` or
  `seat <name> (<type>, unbriefed): prompt: <first line>`.
- Q: What is an unbriefed seat? A: a typed launch (`wuwei:<role>` or a charter name) with no
  marker, registered below strict through the existing adhoc path (#676): `role: adhoc`,
  `type` the Agent type (for example `wuwei:builder`), `label` the WUWEI role, `item` the one
  item of today's plan named as a whole word in the Agent `name`, `description` or `prompt`,
  else the seat name, plus the prompt's first line and digest. It is named `adhoc-<n>` like
  any adhoc seat, so its traces bind by digest, its stop is recorded, `why adhoc` lists it,
  and the consumers that skip adhoc seats (scanner item seats, watch brief check,
  `seat stop --verdict`) already skip it.
- Q: What does the planner see for an unbriefed launch? A: the guard registers the seat, then
  returns exit 1 with a warning of this shape:
  `unbriefed launch registered as adhoc seat <name> for <item>: the Agent prompt has no WUWEI brief: line, so WUWEI cannot receive or continue it; write the brief with bin/wuwei brief <role> <item> <name>, then launch with the prompt bin/wuwei build next <item> or bin/wuwei dispatch next <item> returns`
  (when no item was named, the commands keep the literal `<item>` and `for <item>` reads
  `for no item of today's plan`). Under `warn` the hook records it as
  `guard.would_refuse` and shows it to the session (below).
- Q: Under strict? A: a typed launch with no marker is refused (exit 1) before anything is
  written, naming `bin/wuwei brief <role> <item> <name>` the same way. `seat start --adhoc`
  does not unlock a typed launch.
- Q: How does a warning reach the planner? A: a PreToolUse refusal the posture levels to
  `warn` for the `agent_launch` guard is printed as
  `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": ...}}` (the
  reason and its posture line) when no other guard refuses the call. The event is still
  recorded as today. Other guards' warnings are unchanged (record only).
- Q: How does a refusal say the seat was not registered? A: `agent_launch.check` prefixes every
  `brief.Refused` reason with `seat not registered: `. Under strict that is equally true.
- Q: How does an unbriefed seat stop? A: a typed SubagentStop whose readable transcript names
  no brief goes to the adhoc stop (`_stop_adhoc`), which binds by the prompt digest. An
  unreadable transcript keeps today's path.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - a launch with WUWEI's prompt and a planner note registers (Priority: P1)

The planner adds a paragraph to the prompt WUWEI gave it, before or after it, and launches.
The seat registers as if the prompt were bare, the note is kept with the seat, and
`wuwei why <item>` shows it.

**Why this priority**: the owner's main defect: notes were lost or the launch went
unregistered.

**Independent Test**: log a gate brief, run the launch guard on WUWEI's prompt plus an
appended paragraph, and on a paragraph plus WUWEI's prompt; assert the seat, its `planner_note` and
the `why` line.

**Acceptance Scenarios**:

1. **Given** WUWEI's prompt plus an appended paragraph, **When** the planner launches,
   **Then** the seat registers (exit 0) and `wuwei why <item>` shows the paragraph as the
   planner note.
2. **Given** a paragraph followed by WUWEI's prompt, **Then** the same.
3. **Given** a prompt the planner wrote that carries the marker line somewhere, **Then** the
   seat registers and its note is the prompt without the marker line.
4. **Given** the bare WUWEI prompt, **Then** the seat registers with no note, as before.
5. **Given** a registered seat whose prompt did not start with the marker, **When** its
   SubagentStop fires, **Then** the seat stops through its brief, and its tool calls bind to it.

### User Story 2 - a launch without a marker is never silent (Priority: P1)

The planner launches a WUWEI role with a prompt of its own and no marker. Under observe or
guarded the seat registers as unbriefed and the planner is told how to brief it; under strict
the launch is refused with the brief command. Any other launch refusal below strict tells the
planner the seat was not registered and why.

**Why this priority**: the issue's second acceptance line and the owner's item 39 rule: a
silent non-registration is a defect.

**Independent Test**: under observe, run the launch guard and the hook on a typed launch with
no marker; assert the adhoc seat, its item and label, the exit 1 warning and the printed
context; under strict assert the refusal and no seat.

**Acceptance Scenarios**:

1. **Given** a prompt with no marker under observe, **When** the planner launches
   `wuwei:sentinel-arch` naming item X, **Then** an adhoc seat registers with `item: X`,
   `label: sentinel-arch`, `type: wuwei:sentinel-arch`, and the hook exits 0 with additional
   context naming `bin/wuwei brief sentinel-arch X`.
2. **Given** the same under strict, **Then** the hook denies the launch with a reason naming
   `bin/wuwei brief sentinel-arch X`, and no seat is written.
3. **Given** no item of today's plan named in the launch, **Then** the seat registers with its
   own name as item and the warning names `bin/wuwei brief <role> <item>`.
4. **Given** guarded and a launch refused for any other reason (brief modified, CAP, memory,
   brief already used, a read that failed), **Then** the call passes and the hook's
   additional context names the reason and its fix; a refusal reads `seat not registered: `.
5. **Given** an unbriefed seat, **When** its SubagentStop fires, **Then** it is stopped.

### User Story 3 - a finished seat gets the next round, not a fresh launch (Priority: P1)

Once a launch with a note registers, the item's next step follows the seat as for any seat.

**Why this priority**: the issue's third acceptance line; the visible symptom.

**Independent Test**: a gate item with a logged gate brief; launch it with a planner note
before WUWEI's prompt, stop the seat, run `dispatch.next_step`.

**Acceptance Scenarios**:

1. **Given** a finished seat launched with a planner note, **When** `dispatch next <item>`
   runs, **Then** it offers `wuwei dispatch receive <item> <role> <seat>` and no launch action
   for that brief.
2. **Given** an unbriefed seat running for item X, **When** the launch set is built, **Then**
   X is busy and not offered (existing busy rule; the seat's `item` is X).

### Edge Cases

- Two different marker lines in one prompt: the first one binds; the second is part of the
  note. (`ponytail:` no ambiguity refusal; the logged-brief checks still apply to the first.)
- A marker line whose path fails validation (absolute, `..`, not under today's briefs):
  exit 2 as today.
- WUWEI's launch prompt cannot be regenerated (brief or config unreadable at that moment):
  the note falls back to the prompt without the marker line; a launch is never refused over
  its note.
- A continue round: WUWEI's appended feedback is outside the launch prompt, so it is part of
  the note. (`ponytail:` ceiling; subtract the round's feedback if the owner finds it noisy.)
- Config changed between `build next` and the launch, so the regenerated prompt differs: the
  note is the whole prompt without the marker line.
- A typed launch with no marker before the morning plan (no `state.json`): exit 1, refused
  naming `bin/wuwei brief <role> <item> <name>`, as today.
- An untyped launch (#676) is unchanged: it registers as adhoc with exit 0 and no warning;
  before the morning plan it stays unregistered and silent (#676 decision).
- Another guard denies the same Agent call after this guard registered the seat: the seat
  stays `running`, as a brief seat does in the same case; `seat stop <name> --unmeasured`
  clears it (unchanged).
- A sentinel launched unbriefed still meets the verdict lint at its stop, which needs a brief
  seat (unchanged; see Deferred).
- `security.areas.seats = "off"`: refusals are dropped as today, so nothing is printed.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `brief.reference(text)` MUST return the path of the first line of `text` that
  starts with `REFERENCE_PREFIX`, else None; `brief.transcript_reference` MUST use it on each
  user message.
- **FR-002**: The launch guard MUST bind a typed launch through `brief.reference(prompt)`,
  keeping every existing check on the referenced brief.
- **FR-003**: A registered brief seat MUST carry `planner_note` (redacted, at most 500 characters)
  when the prompt holds text beyond WUWEI's launch prompt for its brief, as defined in
  Clarifications.
- **FR-004**: `wuwei why <item>` MUST show a line per seat launch of the item whose seat has a
  note or is adhoc, with the note or the prompt line.
- **FR-005**: A typed launch with no marker MUST, when the `seats` level is `block`, be
  refused (exit 1) naming `bin/wuwei brief <role> <item>`; otherwise it MUST be registered as
  an adhoc seat with the item and label in Clarifications and return exit 1 with the
  unbriefed warning.
- **FR-006**: `agent_launch.check` MUST prefix each `brief.Refused` reason with
  `seat not registered: `.
- **FR-007**: The hook MUST print each `agent_launch` refusal it levels to `warn` as
  PreToolUse `additionalContext` (reason and posture line) when it lets the call through; the
  `guard.would_refuse` record is unchanged; other guards are unchanged.
- **FR-008**: A typed SubagentStop whose readable transcript names no brief MUST stop its
  adhoc seat through the adhoc stop path.
- **FR-009**: Design spec 4.1 (Agent launch row) and 9.2 (a new invariant) and
  `docs/site/recovery.md` (seat launch contract) MUST describe the marker anywhere, the note,
  unbriefed seats and the warnings.

## Success Criteria *(mandatory)*

- **SC-001**: Tests drive each acceptance scenario of US1, US2 and US3 through the guard, the
  hook, `why` and `dispatch.next_step`.
- **SC-002**: The invariant walk covers: below strict, every typed launch inside a day either
  registers a seat or prints a warning naming its reason; under strict a launch with no marker
  is refused naming `wuwei brief`.
- **SC-003**: The full suite passes.

## Assumptions

- The orchestrator notes file `notes/660-full.md` named by the task does not exist, and no
  dry-run workspace was named; the reproduction above was run in-process on a test day.
- The brief command in the warnings is the real CLI form
  `bin/wuwei brief <role> <item> <name>`; the issue's `wuwei brief <item> <role>` is read as
  that command.
- An unbriefed seat is an adhoc seat (role `adhoc`) with the WUWEI role as its label, not a
  seat of that role: every consumer that needs a brief already skips adhoc seats, and it never
  counts as a builder for CAP or as a live builder for gate readiness. WUWEI has no record of
  its result, so after it finishes the item's next step is the briefed launch the warning
  names. "Never offers a fresh launch for a seat it registered" holds for brief seats, and
  for an unbriefed seat while it runs (launch-set busy rule).
- "Unknown item" in item 39 does not leave a launch unregistered: it registers with its own
  name as item and the warning says so.
- The owner's "checkout not under a configured repository" case, when the session cwd is
  outside the workspace and its repositories, stays outside the guards' scope (design 9.1):
  the guard cannot know a workspace is meant. Inside the scope every non-registration now
  warns.
- Claude Code shows a PreToolUse hook's `additionalContext` to the model when the call
  proceeds; the hook already uses the same field for SessionStart.
- The new invariant takes I47, the id the orchestrator reserved for this item, so
  sibling branches do not collide. Renumber at merge if it is taken.

## Deferred

- The verdict lint at a sentinel's SubagentStop (`guards/verdict.py:82-83`) needs a brief
  seat; an unbriefed sentinel's stop still fails it as today. A follow-up can skip the lint
  for adhoc seats.
- Warnings of other areas (`outward`, `publish`, `integrity` under observe) stay
  record-only; surfacing them is a separate posture decision.
