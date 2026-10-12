# Feature Specification: a governed_by that is not a file is refused at plan propose, and a stuck item never holds a CAP seat

**Feature Branch**: `864-plan-admit` (feature directory `specs/864-governed-by-file/`, shared
branch with #868: both change plan admission)

**Created**: 2026-10-12

**Status**: Draft

**Input**: Issue #864, "fix(plan): a governed_by that is not a file is refused at plan
propose, and a stuck item never holds a CAP seat".

## Context

On the owner's first real day on 0.28.0 the lead proposed TIN-466-ARM with
`governed_by: "specs/ais-4448-index-lane-sweep-schedule"`, a directory. `plan propose`
checked only that the value is a nonempty string (`cli/wuwei/plan.py:110`), the gate approved
it, and `seat brief builder TIN-466-ARM` exited 2 in `specmode.governing`
(`cli/wuwei/specmode.py:321`): the reference is not a file. The value lives in the approved
plan state, so the hint to fix the `Governing:` line in spec.md does not apply; `plan propose`
refuses after the gate, `plan set` takes only spec, ticket and owner_merge, and `plan add`
refuses an existing id. `next` kept returning the item as `start` (`dispatch._start` never
looks at governed_by), so it held one of the CAP seats and the next queued item waited.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A directory reference resolves or is refused at propose (Priority: P1)

**Why this priority**: the gate should never approve a reference the brief cannot read.

**Independent Test**: propose a candidate whose `governed_by` is a directory, with and without
a `spec.md` in it, in a workspace with one configured repository.

**Acceptance Scenarios**:

1. **Given** `governed_by` names a directory that holds `spec.md`, **When** `plan propose`, the
   builder brief or `build analysis` reads it, **Then** it resolves to `<dir>/spec.md` (a
   `#heading` suffix still selects a section of that file).
2. **Given** `governed_by` names a directory without `spec.md`, a missing file, or a heading
   the file lacks, in the candidate's repository, **When** `plan propose` runs, **Then** it
   exits 2, writes nothing and names the item, the reference and the fix.
3. **Given** the candidate's repository is not known (several repositories and none named),
   **When** `plan propose` runs, **Then** only the shape is checked; the start check of Story 3
   still holds.

### User Story 2 - The owner corrects governed_by after the gate (Priority: P1)

**Independent Test**: `plan set <item> governed_by=<path>` on an approved item.

**Acceptance Scenarios**:

1. **Given** an approved item, **When** `plan set <item> governed_by=<path>` runs without the
   owner's Yes on its Owner step card, **Then** it exits 1 with the card and nothing changes.
2. **Given** a path that does not resolve in the item's checkout (its worktree when it exists,
   else its repository), **When** `plan set` runs, **Then** it exits 2 before asking the card
   and nothing changes.
3. **Given** the owner's Yes and a path that resolves, **When** `plan set` runs, **Then** the
   item records the value with one `plan.set` event.

### User Story 3 - An item whose brief cannot be written takes no CAP seat (Priority: P1)

**Independent Test**: an approved planned item whose recorded `governed_by` does not resolve,
with a second planned item queued behind it and CAP 1.

**Acceptance Scenarios**:

1. **Given** that item, **When** `next` derives the launch set, **Then** the item's entry is a
   `park` whose reason names the cause and the fix (`wuwei plan set <item> governed_by=<path>`,
   then `wuwei plan resume <item>`), and the next queued item gets the `start`.

## Requirements *(mandatory)*

- **FR-001**: `specmode.governing` resolves a directory reference to `<dir>/spec.md`.
- **FR-002**: One check in `plan.py` validates `governed_by` (its shape, and its resolution in
  a known checkout through `specmode.governing`); `plan propose`, `plan set` and
  `dispatch._start` call it, and #868's `plan add` reuses it.
- **FR-003**: `plan propose` refuses a candidate whose `governed_by` does not resolve in its
  repository.
- **FR-004**: `plan set <item> governed_by=<path>` records the value after the owner's Yes on
  the Owner step card, the same mechanism `spec=skipped` uses.
- **FR-005**: `dispatch._start` returns a park, with the fix in its reason, for an item whose
  recorded `governed_by` does not resolve where the brief reads it (`specmode.brief_block`:
  spec mode on, engine speckit, item not skipped); a park takes no seat (the existing #603
  rule). The repository park names `wuwei worktree add <item> --repo <name>`, then
  `wuwei plan resume <item>` (review F2).

## Success Criteria *(mandatory)*

- **SC-001**: The TIN-466-ARM sequence (directory reference, approved, brief fails, seat held)
  cannot recur: propose refuses it, and a reference that breaks later parks with a way out.

## Assumptions

- The checkout a reference resolves in is the item's worktree once it exists, else its
  configured repository's checkout (the one repository, or the one the item names). With no
  repository known, propose checks the shape only.
- Changing what governs an item is the owner's decision, so `plan set governed_by=` always asks
  the Owner step card, keyed by the command (which carries the value).
- Only the governed_by failure is predicted at start; other brief refusals (a SLICE brief on
  protected paths, no merge base) already print their own fix and stay out of scope.
- The design spec text on governed_by (#664) still holds; the directory rule is an addition the
  owner may write into the design spec.

## Deferred

- A general "a refused brief parks the item" path for every brief refusal; to be filed if a
  second refusal kind holds a seat in practice.
