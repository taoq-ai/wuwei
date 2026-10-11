# Feature Specification: a launch whose brief does not exist is refused, and a refused brief command never leaves a launch that points at nothing

**Feature Branch**: `725-brief-must-exist`
**Created**: 2026-10-10
**Status**: Draft
**Input**: GitHub issue #725 (owner, 2026-10-10, item 51): a `brief` call was refused, but
the Agent launch in the same batch still started, pointing at a brief file that did not
exist; the owner stopped the agent by hand. Deliver: the agent-launch guard checks that the
brief file the prompt names exists; otherwise it refuses the launch below strict with
"brief <path> does not exist; run bin/wuwei brief ... first" (exit 2, a records-floor case:
a seat without a brief leaves no record), and registers nothing. Companion to #660
(registration by marker).

## Root cause

Reproduced from the owner's day record (read-only) and in process against a scratch
workspace.

The owner's workspace runs `security.posture = "observe"`. Its day events show, in one
batch, the `bin/wuwei brief` call refused by the deploy guard (`hook.refusal`, an
unaccounted git mention), then for the Agent launch in the same batch:

```text
guard.would_refuse  guard=agent_launch area=seats level=warn posture=observe exit=1
reason="no brief logged for this launch; write the brief first with bin/wuwei brief, ..."
```

and no `seat launched` event for it: the agent ran with no brief and no seat record.

In process, a launch naming `.wuwei/days/<day>/briefs/never.md` (never written) gives
`agent_launch.check` = `(1, 'no brief logged for this launch; ...')` in every posture; the
whole hook exits 0 under `observe` (the launch runs) and denies only under `strict`
(`posture: seats = block`). Under `guarded` the seats area is also `warn`
(`cli/wuwei/workspace.py:43` to `46`), so the launch runs there too.

Why:

1. `cli/wuwei/guards/agent_launch.py:131` builds `path = root / relative` and never asks
   whether the file exists. A brief never written falls to the logged-event lookup and is
   refused at line 146 as `brief.Refused` (exit 1). A brief logged and then deleted reaches
   `path.read_bytes()` at line 158 and raises `FileNotFoundError`, which `check` turns into
   `agent launch could not run: [Errno 2] ...` (line 27, exit 2). Neither reason names the
   missing file or the command that writes it.
2. Every `agent_launch.check` refusal is levelled by the `seats` area
   (`cli/wuwei/guards/__init__.py:39`), which is `warn` under `observe` and `guarded`. The
   hook's `posture` (`cli/wuwei/commands/hook.py:249` to `320`) then records
   `guard.would_refuse` and lets the call through.
3. The records floor list `RECORDS_FLOOR` (`cli/wuwei/guards/__init__.py:65`) only rewrites
   the posture line (`cli/wuwei/commands/hook.py:279` to `280`); it never sets the level to
   block. Its two current members come from owner-only checks (`outward.check_tier`, `pr`),
   which already block, so the gap never showed. A records-floor reason from a guard in a
   `warn` area would be labelled `block (floor)` and still pass.

Nothing is registered on these refusals today (the refusal is raised before `reserve`), so
"registers nothing" already holds; the defect is that the launch is not stopped.

## Clarifications

### Session 2026-10-10

Answered with the recommendation (AGENTS.md: no clarifying questions).

- Q: Which cases are the new floor refusal? A: Exactly one: the brief file the prompt names
  does not exist, whether it was never written (the owner's case: the `brief` call was
  refused) or was logged and later removed. The other launch refusals (no logged brief for
  an existing file, role or name mismatch, modified brief, capacity, memory, dirty tree)
  keep the `seats` level unchanged.
- Q: Where does the check sit? A: In `agent_launch._check`, right after the brief path is
  validated (so a traversal or a path outside today's `briefs/` stays `invalid brief path`)
  and before the events are read.
- Q: What does the refusal say? A: `brief <path> does not exist; run bin/wuwei brief <role>
  <item> <name> first`, with `<path>` the normalised workspace-relative path and `<role>`
  the launch's role filled in; `<item>` and `<name>` stay placeholders. The issue's text
  reads `bin/wuwei brief <item> <role>`, but the command's argument order is `ROLE ITEM NAME`
  (`cli/wuwei/commands/brief.py:11`), so the message follows the command. The name is not
  filled with the missing file's stem: when that brief was logged and then removed, writing
  it again under the same name gives two `brief written` events for one path, which the
  guard refuses as ambiguous.
- Q: How does it block below strict? A: Through the existing records floor: the reason's
  constant prefix joins `RECORDS_FLOOR`, and the hook's posture sets the level to `block`
  for every `RECORDS_FLOOR` reason, not only its line. That makes the existing label true
  for every member; the two current members already block, so their behaviour is unchanged.
- Q: Exit code? A: 2, as the issue asks (a seat without a brief leaves no record; the launch
  could not run).
- Q: What about #660 (registration by marker)? A: Not on `main`; nothing here depends on it.
  This feature only refuses before any registration.

## User Scenarios and Testing

### User Story 1 - a launch naming a missing brief never starts (Priority: P1)

The planner batches `bin/wuwei brief ...` and the Agent launch. The brief call is refused, so
the brief file is never written. The launch is refused in every posture with the brief
command to run, and no seat is registered, so no agent runs with nothing behind it.

**Why this priority**: it is the owner's reported defect.

**Independent Test**: in process, the `launch` fixture of `tests/test_agent_launch.py`, the
brief file removed or never written; `agent_launch.check` and the whole PreToolUse hook
under `observe`, `guarded` and `strict`.

**Acceptance Scenarios**:

1. **Given** an Agent launch for a WUWEI role whose prompt names a brief path that does not
   exist, **When** the PreToolUse hook runs under `observe`, `guarded` or `strict`, **Then**
   the launch is denied (hook exit 2), the reason is `brief <path> does not exist; run
   bin/wuwei brief <role> <item> <name> first` followed by `posture: records = block (floor;
   no setting lowers it)`, `agent_launch.check` returns exit 2, and no seat and no
   `seat launched` event is recorded.
2. **Given** a brief that was logged and whose file was then removed, **When** the launch
   runs, **Then** the same refusal, and nothing registered.
3. **Given** the brief exists and is logged, **When** the launch runs, **Then** today's
   registration: exit 0, the seat recorded as running, one `seat launched` event.

### Edge Cases

- A brief path with `./` or a doubled slash is normalised in the message, so the reason
  always starts with `brief .wuwei/days/` and always meets the floor.
- A traversal or a path outside today's `briefs/` is still `invalid brief path` (exit 2,
  `seats` level), checked before existence.
- An existing file with no `brief written` event keeps `no brief logged for this launch`
  (exit 1, `seats` level).
- `security.areas.seats = "off"` does not drop the missing-brief refusal: the floor wins.
- The existing `RECORDS_FLOOR` members (canary egress, owner disposition markers) give the
  same `hook.posture` result as before.

## Requirements

### Functional Requirements

- **FR-001**: `agent_launch._check` MUST return exit 2 with `brief <path> does not exist;
  run bin/wuwei brief <role> <item> <name> first` when the validated brief path does not
  exist, before reading events, and MUST NOT write state or events.
- **FR-002**: `<path>` MUST be the path relative to the workspace root as pathlib
  normalises it (`.wuwei/days/<day>/briefs/<name>.md`); `<role>` MUST be the launch's role.
- **FR-003**: `RECORDS_FLOOR` MUST include the constant prefix `brief .wuwei/days/`.
- **FR-004**: `hook.posture` MUST enforce every refusal whose reason starts with a
  `RECORDS_FLOOR` prefix as `block` with the records floor line, in every posture and
  whatever the area override.
- **FR-005**: Every other agent-launch refusal and every launch with an existing logged
  brief MUST behave exactly as today.
- **FR-006**: The design spec 9.2 table and `tests/test_invariants.py` MUST gain the
  invariant (constitution, Workflow), and the docs that list the records floor cases MUST
  name the missing brief.

### Key Entities

- **Brief reference**: the first prompt line `WUWEI brief: <relative path>`; the file it
  names lives in today's `briefs/` and is logged by a `brief written` event.
- **Records floor**: `workspace.FLOORS['records']` plus the `RECORDS_FLOOR` reason prefixes;
  blocks in every posture.

## Success Criteria

- **SC-001**: Under every posture, a launch naming a missing brief is denied and the day
  records no seat for it (hook exit 2; seats unchanged; no `seat launched` event).
- **SC-002**: A launch with an existing logged brief registers exactly as before (the
  existing `tests/test_agent_launch.py` table passes unchanged except the `missing-file`
  row's hint).
- **SC-003**: The full suite passes.

## Assumptions

- The issue's "is the current brief for the item and role" is already covered by the
  existing checks (logged event, role and name match, sha256 match), which stay at the
  `seats` level. Only the missing file joins the records floor, as the issue's message and
  acceptance name only that case.
- The message's argument order follows the command (`ROLE ITEM NAME`), correcting the
  issue's `<item> <role>`.
- The item is not derivable from a brief that was never written, so `<item>` stays a
  placeholder; the role is known from `subagent_type` and is filled in.
- The orchestrator notes file for this issue was not present; the reproduction used the
  owner's workspace day events (read-only) and an in-process scratch workspace instead.
- The invariant number is the next free one above the highest in the 9.2 table at build
  time (I56 when this spec was written).

## Deferred

- Whether the other pre-registration launch refusals (role or name mismatch, modified
  brief) should also be the records floor below strict: not asked, and each already names
  its fix. A follow-up issue if the owner wants it.
