# Feature Specification: launch the gate seats that fit; one build slot count

**Feature Branch**: `910-gates-that-fit`

**Created**: 2026-10-12

**Status**: Draft

**Input**: GitHub issue #910: "launch the gate seats that fit and share one running-seat count
across derive, dispatch and the launch guard" (independent review, item 10).

## What happened

The review read main after 0.29.0. Each claim was checked again on main after 0.30.0 with
#898 (`brief.live`) and #845 (per-runtime window room in `launch_set`).

1. Held. `dispatch.launch_set.add` counts every seat of a gate action as one block
   (`launches = len(value['seats'])`) and waits the whole set when it exceeds the free host
   seats, or when any runtime's window room is short of its seats. A three-gate item with
   `host.seats = 2` waits on an idle host on every sweep: nothing ever frees a seat. A second
   opinion adds a fourth seat on its own runtime, and a spent Codex window holds the three
   Claude sentinels too. The waiting gate sets `gate_waits`, so no planned build starts either:
   the day stops until the owner raises `host.seats`.
2. Held. The CAP count is computed five times with two definitions: the approved items in a
   build phase, not held (`derive.offers`, `launch_set`, `build.next_action` for a new build,
   `next`'s wait row), and the live builder seats (`agent_launch` guard). They disagree on a
   Codex build loop (a build, no seat), on a fix round that re-enters a build phase, and on a
   CAP derived lower at launch. `launch_set` offers a builder continuation without a CAP check,
   so the guard can refuse what `next` offered, and a refused launch runs unregistered (#837).
   `brief.live` (#898) is already the one host seat count for `launch_set` and the guard;
   `derive.offers` counts no host seats.

## User Scenarios & Testing

### User Story 1 - the gate seats that fit launch (Priority: P1)

**Independent Test**: one item at its gate with three briefed sentinels and `host.seats = 2`:
the launch set returns the item's `gates` action with two seats and `deferred: 1`; after those
two verdicts are received the third launches; the item raises. At no point do more than two
seats run.

**Acceptance Scenarios**:

1. **Given** three gate seats and two free host seats, **Then** two launch and the entry says
   one waits for a seat.
2. **Given** a second opinion on a runtime whose window has no room, **Then** the Claude
   sentinels launch and the second opinion waits, naming its runtime window.
3. **Given** no seat of the set fits, **Then** the entry waits as today: the host seat reason,
   or the window hold with its reset when the host has room.
4. **Given** a gate set partly launched, in the sweep that defers it and while its first batch
   runs, **Then** no planned build starts (the existing rule: a sweep where a gate waits for
   seats starts no new planned build).
5. **Given** the batch running, **Then** the item is not offered again until its seats stop
   (`derive.offers` skips an item with a running seat); the stopped seats' receive commands and
   the remaining seats come in one entry.

### User Story 2 - one build slot count (Priority: P1)

**Given** CAP 1, item B building first in plan order with a stopped builder awaiting its checks
and item X in a fix round after it, **When** derive, the launch set and the launch guard count,
**Then** each counts B and X as holding or wanting a slot: B's continuation launches, X's builder
waits with the CAP reason in the launch set and the guard refuses it with the same reason, and
no planned item starts.

**Given** a Codex build loop (a build with no seat) and CAP 1, **Then** a Claude builder for a
later item is refused by the guard, as the launch set already waits it.

### Edge Cases

- CAP derived lower at launch than the builds already in a build phase: the first CAP holders
  in plan order keep their slots; the rest wait. No deadlock: the holders do not wait on them.
- A build step that launches no seat (fast checks, a wait) is never held by CAP.
- A held item (#648) holds no slot.
- Head pinning: the gate briefs of a set are written together at one head; the launch guard
  refuses a brief whose worktree HEAD moved and a head that is not the build's checked head
  (#901); a verdict counts only at the current head (`derive.counted`). A deferred seat launches
  on the head its siblings read or not at all.

## Requirements

- **FR-001**: `launch_set` launches the subset of an action's seats that fits the free host
  seats and each runtime's window room, in the action's order, and marks the entry with
  `deferred` (the count left) and a reason. With none fitting it waits as before.
- **FR-002**: `gate_waits` also holds for a partly launched gate set: one that deferred seats
  this sweep, or an initial gate with a running gate seat and fewer gate seats registered than
  its gate set.
- **FR-003**: `commands.next.building(data)` is the one build slot count: the approved items in
  a build phase, not held, in plan order (running and reserved builds). `derive.offers`,
  `launch_set`, `build.next_action`, `next` and the launch guard use it; their own sums go.
- **FR-004**: a builder seat launches only while its item holds a slot: it is among the first
  CAP holders, or fewer than CAP hold one. The guard refuses it otherwise; the launch set waits
  any builder launch (build or fix kind) that fails it.
- **FR-005**: the guard's refusal text starts `build slots`, and the capacity list that keeps
  capacity refusals log-only (#837) names it.

## Assumptions

- Kept rule: a sweep where a gate waits for seats starts no new planned build (design, #528),
  widened to a gate set that is partly launched (below).
- The batch is received before the rest is offered: `derive.offers` already skips an item with a
  running seat, and that decision code belongs to #902. Reviews may run in two rounds.
- Slot order is plan order (`approved`), the order every other count already walks.
- CAP still counts at launch with the CAP derived at launch (#528); the host seat count stays
  `brief.live` (#898).
- The design text "CAP counts running build seats" and the lead charter ("a slot frees at builder
  handoff") already describe this count. The design spec is the owner's and is not edited here.
  Proposed amendment for the owner to the CAP bullet: "CAP counts build slots, one count for
  `next`, the launch set, `build next` and the launch hook: the approved items in a build phase
  and not held, in plan order, so a stopped builder awaiting its checks keeps its slot until its
  handoff. A builder launches while its item is among the first CAP holders or a slot is free. A
  gate set launches the seats that fit the free host seats and each runtime's window room (a
  second opinion takes its own runtime's); the rest launch after those verdicts are received, on
  the same checked head. While a gate set is partly launched (the sweep that defers it, and while
  its first batch runs) no new planned build starts."
- The slot count is read fresh after the sweep's offers resolve, so a fix round opened in the
  same sweep holds its slot before any later builder or planned start is offered (review F2).
- A gate set is partly launched while its item is at its initial gate, one of its gate seats
  runs, and fewer gate seats are registered than its gate set holds. A delta round is not
  tracked this way: only the sweep that defers it holds new builds.
- An item on a #904 environment hold (its build waits on a recheck the owner repairs) is not
  `state.held`, so it keeps its build slot until the owner repairs it or its repeats park it.
  After a CAP drop, a later stopped builder past CAP waits on that repair ("CAP N reached: build
  slots held by ..."), where the old guard let it continue. The wait is an owner decision, not a
  loop (review F4).
