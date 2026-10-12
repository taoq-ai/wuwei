# Feature Specification: second opinion is selective, and turning it off releases items waiting only on it

**Feature Branch**: `873-second-opinion-selective`
**Created**: 2026-10-12
**Status**: Draft
**Input**: GitHub issue #873: "feat(gates): second opinion is selective by flag or per item, and turning it off releases items waiting only on it"

## Root cause

- `cli/wuwei/dispatch.py:326-330` (`tier`): every STANDARD and FULL item gets
  `second_opinion` written into its tier record when `gates.second_opinion` is not `off`;
  there is no way to narrow it.
- `cli/wuwei/dispatch.py:652-662` (`next_step`): the tier record is written once, at the first
  `dispatch next` at the gate, and `gate_set` (`dispatch.py:218-237`) reads the second opinion
  from that stored record from then on. A later `gates.second_opinion = "off"` changes nothing
  for an item already tiered, so `quality@codex` stays in its gate set and the item waits on
  a gate that is switched off.

## User Scenarios & Testing

### User Story 1 - Only selected items get the second gate (Priority: P1)

**Acceptance Scenarios**:

1. **Given** `gates.second_opinion = "codex:m1"` and
   `gates.second_opinion_when = ["trust_surface"]`, **When** a STANDARD item flagged
   `trust_surface` is tiered, **Then** its gate set holds `quality@codex`; **When** a STANDARD
   item without the flag is tiered, **Then** it does not.
2. **Given** `second_opinion_when = []` (the default), **Then** every STANDARD and FULL item
   gets the second gate, as today.

### User Story 2 - Switching off releases waiting items (Priority: P1)

**Acceptance Scenarios**:

1. **Given** an item tiered with `quality@codex` whose arch, quality and security gates passed
   and whose second opinion has no verdict, **When** the owner sets
   `gates.second_opinion = "off"` and `dispatch next` (directly or through `next`) runs,
   **Then** the second opinion leaves the item's gate set and the step is `raise`.
2. **Given** the same item, **When** the selector changes so it no longer matches, **Then** the
   same release happens.
3. **Given** a released item, **When** `dispatch opinion` runs for it, **Then** it refuses with
   `item has no second opinion`.
4. **Given** an item whose second opinion returned FIX while its other gates passed, **When**
   the owner switches it off or narrows the selector, **Then** `dispatch next` still opens the
   fix round for `quality@codex` and the tier record keeps the second opinion.

### Edge Cases

- Turning the second opinion on (or widening the selector) mid-round does not add the gate to
  items already tiered; it applies at the next tiering. Adding a gate at delta would need an
  initial verdict that cannot exist.
- A recorded second-opinion verdict stays in `gate_verdicts` (the retro still lists it); only
  the gate set drops the gate.
- A second opinion that already returned a blocking verdict is not released: the item still
  goes to its fix round, and the delta rechecks it.

## Requirements

### Functional Requirements

- **FR-001**: New config key `gates.second_opinion_when`: a list of item flags
  (`trust_surface`, `boundary_relevant`, `agent_surface`), default empty. Empty selects every
  STANDARD and FULL item; otherwise an item is selected when any listed flag is set.
- **FR-002**: One function decides an item's second opinion from the config, its flags and its
  tier; `tier` uses it.
- **FR-003**: `dispatch next` and `dispatch opinion` re-check a recorded second opinion with
  the same function and drop it from the item's tier record when it no longer applies
  (event `gate.released`), before computing the gate set, unless its latest verdict (delta,
  else initial) blocks.

## Success Criteria

- **SC-001**: With the selector set to `trust_surface`, only trust-surface items get the
  second gate.
- **SC-002**: After switching to `off`, `next` moves an item whose other gates passed on to
  raise.

## Assumptions

- The selector is enough; the per-item `plan set <item> second_opinion=on|off` card the issue
  offers as an alternative is deferred (the issue asks for one of the two).
- The check runs where the planner acts (`dispatch next`, which `next` resolves for every gate
  offer, and `dispatch opinion`), so the stored tier record stays what `merge`, `derive`,
  `report` and `shepherd` read, and all of them see the release once it is written.
- Release applies only to a pending second opinion or one that passed. A second opinion whose
  latest recorded verdict blocks (FIX, PARK, ESCALATE, or a `blocks: yes` finding) keeps its
  gate after the switch, in every phase, so its finding is fixed and rechecked at delta
  (review F1; design: a blocking finding from either model blocks).
- Flags are the item's recorded risk flags (`items.<item>.flags`), the same ones that raise
  the tier and run gate step zero.

## Deferred

- Per-item `plan set <item> second_opinion=on|off` behind an Owner step card.
