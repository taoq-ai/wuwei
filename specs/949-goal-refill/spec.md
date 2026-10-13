# Feature Specification: Goal refill and planner Stop wake

**Feature Branch**: `949-goal-refill`
**Created**: 2026-10-13
**Status**: Implemented and verified; L4 deferred
**Input**: GitHub issue #949 and its 2026-10-12/13 empty queue field case.

## User Scenarios & Testing

### US1: Continue against open goals (P1)
When the approved queue is exhausted, the planner receives a refill row. A numbered
lead brief references approved goal blocks, wuwei status and the morning discovery sources.
The lead answer is saved to lead-N.json and admitted through plan propose.
Under-bar work citing an open goal joins automatically. Other candidates share one
Owner step card. Repeating the command cannot duplicate work or cards.

### US2: Finish an unproductive search (P1)
An empty or wholly declined refill records its result, permits close, and does not
repeat for the same open goal definitions that day. The report names goals for which
no work was found. A productive refill permits another search after its work finishes.

### US3: Wake a quiet planner (P1)
Stop on a started, unclosed planner day blocks with the actionable next row (set,
refill, lead or propose). Wait, a pending owner card, a seat, an unstarted or closed
day, and an active Stop with the same row signature pass. Blocks are capped per day. Errors pass and are recorded.

### Edge cases
Memory edits do not expand or change the gate-approved refill scope. Existing item IDs never rejoin, even
when parked, carried or finished. Refill cannot rewrite the morning plan or its
approved goals, envelope or seat policy. Owner No disposes of the exceptional batch.
Malformed lead JSON is refused before admission. Hook reads do no discovery or
network work and do not resolve launches. Event replay must preserve refill state.

## Requirements

- FR-001: next.step selects refill only at queue exhaustion, before close is requested.
- FR-002: Reuse the lead brief, discovery and proposal validation/ranking/admission.
- FR-003: Auto-admit only in-goal, under-bar candidates; one needs_owner card covers
  all remaining candidates, bound to their exact validated content.
- FR-004: Record each refill and suppress an unproductive repeat for identical goals.
- FR-005: Report goals with no candidate found, including outcomes.
- FR-006: Route Stop through hooks.json, hook.py and lifecycle's guard registration.
- FR-007: Stop calls next.step, checks planner identity and owner waits, records its
  row signature, returns block JSON with exit 0, and fails open on every error.
- FR-008: Preserve plan add and seat findings; no runtime dependencies or new modules.

## Key Entities
Open goals: the gate-approved IDs and their days/<day>/goals.md snapshot. Refill: numbered lead output and recorded
proposal result with goal snapshot, candidate IDs, owner decision and no-work goals.
Stop block: session and SHA-256 of row state plus sorted named commands; next.action
is not progress. Commands are not copied into the hook event.

## Success Criteria
The field case refills without an owner nudge. All listed Stop exemptions pass in
fixture tests. No discovery or adapter is called by Stop. All changed-module importing
test files pass with fake adapters. The review follow-up runs the full suite once,
then explicit affected files after any corrections.

## Assumptions

- The owner explicitly reverses #843 for this issue. Proposed design 5.7 wording:
  when the approved queue empties, repeat lead discovery against open goals, admitting
  safe goal work automatically and asking one card for exceptions. No owner design
  file is edited. Stop is an advisory continuation, exempt from fail-closed guards.
- goals.md has no completion field or measured attainment store. Goals still present
  are open; never infer attainment from finished tickets or a passed target date.
- No auto-start bar survives in current plan/config code. Use SLICE, no risk flags,
  no owner_actions, non-empty paths free of configured never-auto paths, kind build, size <= 3 (WSJF) or effort <= 1
  (RICE). FULL or an explicit full tier requires the owner. The normal morning gate remains the owner's approval.
- Only the gate-approved day goal IDs are eligible. Approval saves the goal snapshot
  even when it reuses memory goals. A legacy day without a snapshot does not refill.
- An empty outcome suppresses identical goal definitions for the rest of this day;
  productive refills can recur within plan.max_refills (default 3, zero disables).
  Refill stops at the approved envelope.end in owner.timezone, or the machine zone
  when unset. No new envelope config is introduced. An existing pending refill may
  finish at the count cap, but cannot admit work after the end. A pending pass
  must finish before any new pass starts. Admission rechecks the deadline after discovery. Reports give the bound
  and use only the last refill for goals with no work found.
- Refill uses plan propose INPUT --refill N, with numbered output in the day directory.
  The next row supplies the command. No new intake command or polling process.
- Refill admission emits the existing plan.approved event with a refill number and
  the newly admitted IDs and flags, so merge risk evidence and cycle measurements
  use the same producer contract as the morning gate.
- No questions, commits, push, stash, gh, or network tests, per implementation seat rules.

### Round 2 reconsideration and assumptions

The owner authorizes this correction after the second review. The prior deadline
assumption came from the template's HH:MM value and missed real ISO datetime values.
Keep the shared refill_limit function; parse full ISO datetimes first, then HH:MM
on the day date. Preserve explicit offsets, interpret naive values in owner.timezone
(or the machine zone), and apply no deadline if neither form parses. Count caps still
apply. No existing envelope-end parser was found in cli/wuwei.
The first Stop passed because of the daily block cap records hook.stop_capped at warn
tier, once per day across planner sessions, including a zero cap. Later capped Stops
pass without repeating the warning. Remove only the unused session_start imports.

### Review follow-up and proposed owner design wording

- The current status command requires --line and shows counts. Reference it and the
  day state.json for approved IDs and item details; do not add a new status view.
- H1 replaces event-count progress with the unchanged row test while stop_hook_active
  is true. guards.stop_max_blocks defaults to 20 per day across planner sessions;
  zero disables blocking. A new owner turn can wake the same row subject to the cap.
- M1 removes owner.requested and pending_owner entirely. An unchanged row after an
  unanswered card lets an active Stop through without introducing global card state.
- Unresolved repositories, missing paths and review/measure candidates share the
  exceptional owner card; they never prevent safe candidates from joining.
- This explicitly reverses the owner's Stop-hook removal in design line 187,
  #789 part 23, and changes the 4.1 hook table. PreCompact remains removed.
  Proposed exact replacement paragraph:

  The PreCompact hook remains removed (owner, 2026-10-12, #789 part 23). The Stop hook
  resumes only the main planner on a started, unclosed day when wuwei next names set,
  refill, lead or propose. It passes on wait or an owner decision, an unchanged row
  during an active Stop, or the daily block cap, and fails open on errors. wuwei close
  still refuses until every outward duty is recorded and the retro landed.

  Proposed exact 4.1 table row:

  | Stop | Main planner stops on a started, unclosed day | wuwei next names set, refill, lead or propose; pass on wait, owner decision, unchanged active Stop row or guards.stop_max_blocks (default 20). Errors fail open and are recorded. |

  Proposed exact 5.8 decision-table row:

  | Refill exceptions | One Owner step card listing all candidates outside approved goals or above the auto-start bar, including unresolved repositories | Admit the listed candidates through plan propose INPUT --refill N | Skip the listed candidates |

## Clarifications
2026-10-13: Resolved open-goal representation, conservative bar, owner No, retry
identity and close override by the assumptions above. No unresolved clarification.

## Deferred
L4: consuming a Yes and committing admission atomically needs a shared owner-answer
transaction change. Do not reorder authorization after mutation or add a refill-only
approval mechanism in this bounded correction. The user permits deferral unless small.
