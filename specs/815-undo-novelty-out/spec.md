# Feature Specification: delete the undo door, undo rehearsal and novelty

**Feature Branch**: `b3-decision-framework` (feature directory `specs/815-undo-novelty-out/`)

**Created**: 2026-10-11

**Status**: Draft

**Input**: Issue #815, part 10 of the #789 deletion pass: "chore(decisions): delete the undo door, undo rehearsal and novelty".

## Context

Two layers sit on top of the `Reversibility:` field of a decision record.

**Measured reversibility (#557).** A record counts as two-way only when the CLI knows the
undo for its class and that undo ran once in this workspace.

- `wuwei undo rehearse <kind>` exercises an undo on a scratch target and writes
  `memory/rehearsals.json`.
- `decision lint` prints a correction, and `decision route` rewrites the door to one-way on a
  first route.
- Each missing rehearsal comes back from `wuwei next` as a `rehearse` row.
- `wuwei undo D-n` reverts a mandate answer.
- `wuwei undo <event id>` opens the revert PR of a merge event.

**Novelty (#556).** A seen set in `memory/targets.json` makes a record, a guarded action or a
chat send that names a target the workspace never touched run one level lower, which means a
card.

Both make the model reason about the process: which undo was rehearsed, which target is new,
whether its written door will be lowered. The rule stays in the charters as prose: when
unsure, the door is one-way.

Part 9 (#814) is already done in this batch. Cruise, its undo window and the window check in
`decision undo` are gone. `decision undo` and `wuwei undo D-n` revert a mandate answer
without a window, and this part deletes them with the rest.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The written door stands (Priority: P1)

A seat writes a two-way record inside its item and routes it. The record routes on the door
it wrote. No ledger is read, nothing rewrites the record, and no lint line names an undo.

**Why this priority**: routing is process control kept in code (pass plan: owner decisions
reach the owner through `next`). It must stay deterministic and must not depend on a ledger.

**Independent Test**: route a two-way `approach` record in a workspace with no
`memory/rehearsals.json` and without the conftest fake.

**Acceptance Scenarios**:

1. **Given** autonomous mode, no rehearsal ledger and a two-way `approach` record, **When**
   `wuwei decision route D-3` runs, **Then** it prints `mandate`, and the record keeps
   `Reversibility: two-way` with no `Reversibility corrected` line.
2. **Given** a one-way record, **When** it routes, **Then** it goes to the owner as before.
3. **Given** a two-way record of class `message`, `merge`, `other` or with no class, **When**
   it routes, **Then** it routes like any two-way record of its CISR class. The outbound
   tiers and the merge policy still gate the action itself.
4. **Given** `wuwei decision lint` on a two-way record, **When** it runs, **Then** the OK line
   carries no `Reversibility: one-way, not` line.

### User Story 2 - A new target asks nothing extra (Priority: P1)

A record, a deploy refusal or a chat send that names a repository, channel or person never
seen before behaves like one that names a known target.

**Independent Test**: route a Routine record whose Context names `repo:acme/new`, with no
`memory/targets.json`.

**Acceptance Scenarios**:

1. **Given** autonomous mode and a Routine record naming `repo:acme/new`, **When** it routes,
   **Then** it prints `mandate` with no `first time for` line, and no `memory/targets.json` is
   written.
2. **Given** an owner answer on a card, **When** it is recorded, **Then** no seen-set file is
   read or written.

### User Story 3 - Nothing names undo, rehearsal or novelty (Priority: P2)

**Acceptance Scenarios**:

1. **Given** the CLI, **When** `wuwei undo` or `wuwei decision undo D-1` runs, **Then**
   argparse refuses it as an invalid choice (SystemExit 2).
2. **Given** a day after the gate with no rehearsal ledger, **When** `wuwei next` runs,
   **Then** no row has state `rehearse`.
3. **Given** a day, **When** the report is written, **Then** it has no `## First time today`,
   `## Undone today` or `## Cannot be undone` section.
4. **Given** a workspace holding any of `memory/rehearsals.json`, `memory/rehearsals.lock`,
   `memory/targets.json`, `memory/targets.lock` or `memory/cruise.json`, **When**
   `wuwei init --upgrade` runs, **Then** each one is removed and named once. Under
   `--dry-run` each is named with `Would` and kept.
5. **Given** `wuwei doctor`, **When** it runs, **Then** it has no `undo rehearsals` row.

### Edge Cases

- Day state written before the upgrade may hold `novel` on a `decision_routes` row. Nothing
  reads it.
- Day directories keep their `undo.jsonl` journal and old `undo.done`, `undo.rehearsed` and
  `decision.reversed` (with `undo: true`) events as history. Nothing reads the first three.
- A merge that turns its base red still gets its revert PR, its breaker and its page:
  `merge.revert` and the red-base path of `merge.monitor` stay, and they never read the
  journal.
- An owner who wants a mandate answer reversed answers the record with `wuwei decide D-n
  <option>`. That writes `decision.reversed` as today.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `decision route` MUST route on the written `Reversibility:` and MUST NOT rewrite
  the record's door or class.
- **FR-002**: `decision lint` MUST NOT print a reversibility correction. Its exit code and OK
  line are otherwise unchanged.
- **FR-003**: No route, guard, draft or owner answer MUST read or write a seen set. The
  `novel` route field, the `first time for` texts and the target-key lookup in `why` go.
- **FR-004**: The following MUST be gone:
  - the `wuwei undo` command, `decision undo` and the `undo` DM verb path;
  - `undo.py` and `novelty.py`;
  - the git adapter's `rehearse_revert`;
  - the `next` row `rehearse`, the doctor row `undo rehearsals` and its Keep/Undo card
    exclusion;
  - the init line `Undo not rehearsed` and the init seen-set seed;
  - the events `undo.rehearsed` and `undo.done`;
  - the report sections `First time today`, `Undone today` and `Cannot be undone`.
- **FR-005**: The merge undo journal (`days/<day>/undo.jsonl`, `merge.undo`) MUST go.
  `merge.revert` and the red-base revert, breaker and page MUST stay unchanged.
- **FR-006**: `init --upgrade` MUST remove `memory/rehearsals.json`, `memory/rehearsals.lock`,
  `memory/targets.json`, `memory/targets.lock` and `memory/cruise.json` (part 9) when they are
  present, naming each, and MUST honour `--dry-run`.
- **FR-007**: The charters keep the rule "when unsure, write it as one-way". No charter,
  skill, docs page or design spec section describes measured reversibility, undo rehearsal,
  `wuwei undo` or novelty.

### Key Entities

- **Decision route row** (`decision_routes.<id>`): `reversibility`, `recommendation`, `cisr`,
  `class`, `at`. `novel` is no longer written.

## Success Criteria *(mandatory)*

- **SC-001**: Every touched test file passes. No test is loosened, and only tests of deleted
  code are deleted.
- **SC-002**: The grep
  `grep -rniE 'novelty|\bnovel\b|rehears(e|al)|wuwei undo|decision undo|undo\.(py|jsonl|done|rehearsed)|targets\.json|rehearsals\.json'`
  over `cli/`, `adapters/`, `charters/`, `skills/`, `agents/`, `hooks/`, `templates/`,
  `scripts/`, `.github/`, `docs/site/`, `README.md` and the design spec returns only two
  kinds of hit:
  - the release rehearsal: `docs/site/rehearsal.md`, `scripts/headless_e2e.py --rehearsal`,
    `mkdocs.yml` and the links to them;
  - the init file-removal list.
- **SC-003**: The same record routes the same way whatever `memory/` holds.

## Assumptions

Open questions answered with the recommendation (strict, non-interactive):

1. The #600 config-write correction goes: `undo.config_write`, `two_way`, `CONFIG` and the
   config branch of `undo.correct`. A record with a config value never reaches the mandate:
   `mandate` returns early on `config_keys` (#529). The correction therefore only changed the
   door and class printed on the owner's card. Invariant I33 goes with it if the walk still
   exists.
2. A message record is no longer forced one-way. The record sends nothing; the outbound tiers
   (4.9) gate the send. No new lint rule (YAGNI).
3. The merge undo journal is write-only: nothing under `cli/` reads it. It goes. `merge.revert`
   stays because the red-base watch needs it.
4. The release rehearsal (`docs/site/rehearsal.md`, `scripts/headless_e2e.py --rehearsal`) is
   a different thing and stays.
5. `init --upgrade` removes the memory files of parts 9 and 10. This issue asks for the
   retired files, and the mechanism is one tuple. Old `undo.jsonl` files in day directories
   are day history and stay.
6. `decision.reversed`, written when an owner answer differs from a taken one, stays. It is
   the owner's record, and telemetry, metrics and `why` read it.
7. Part 9 already rewrote the README principle that named novelty and undo. This part only
   checks it.
8. The design spec edits are part of the owner-approved #789 pass.
9. Earlier `specs/` directories (#556, #557) and the CHANGELOG keep their history.
