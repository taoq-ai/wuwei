# Feature Specification: Measured reversibility

**Feature Branch**: `557-measured-undo`
**Created**: 2026-10-08
**Status**: Draft
**Input**: GitHub issue #557: a record is two-way only when the CLI knows the undo for its
action and that undo was rehearsed once; `wuwei undo` runs it; a message is never two-way;
the day report lists what cannot be undone.

## Root cause

The whole routing rests on a field the seat writes and nothing measures:

- `cli/wuwei/decision.py:128-132` (`evaluate`) accepts `Reversibility:` as written
  (`one-way`, `two-way` or `unsure`) and never checks it against anything.
- `cli/wuwei/decision.py:363-375`: `cisr` (Routine by definition unless written one-way,
  low risk only when written two-way) and `route` (`seat` only when written two-way) read
  that field as given.
- `cli/wuwei/commands/decision.py:42-78` (`decide`, the `decision route` command, the one
  routing point) and `:81-110` (`mandate`) take a record under the mandate, or send it to
  the seat, on the written value. `owner_outcome` (`:166`), `waits` (`decision.py:433`) and
  the DM listener (`remote.py:279`) then trust the same field in the file.
- `cli/wuwei/decision.py:16-19`: the class `message` exists, but nothing stops a message
  record written `two-way` from routing as two-way, although 4.9 and 5.8.1 say a message
  has no undo.
- There is no undo registry and no rehearsal record: on this base `commands/decision.py`
  has no undo at all (#283 adds `decision undo` for a cruise answer), `merge.py:331`
  (`undo`) only logs a merge's revert PR to `undo.jsonl`, and `report.py:102` lists mandate
  decisions with a reversal command but nothing that was undone or cannot be undone.

## User Scenarios and Testing

### User Story 1: A two-way claim the CLI cannot back goes to the owner (Priority: P1)

A seat writes `Reversibility: two-way`. The CLI derives the record's action kind from its
class, looks the kind up in the undo registry and the rehearsal ledger, and lowers the door
to one-way when the undo is unknown or never ran here. It says so; it never rejects the
record for it.

**Independent Test**: neutral workspace in `tmp_path`, default config (autonomous), records
from `wuwei decision template` with the class, blast radius and door set per case, the
ledger written by `wuwei undo rehearse` or absent.

**Acceptance Scenarios**:

1. **Given** a `Class: merge` record written two-way whose Context names
   `repo:fixture-org/app`, a configured repository without `merge_deploys = false`, **When**
   `wuwei decision lint` runs on it, **Then** it exits 0 and prints the OK line plus
   `Reversibility: one-way, not two-way: a merge to repo:fixture-org/app deploys
   (merge_deploys is not false, 4.6); ask the owner: wuwei decision route sends the card`; **When**
   `wuwei decision route D-n` runs, **Then** it prints `owner` on its first line and the same
   reason on its second, the record file now reads `Reversibility: one-way` with one `Notes:
   Reversibility corrected at <stamp>: <reason>.` line, `decision_routes[D-n].reversibility`
   is `one-way` and no `decision_outcomes[D-n]` exists.
2. **Given** a `Class: retry` record (kind `commit`) written two-way with blast radius `own
   branch` and a ledger where `commit` is rehearsed, **When** it is linted and routed,
   **Then** the lint prints only the OK line, the file is unchanged, and the route is as
   today: `mandate` under autonomous (taken as recommended), `seat` under supervised.
3. **Given** the same record and no `commit` rehearsal, **When** it is linted, **Then** exit
   0 and the line `Reversibility: one-way, not two-way: the commit undo was never rehearsed
   in this workspace; run wuwei undo rehearse commit`; **When** routed, **Then** `owner` plus
   that line, the file is corrected as in scenario 1, and the record is a card.
4. **Given** that correction, **When** `wuwei undo rehearse commit` has run and a second
   `Class: retry` two-way record D-m is routed, **Then** D-m keeps two-way and is taken under
   the mandate; D-n stays with the owner (a repeat route of D-n writes nothing, as today).
5. **Given** a `Class: message` record written two-way, with any ledger, **Then** it is
   corrected to one-way with `a message has no undo (4.9)`; a `Class: other` record, or a
   record without a class, is corrected with `<class> has no registered undo`.
6. **Given** a record written `one-way`, **Then** nothing is printed or rewritten (the CLI
   only lowers a door). **Given** a record written `unsure` whose kind is unrehearsed,
   **Then** it is corrected to one-way like a two-way claim (a Routine class is no longer
   two-way by definition without its undo).
7. **Given** posture observe, guarded or strict, **Then** a correction never changes the
   lint exit code: a valid record lints 0 whatever the ledger.
8. **Given** a record already routed or decided (a repeat route, or a record taken under the
   mandate before the ledger existed), **When** `decision route` runs on it again, **Then**
   nothing is corrected or rewritten and the output is as today.

### User Story 2: `wuwei undo` reverses a mandate decision inside its window (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a cruise answer D-n taken under the mandate with an open undo window (#283),
   **When** the planner runs `wuwei undo D-n` after the owner's `Undo` answer on its card
   (or the owner replies `undo D-n` in the DM, or answers y at a host terminal), **Then** it
   exits 0, the outcome is reverted exactly as `wuwei decision undo D-n` reverts it
   (`decision.reversed` with `undo: true`, the record back to `Decided-by: owner` and
   `Outcome: pending`, the class lowered one level and the reversal counted, 5.8.1), and the
   ledger records `decision` as exercised.
2. **Given** `wuwei decision undo D-n`, **Then** it is the same function (one undo path;
   `decision undo` is kept as an alias).
3. **Given** the window closed, no window, or a seat calling it (no planner card answer, no
   DM reply, no host terminal), **Then** it exits 1 with #283's reason (or, without a
   terminal, `run wuwei undo D-n in a host terminal and answer y`) and writes nothing.
4. **Given** an event id `YYYY-MM-DD:N` naming a `merge.completed` event, **When** `wuwei
   undo <event id>` runs and the owner answers y at a host terminal, **Then** the code host
   opens the revert PR through the same call the merge watch uses on a red base, the merge
   entry records `revert_pr`, an `undo.done` event names the event id, the kind `merge` and
   the revert PR, and the ledger records `merge` as exercised. Without a terminal it exits 1
   naming `run wuwei undo <event id> in a host terminal and answer y`.
5. **Given** an event id naming any other kind, **Then** exit 1: `<kind> has no registered
   undo, so it cannot be undone here; run wuwei why <event id> to see what it changed`
   (every reason names a next step, #362).

### User Story 3: A rehearsal proves an undo on a scratch target (Priority: P1)

**Acceptance Scenarios**:

1. **Given** no rehearsal, **When** `wuwei undo rehearse commit` runs, **Then** in a
   temporary directory outside every configured repository it makes a scratch git
   repository, commits a change, reverts it through the git adapter and checks the tree
   equals the tree before the change; it removes the directory, appends `undo.rehearsed`
   (`kind: commit`) and writes `commit` into `memory/rehearsals.json`; exit 0, prints
   `rehearsed commit`.
2. **Given** `wuwei undo rehearse decision`, **Then** in a temporary scratch workspace with
   the default config it routes a scratch `Class: park` record under the mandate, undoes it
   with the same undo function `wuwei undo D-n` runs, and checks the outcome is reverted;
   then the same event and ledger row for `decision`. `WUWEI_WORKSPACE` is pinned to the
   scratch root for the rehearsal and restored after, so no call inside resolves the real
   workspace, even when the planner's environment sets `WUWEI_WORKSPACE`.
3. **Given** `wuwei undo rehearse merge`, **Then** exit 1: a merge's undo is a revert PR on
   the code host, which has no scratch target; it counts once `wuwei undo <merge event id>`
   ran here. **Given** `message`, `other` or an unknown kind, **Then** exit 1:
   `<kind> has no scratch rehearsal; run wuwei undo rehearse commit or wuwei undo rehearse
   decision`.
4. **Given** a rehearsal step that fails (git missing, revert differs), **Then** exit 2 with
   the reason, no event, no ledger row; no configured repository and no real record was
   touched.
5. **Given** a seat `Write` or `Edit` to `.wuwei/memory/rehearsals.json`, **Then**
   protect_state refuses it as a record under every posture, with a hint naming
   `wuwei undo rehearse`.

### User Story 4: The CLI returns the rehearsal as the next action (Priority: P2)

**Acceptance Scenarios**:

1. **Given** the morning gate approved and `commit` not rehearsed, **When** `wuwei next`
   runs, **Then** it returns a `run` row with state `rehearse`, command `wuwei undo rehearse
   commit` and a why naming that two-way commit records go to the owner until it ran; then
   the same for `decision`; once both ran (or were returned three times, as every row),
   `next` goes on as today and no longer reads the ledger.
2. **Given** `wuwei init --upgrade` or `wuwei doctor`, **Then** each lists the kinds without
   a rehearsal: init prints `Undo not rehearsed: <kinds>; run wuwei undo rehearse <kind> (a
   merge counts after its first wuwei undo)` (not an `Upgraded` line, so doctor's template
   row is unchanged), doctor adds a Workspace
   row `undo rehearsals` with status ok naming rehearsed and unrehearsed kinds, and status
   fail with the fix when the ledger is damaged.

### User Story 5: The owner sees what was undone and what cannot be (Priority: P2)

**Acceptance Scenarios**:

1. **Given** a day with an undo, **When** the report is built, **Then** `## Undone today`
   lists each `decision.reversed` event with `undo: true` as `- D-n: undone (<class>)` and
   each `undo.done` as `- <event id>: <kind> undone (<revert PR>)`, or `none`.
2. **Given** decisions recorded today with reversibility one-way and messages sent today
   (`draft.sent`), **Then** `## Cannot be undone` lists `- D-n: <option> (one-way)` and `-
   message <draft id>: a message has no undo`, or `none`.

### Edge Cases

- A merge record naming two repositories is two-way only when every named one is configured
  with `merge_deploys = false` and `merge` is exercised; naming none is one-way (`add repo:<org>/<name> to
  Context`).
- A damaged or symlinked `memory/rehearsals.json` counts as nothing rehearsed (the safe
  side: one-way, never a block); the lint and route name the fix (`move it aside, then run
  wuwei undo rehearse <kind>`) and doctor fails the row.
- A legacy record without `Class:` routed today has no kind: one-way.
- A route of a record the CLI already corrected finds `one-way` written and changes nothing.
- A record already in `decision_routes` or `decision_outcomes` is never corrected: the
  correction applies to a first route only, so an upgrade never rewrites a record the mandate
  already took.
- CLI-written records that the CLI routes itself through `route_owner` (grant, remote
  denial, pr disposition, outbound learn, MCP) are not seat claims and are not corrected.

## Requirements

### Functional Requirements

- **FR-001**: One module, `cli/wuwei/undo.py`, MUST hold the registry: action kind to its
  undo (the command shown and run) and its proof event: `commit` (git revert on the item
  branch, or delete the unmerged branch; proof `undo.rehearsed`), `decision` (`wuwei undo
  D-n`; proof `decision.reversed` with `undo: true` or `undo.rehearsed`), `merge` (a revert
  PR through `wuwei undo <event id>`, only while the base does not deploy; proof
  `undo.done`). `message` has no undo; any kind not in the registry is one-way.
- **FR-002**: The class-to-kind map MUST be: `approach`, `retry`, `accept-residual`,
  `scope-cut`, `design`, `boundary`, `refactor`, `dependency-bump` to `commit`; `park`,
  `defer`, `re-plan` to `decision`; `merge` to `merge`; `message` to `message`; `other` and
  no class to no kind.
- **FR-003**: A record's measured door MUST allow two-way only when its kind is in the
  registry, the kind is in the ledger, and, for `merge`, at least one repository is named
  and every named one is configured with `merge_deploys = false`. Otherwise a written
  `two-way` or `unsure` is lowered to `one-way` with one reason; a written `one-way` stays.
- **FR-004**: `decision lint` MUST print the correction line after the OK line when the
  workspace is known and MUST keep exit 0 for a valid record; it MUST NOT write the record.
- **FR-005**: On a first route (the id in neither `decision_routes` nor `decision_outcomes`),
  `decision route` MUST apply the correction before any other routing (external,
  mandate, cruise, seat or owner): rewrite the record's active `Reversibility:` line to
  `one-way`, append one `Notes: Reversibility corrected at <stamp>: <reason>.` line, route
  with the corrected fields, and print the reason as the second line of its output.
- **FR-006**: `wuwei undo D-n [--answer <label>]` MUST run the undo function #283 defines for
  `decision undo` (one function; `decision undo` stays as its alias) and, on exit 0, record
  `decision` as exercised in the ledger.
- **FR-007**: `wuwei undo <YYYY-MM-DD:N>` MUST undo a `merge.completed` event by opening its
  revert PR through the code-host adapter, after the owner's y at a host terminal, write
  `undo.done` and record `merge` as exercised; any other event kind exits 1.
- **FR-008**: `wuwei undo rehearse <kind>` MUST exercise the undo of `commit` or `decision`
  on a scratch target in a temporary directory, never on a configured repository or a real
  record (the `decision` rehearsal pins `WUWEI_WORKSPACE` to the scratch root while it runs),
  and on success append `undo.rehearsed` and write the ledger row.
- **FR-009**: `memory/rehearsals.json` MUST be written only by `wuwei undo` and `wuwei undo
  rehearse`; protect_state MUST refuse seat writes to it; `undo.rehearsed` and `undo.done`
  MUST be reserved event kinds produced only by those commands.
- **FR-010**: `wuwei next` MUST return `wuwei undo rehearse <kind>` for each unrehearsed
  scratch kind once the gate is approved, before decision cards.
- **FR-011**: `init --upgrade` and `doctor` MUST list kinds without a rehearsal.
- **FR-012**: The day report MUST add `## Undone today` and `## Cannot be undone`.
- **FR-013**: No new refusal under observe or guarded: the correction is a card, never a
  rejection; the only new refusals are the records floor (the ledger file) and the owner's
  confirmation that #283 already requires for an undo.
- **FR-014**: Docs: `docs/site/concepts.md` (reversibility, undo), `docs/site/reference.md`
  (`wuwei undo`, `undo rehearse`, the correction line, the ledger), `docs/site/daily.md`
  (rehearse step, undo by card, DM or terminal, the two report sections). Design 5.8 gains a
  short paragraph "Measured reversibility (owner, 2026-10-08, #557)".
- **FR-015**: Invariants: (a) a record is two-way only with a registered, rehearsed undo;
  (b) a message is never two-way; (c) `undo` runs only from the planner after a card or a
  DM `undo`, never from a seat; (d) the correction never changes a lint exit code. When
  `tests/test_invariants.py` exists on the base they go there and in the design 9.2 table;
  otherwise into `tests/test_undo.py` as `test_invariant_*`.

### Key Entities

- **Undo registry**: kind to (undo text, proof event, scratch rehearsal or none); a constant.
- **Rehearsal ledger** `memory/rehearsals.json`: `{"kinds": {"<kind>": {"at": "<iso>",
  "by": "rehearsal" | "undo"}}}`; missing means nothing rehearsed.
- **Correction**: (kind, reason) for a record; reason None means the written door stands.

## Success Criteria

- **SC-001**: The four acceptance scenarios of the issue pass as tests.
- **SC-002**: In the invariant grid (every class, every written door, ledger empty, partial
  and full, merge base deploying or not, every posture) no record routes as two-way without
  a registered and rehearsed kind, and no `message` record ever does.
- **SC-003**: The existing suite passes with the ledger standing in as rehearsed for
  `commit` and `decision` (the state a workspace reaches after its first two rehearsals).
- **SC-004**: A rehearsal leaves no file outside a temporary directory except the event and
  the ledger row.

## Assumptions

- #283 (cruise mode) is not on main at spec time (main is at #565), but it is fully built,
  reviewed and pushed on its branch and is in its ship step. The orchestrator note says: if
  #283 has not landed, build the registry so #283 can reuse it. #283's code is frozen, so
  "reuse" means this item calls it: `wuwei undo D-n` calls #283's
  `commands.decision.undo(args, *, root=None, where=None)`, the one undo function (window,
  owner confirmation, reversal, class lowered), and `decision undo` stays as its alias. A
  second D-n undo built here would be the second path the note forbids. The builder first
  fast-forwards the worktree to `origin/main` (T001; the worktree holds only untracked spec
  files, so this writes no commit); if `origin/main` still lacks #283, it stops and reports
  the dependency. The registry's `decision` row names that undo, so #283 needs no change.
- "Refuses a record that claims two-way" is read as refusing the claim, not the record,
  under every posture, strict included: the CLI already knows the right value, so sending
  the record back to the seat only adds a round trip. The record is kept, corrected and
  sent to the owner as a card (#530: no new refusal under observe or guarded).
- `wuwei undo D-n` undoes the decision: the outcome goes back to the owner as a card. The
  code a seat committed on its own item branch under that decision is reverted by the seat
  on the owner's new answer; the CLI does not revert item-branch commits itself. The
  `commit` row exists so the door of a commit-kind record is measured; its undo is proved by
  the scratch rehearsal.
- Autonomy cost: the rehearsals run once per workspace, on scratch, from `wuwei next`
  rows the planner runs without asking the owner. Until they run, two-way records of that
  kind are cards; after, routing is exactly as today. No owner step is added.
- "The lint rewrites it" is read as: the PostToolUse lint reports the correction and the
  routing point writes it. A hook that rewrites the file under the seat would break the
  seat's next Edit; `decision route` is the one routing point and runs before anything acts
  on the record.
- The kind comes from the record's class (FR-002), not a new field: the classes already say
  what the action is, and a seat-written `Action:` field would be one more claim to measure.
- Registered kinds are those whose undo the CLI can run or name today. A PR raise (no PR
  close in the code-host adapter), tracker and docs writes (no delete or restore in their
  adapters) and card config writes (`config.set` carries no previous value) are not
  registered, so they are one-way. Adding one is a registry row plus its adapter call.
  Recorded as Deferred.
- A record corrected for a missing rehearsal stays with the owner after the rehearsal runs
  ("until it ran" applies to the next record of that kind); re-routing it would undo an
  owner route already sent.
- Rehearsal of `commit` uses a scratch git repository in a temporary directory, which
  exercises the same git revert the item branch would use without touching a configured
  repository. Rehearsal of `decision` runs the real route and undo functions against a
  scratch workspace with the CLI's default config and a scratch ledger that marks
  `decision` as rehearsed (the scratch workspace is discarded; only the real ledger counts).
- A merge's undo cannot be rehearsed on scratch; only a real `wuwei undo <merge event>`
  records it. The merge watch's automatic revert on a red base does not write the ledger
  (one producer).
- The event undo for a merge confirms only at a host terminal (an event id does not fit a
  card header of 12 characters); a DM `undo <event id>` is Deferred.
- A damaged ledger counts as nothing rehearsed rather than exit 2: unmeasured is the safe
  side (one-way, a card) and never a block (#530).
- `tests/test_invariants.py` and design 9.2 are not on this base (PR 555 adds them);
  FR-015 says where the rows go either way.
- An autouse fixture in `tests/conftest.py` stands the ledger in as rehearsed for `commit`
  and `decision`, as `quiet_heartbeat` does for the beat; tests of this feature request the
  real reader. Subprocess-driven fixture days that route two-way records write the ledger
  with `wuwei undo rehearse` in their setup.

## Deferred

- Undo kinds for PR raise, tracker writes, docs writes and card config writes (each needs
  its adapter call or the previous value on its event).
- A DM `undo <event id>` and a card for an event undo.
- Counting the merge watch's automatic revert as a merge exercise.
