# Feature Specification: next and every refusal carry one executable action

**Feature Branch**: `902-one-action`

**Created**: 2026-10-12

**Status**: Draft

**Input**: GitHub issue #902 (independent review, item 2, and its contradictions list): "Make
next and refusals consume the same executable action. Extract the shared gate decision from
derive._gate and dispatch.next_step. Keep execution in dispatch. Preserve the action through
dispatch.resolve_offer instead of replacing it with run wuwei next again. Make build next and
next use the same resolver. Feed emitted actions into their real command and hook consumers."

## What happened

`derive._gate` (what `wuwei next` offers) and `dispatch.next_step` (what `dispatch next` does)
each held a copy of the gate decision. They disagreed: derive's copy did not know the polish
offer, the checked-head rule (#901) or a build that is not done, so next offered a gate step
that dispatch next answered differently or refused. `resolve_offer` then replaced any answer
that was not a launch (a park, an owner card, a finished build) with "run wuwei next again", so
the planner looped on prose. Several refusals named a step another part of WUWEI refuses.

## Claims checked against the base branch

Base: main after 0.30.0 and #901 (`322c2053`). Each claim that holds has a test that feeds the
emitted action into its real consumer (the command, run through the PreToolUse hook as the
planner runs it, and the Agent launch guard) and failed on the base branch.

| Claim | Holds | Where (base) | Failing test (`tests/test_one_action.py`) |
|---|---|---|---|
| Missing initial receipt in fix or delta: next_step names `receive`, which refuses an initial outside gate | yes | `dispatch.py:727`, `:734`, `:1242` | `test_a_missing_initial_receipt_in_delta_is_gated_and_received` |
| Changed verdict file: merge says receive again, receive refuses a current receipt | yes | `merge.py:822-835`, `dispatch.py:1261` | `test_a_verdict_file_changed_after_its_receipt_does_not_block_the_merge_gate` |
| Stale gate receipt: `_seats` offers a continue the launch guard refuses (no Agent resume, not delta) | yes | `dispatch.py:1025`, `guards/agent_launch.py:252` | `test_a_stale_gate_receipt_rereads_on_a_seat_the_guard_accepts` |
| Lost delta seat: `_seats` offers nothing when the original seat is lost; the charter permits a fresh seat | yes | `dispatch.py:1079`, `charters/_common.md` Evidence 6 | `test_a_lost_delta_seat_is_replaced_by_a_fresh_one` |
| Failed shepherd: raise_action returns only a why lookup; rebriefing its name is refused | yes | `dispatch.py:801` | `test_a_shepherd_that_stopped_without_a_pr_is_retried_then_parked` |
| Blocked builder: the stop guard demands spec artifacts first in strict mode | yes | `specmode.py:285`, `guards/spec.py:75` | `test_a_blocked_builder_stops_and_the_owner_is_asked_before_its_checks` |
| Broken config: the docs prescribe `config check` and `init --upgrade`; the hook lets only repair reads and `config set` through | yes | `docs/site/recovery.md:23-25`, `commands/hook.py:186` | `test_the_broken_config_recovery_commands_pass_the_hook` |
| Docs say the morning gate pre-approves owner_actions; the lead charter and the plan say it does not | yes | `docs/site/reference.md:115`, `charters/lead.md` rule 4 | `test_docs_agree_on_owner_actions_and_integrity` |
| Docs say uncommitted edits block tools; integrity is warning-only | yes | `docs/site/index.md:78`, next's ENFORCE sentence | same test |
| Fresh builder brief vs build next (review list) | no | closed by #889/#892 | none |
| next offers a gate launch dispatch next answers otherwise (polish, checked head, build not done) | yes | `derive.py:186`, `dispatch.py:668-674` | `test_next_and_dispatch_next_take_one_gate_decision` |
| resolve_offer turns a park, an owner card or a finished build into "run wuwei next again" | yes | `dispatch.py:826` | `test_next_keeps_the_resolved_action` |

## User Scenarios & Testing

### User Story 1 - one gate decision (Priority: P1)

**Independent Test**: for an item at gate or delta, the step next offers and the step dispatch
next takes come from one function; a polish offer, a moved checked head and an unfinished build
each give the same step in both.

**Acceptance Scenarios**:

1. **Given** every gate passed with notes and `gates.polish = offer`, **When** next derives the
   item, **Then** it offers a polish launch, and resolving it returns the polish action.
2. **Given** a done build whose worktree moved past its checked head, **When** next derives the
   item, **Then** the launch resolves to the build's fast-check step.
3. **Given** a build at its checks with the item at gate, **When** next derives it, **Then** it
   launches `wuwei build next <item>`, never a gate step dispatch next refuses.

### User Story 2 - the resolved action is kept (Priority: P1)

1. **Given** a launch whose resolver answers an owner card, **When** next resolves the set,
   **Then** the card is the set's decision with its command, not a refused launch.
2. **Given** a launch whose resolver parks the item or finishes a build, **When** next resolves
   it, **Then** the entry keeps that action (no "run wuwei next again").
3. **Given** `build next` past the build, **When** run, **Then** it answers what `dispatch next`
   decides, through the resolver next uses.

### User Story 3 - the contradictions are closed (Priority: P1)

Each row marked "yes" above: the emitted action, run by its real consumer, makes progress,
waits on something real, or opens a specific owner decision.

## Requirements

- **FR-001**: `dispatch.decide` is the one gate decision of an item at gate or delta. It only
  reads, so next derives it on the hook path; `next_step` executes it; derive's copy is
  deleted. `pr_actions._gated_push` reads it too.
- **FR-002**: The decision covers the gone worktree, a done build moved past its checked head,
  a build that is not done, the builder's Blocked card, missing and stale gates, polish, raise,
  the round cap, PARK, ESCALATE and FIX.
- **FR-003**: `resolve_offer` returns the resolver's action unchanged. `build next` and next's
  build launches resolve through one function (`build.step`); past the build it answers
  `dispatch.gate_step`, which next's gate launches use as well.
- **FR-004**: next promotes the first owner action a launch resolves to (an `escalate`) to the
  set's decision when the set has none. A launch that resolved to an owner step, a park or a
  finished build is not left in the launches (review F4); the next derivation brings it back.
- **FR-005**: A gate with no initial verdict in fix or delta does not refuse: the fix round goes
  on, and in delta that gate reads the current head on a fresh seat; `receive` takes that one
  initial verdict in delta. It is recorded like a later round's (round `delta` in the record,
  marked `late`), so merge's round-one HEAD agreement does not count it. A late verdict that is
  not a PASS is judged as an initial verdict until a fix round opens, whatever moves the head
  meanwhile (review F1, D1): FIX opens the fix round after the cap check, PARK parks, ESCALATE
  asks the owner; it takes no delta re-read. The fix round (`rotate`) clears the flag; a late
  PASS takes the ordinary stale and recheck path.
- **FR-005a**: A stale second opinion (`role@runtime`) reruns through `dispatch opinion`, never a
  Claude fresh seat; `dispatch opinion` returns its stored verdict only while it counts at the
  current head (review F2).
- **FR-006**: merge's gate check reads the receipt, as derive does (#844 F3): a verdict file
  changed after its receipt changes nothing.
- **FR-007**: A stale receipt (its head moved) re-reads on a fresh gate seat at the current head;
  a delta whose original seat is lost (missing, no agent id, or stopped as unmeasured) gets a
  fresh seat with the delta feedback in its brief.
- **FR-008**: A shepherd seat that stopped without raising the PR is retried on a fresh seat
  (`shepherd-<item>-<n>`) once, and once more per owner resume of the item; then the item parks
  for the owner's resume card. A running shepherd is a wait.
- **FR-009**: A builder stop whose `Blocked:` line is not `none` passes the spec stop guard. A
  build at its checks whose stopped builder is Blocked answers the owner's card first (command
  `wuwei build next <item>`): Yes continues the builder on the answer, No parks the item.
- **FR-010**: While config.toml does not load, the hook lets `config check` and `doctor --fix`
  (which asks its own Owner step card) through, and the refusal names them.
- **FR-011**: The docs say the morning gate does not pre-approve owner_actions, and that
  integrity warns and never blocks a tool call; next's guard sentence agrees.

## Assumptions

- A gate with no initial verdict in delta is rare (a manual or lost receipt). Its verdict at the
  current head is its first read and is judged as one (FR-005).
- A stale receipt re-reads on a fresh seat instead of a continue: Claude Code's Agent has no
  resume, so a continue is a fresh Agent anyway, and a fresh brief is the launch the guard
  accepts. Charter Evidence 6 (continue the same sentinel) is about the delta, which keeps its
  continue.
- merge trusting the receipt lowers no protection: the receipt was linted when recorded, the
  records floor keeps the planner off `decisions/`, and a file changed afterwards could only
  block a merge, never pass one.
- The shepherd retry bound is one fresh seat per owner resume.
- A builder not stood down at a gate (no build record, no stopped seat) still refuses in
  dispatch next and shows as a refused launch: there is nothing to run, and #901's reconcile is
  the re-entry for work outside the record.
- #927 (#906) reworks raise_action's seat helper and the shepherd duty; this change edits only
  raise_action's stopped-seat branch, so a merge keeps both.

## Deferred

- An existing PR routed to raise, and a post-PR delta that can select no reviewer: review item
  3, its own issue.
- The spec backstop at dispatch next (an item at gate with a spec gap) still names the builder
  step it needs; reachable only by a manual transition.
