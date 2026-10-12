# Feature Specification: environment failures are holds, an approved resume moves the build on

**Feature Branch**: `904-recovery`

**Created**: 2026-10-12

**Status**: Draft

**Input**: GitHub issue #904 (independent review, item 4): "environment failures are mechanical
holds, an approved resume moves the build on, the resume round grant is honoured once, and
owner_merge=false is not a hold."

## What happened

On the owner's day one about 20 owner cards went to plumbing. A missing interpreter or test
runner parked the build for the owner; the owner's Yes on `plan resume` then changed nothing,
because `build next` returned the same park. At the round cap the owner's Yes was promised one
more round (`docs/site/concepts.md`, Fix rounds) but `dispatch next` parked the item again.

## Claims checked against main 0.29.1

| Claim | Holds | Where (0.29.1) | Failing test |
|---|---|---|---|
| An environment failure parks for the owner | yes | `commands/build.py:542` `_park(... 'environment: ...')` | `test_a_missing_interpreter_holds_for_a_recheck_and_the_repair_moves_on`, `test_environment_failure_holds_after_first_check_without_feedback` |
| `plan resume` leaves the parked build action, so `build next` returns the park | yes | `plan.py:733-742` resets the phase only; `build.py:262` returns `record['action']` | `test_a_resumed_stuck_build_continues_its_builder_once`, `test_an_unchanged_environment_failure_parks_and_a_resume_rechecks_once` |
| Dispatch checks the cap before the resume at a blocking delta | yes | `dispatch.py:735-736` | `test_issue_acceptance_blocking_trust_finding_at_round_three_parks` (updated to the documented promise) |
| `_fix_round` ignores the resume at the cap | yes | `pr_actions.py:514-515` | `test_red_ci_at_the_round_cap_after_the_owners_resume_opens_one_round` |
| `derive.offers` asks the owner for red checks at the cap after a resume | yes (same class) | `derive.py:327` | `test_red_checks_at_the_cap_after_the_owners_resume_are_a_fix_round` |
| The moved-head paths ignore the resume | no | `dispatch.py:642`, `pr_actions.py:380`, `derive.py:317` already honour it (#872) | none needed |
| `derive.offers` treats `owner_merge=false` as a hold | yes | `derive.py:312` truthiness of the stored record | `test_a_released_owner_merge_is_not_a_hold`; the `test_loop.py` generator now stores the real record and fails on the old check |

## User Scenarios & Testing

### User Story 1 - a repaired environment moves on (Priority: P1)

**Independent Test**: a fast check reports `pytest not found`; `build next` returns a `check`
action with the reason and the repair; the item stays in `implement`; after the repair `build
check` passes and the item reaches `gate`.

**Acceptance Scenarios**:

1. **Given** a check result with `environment`, **When** checks complete, **Then** the build
   stays `check` with a `reason` naming the repair and `bin/wuwei build check <item>`, no builder
   round is spent, and the item does not park.
2. **Given** the same environment failure `build.stuck_after` times, **When** checks complete,
   **Then** the build parks with `environment: <reason>` (an ask park, as before).
3. **Given** the Codex build loop, **When** it reaches an environment hold, **Then** it stops
   with the reason instead of rechecking in a loop.

### User Story 2 - an approved resume moves the build on (Priority: P1)

1. **Given** a build parked on a repeated failure or the iteration limit, **When** the owner
   says Yes on `plan resume`, **Then** `build next` returns a `continue` of the builder with the
   park reason as feedback.
2. **Given** a build parked on an environment failure, **When** the owner resumes it, **Then**
   `build next` returns the recheck.
3. **Given** either, **When** the same failure repeats once, **Then** the build parks again.

### User Story 3 - the resume round grant is honoured once (Priority: P1)

1. **Given** an item parked at the round cap, **When** the owner resumes it, **Then** `dispatch
   next`, `pr act` (red checks or a moved head) and `next` open exactly one more round.
2. **Given** that round opened, **When** the next delta still blocks, **Then** the item parks
   at the cap again.

### User Story 4 - a released owner merge is not a hold (Priority: P2)

1. **Given** `owner_merge` stored with `value: false`, **When** `next` derives offers on a green
   PR, **Then** it offers the merge; with `value: true` it asks the owner.

### Edge Cases

- An environment failure followed by a real failure: the signatures differ, so the repeat count
  restarts and the builder continues with the failure as before.
- A build the scanner, a PARK verdict or the owner parked (`plan park`) has status `done` or
  `ready`, not `parked`: `plan resume` leaves its build record as it is.
- Nothing resumes on its own: every reset and every extra round follows the owner's Yes.

## Requirements

- **FR-001**: an `environment` check result holds the build in `check` with a recheck action
  naming the repair; only `build.stuck_after` unchanged environment results park it.
- **FR-002**: `plan resume` resets a `parked` build record with the item phase: an environment
  park becomes a recheck (`check`), any other park a builder `continue` (`ready`).
- **FR-003**: one shared test, `dispatch.capped`, answers "the cap is spent and no resume grants
  a round" for `next_step`, `_fix_round`, the gated push and `derive.offers`; `open_fix` reads
  the grant itself and its `build.fix_opened` event spends it.
- **FR-004**: `derive.offers` reads the owner hold through `merge.owner_hold`.
- **FR-005** (review F1): a `build.checked` event ends the resume grant, like `plan.disposed`
  and `build.fix_opened`. A resumed build park is answered by its check, so the item reaches
  its gates with no grant and a PARK verdict, an ESCALATE or a Blocked line still goes to the
  owner. The cap, PARK and Blocked resumes reach their consumers with no check in between.
- **FR-006** (review F2): `derive._gate` uses `dispatch.capped` for the cap at a blocking delta.

## Success Criteria

- **SC-001**: the seven failing tests above pass, and every test file importing a changed
  module passes under 3.12 and 3.11.

## Assumptions

- A Yes after a stuck-loop park means "try once more": the builder continues once, its repeat
  and iteration counters are kept, so the same failure parks again on its next check.
- The environment hold is bounded by the existing `build.stuck_after`, not a new setting.
- "Adapter unmeasured" in the issue: the only other `_park` in the build loop is the owner's own
  `seat stop --unmeasured`, an owner choice, so it stays a park. A check that cannot run (exit 2)
  already raises with a rerun step and parks nothing.
- The round cap grant keeps the existing event-log definition (`dispatch._resumed`): a
  `plan.resumed` after the last `plan.disposed` and `build.fix_opened`.
- `owner_hold` raises on a damaged `owner_merge` record, as `merge.check` already does.

## Deferred

- `fix round already used` (a manual transition into `fix` after its delta) still re-parks
  after a resume; it is reached only by a manual transition and its intended next step is not
  defined by the issue.
