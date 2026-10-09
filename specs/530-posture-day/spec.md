# Feature Specification: The fixture day for autonomous and supervised, and the invariant table checked against what landed

**Feature Branch**: `530-posture-day`
**Created**: 2026-10-08 (revised 2026-10-09 against main at 705250f)
**Status**: Draft
**Input**: GitHub issue #530 part E: "the fixture day acceptance for autonomous and
supervised, and the invariant table checked against everything that landed". Closes #530.
Owner, 2026-10-05: autonomy over structure; reuse the #362 reason shape, the card and grant
flow of #478 and #506, and the existing fixtures.

## Build base

Every part this one checks is on `main` at 705250f: part P (#547), A (#544), B (#555,
`tests/test_invariants.py` and design 9.2), C (#596, the `autonomy` setup question), #524
(#575, the merge grant), #526, #528, #529, #533, #551 (#564, `wuwei next`), #510 and #511.
The worktree branch was cut at 327dd57, before B, C, #524 and #551. The build runs on a
base at or after 705250f (task T001 checks it and stops with a report otherwise). File and
line references below are to 705250f.

## Root cause

Nothing proves #530's acceptance as a whole, and the invariant table lags what merged.

1. No fixture day runs under a setup answer. `tests/test_path_day.py:68`
   (`test_the_day_closes_walking_only_next`, the #551 hook-routed day) walks `wuwei next`
   but pre-answers every setup question (`tests/test_path_day.py:31-34`), runs solo with no
   review channel (`:19`), answers every card with its first option and never counts them
   (`:91-95`), and merges by replaying a server-side merge (`:104-109`), so WUWEI never
   merges in it. It also records each card before the `AskUserQuestion` PostToolUse
   (`:93-94`), so `calibrate --answer` never sees a card answer and never writes the
   autonomy keys (#529 FR-005). `tests/test_e2e_day.py:14` (`test_scripted_day`) has the
   same replayed merge (`:85`) and records a decision at the host terminal (`day.owner`,
   `:81`).
2. The I1 note and `OWNED` still name merged issues. `tests/test_invariants.py:40-47`
   marks five walls `#524` and five `#529`; design 9.2 I1 (line 1945) says "Owned: the
   merge family (#524); config and integrity re-confirmation through the card record
   (#529)". Both issues merged. #524 kept the session `gh pr merge` refusal by design (its
   US5: the reason names `bin/wuwei merge`, the one journaled path), and approval,
   `--admin`, branch protection and the shepherd merge stay the owner's (constitution VII:
   "never by approval or override"). #529 left all five of its walls in place
   (`cli/wuwei/guards/commit_push.py:91`, `:114`, `:158`, `cli/wuwei/guards/pr.py:296`,
   `cli/wuwei/integrity.py:192`). The `MERGE` comment `cli/wuwei/guards/__init__.py:59`
   still says "owner-only until #524 makes merging grantable".
3. I3 checks the wrong thing. `tests/test_invariants.py:378-383` (`i3`) asserts only that
   the `pr` guard refuses `gh pr merge` with a `MERGE` prefix, and the I3 note (line 1947)
   says "asserted today as gh pr merge refused in every posture". The rule #524 built (a
   merge happens only at the gated head with green required checks, whatever the grant) is
   not in the invariant test.
4. I8 does not check `config set --from-card`. `tests/test_invariants.py:217-236`
   (`Rules.record`) runs only `bin/wuwei decide D-1 once`; the I8 note (line 1952) says
   "#529 extends it to `config set`", in the future tense, after #529 merged.
5. Three merged rules have no row: #526 (a thread reply follows its recorded participants),
   #528 (CAP comes from the host) and #533 (the internal-state word list is scoped by
   audience and kind). Ids I11 to I18 are taken by #558, #559, #560, #579 and #530 C, so
   the new rows are I19, I20 and I21.
6. Three more merged rules pinned their invariants in their own test files because
   `tests/test_invariants.py` was not on their base, and each said the rows move there when
   it exists: #557 (measured undo, `tests/test_undo.py` `test_invariant_*`), #556 (novelty,
   `tests/test_novelty.py` `test_invariant_*`) and #552 (the register-or-view rule,
   `tests/test_graph.py`). They have no row in design 9.2. #567 (process depth) added no
   row for the same reason; its rule (depth comes from the CLI's tier, standard until
   tiered, never the builder's prediction for a gate reader) is the depth clause of I15,
   which #579 built on `dispatch.depth`, but I15 does not check `dispatch.depth` itself.

Rule coverage after this feature (F2 of the 530e review), each merged rule against its row:
merge grants I3, I5 and I18 (#524, #530 C); measured undo I22 (#557); shadow promotion I13
and I14 (#560); process depth I15 (#567); pace I15 to I17 (#579, PR #594); novelty I23
(#556); error budget I11 (#558); calibration I12 (#559); graph register I24 (#552, PR #573);
thread reply I19 (#526); host CAP I20 (#528); audience-scoped lint I21 (#533). The DORA keys
(#586, PR #595) only read records and decide nothing, so they need no row.

## User Scenarios and Testing

### User Story 1: An autonomous day asks only the gate and the client card (Priority: P1)

The owner answers Autonomous on the setup card. A whole day runs by walking `wuwei next`:
plan, morning gate, build, gates with one FIX round, PR raise, review ping, merge by WUWEI
and close. The owner answers the morning gate and one draft card for a message to a client
channel. Every other decision is taken under the mandate and listed in the report.

**Independent Test**: `python -m pytest -q tests/test_path_day.py -k posture`.

**Acceptance Scenarios**:

1. **Given** a fixture workspace (non-solo `Day`: review channel `CREVIEW`, client channel
   `C0CLIENT` of class `client`) with every setup question answered on an earlier day
   except `autonomy`, **When** the planner walks `wuwei next` and answers the `calibrate`
   card with `Autonomous`, **Then** `autonomy.mode` is `autonomous` in the loaded config,
   written by the card answer with no host-terminal command.
2. **Given** that day, **When** it walks to `done`, **Then** the item is `merged`, the code
   host recorded one `merge` call at the gated head made by WUWEI (`pr act`), and the day
   closed (`day.closed` event, `report.md`, the retro file).
3. **Given** that day, **Then** apart from the setup card (the `calibrate` row, holding the
   autonomy question only), the cards answered are exactly the `gate` row's card and one
   draft card for the client message: `decision_routes` is empty, `drafts`
   holds exactly one row and its channel is `C0CLIENT`. On failure the assertion prints
   each extra card id with its `cisr`, grant action or draft channel.
4. **Given** a Routine record (`Class: retry`, blast radius `item A`), a Consequential
   record (two-way, blast radius `outside`, clear margin) and a scoring Exploratory record
   (two-way, blast radius `item A`, a lead), **When** each is routed with
   `wuwei decision route D-n`, **Then** each prints `mandate` and `report.md`'s
   `## Taken under mandate` lists all three, the Consequential one first, each naming
   `decisions/D-n.md` and `reverse: bin/wuwei decide D-n`.
5. **Given** the merge ran with no card, **Then** the events hold one `grant.used` with
   decision `merge.default_tier` and action `merge`, no `grant.asked`, and `report.md`'s
   `## Grants` lists the merge.
6. **Given** the client draft card answered `Send now` and its record command run by the
   planner, **When** the same MCP call is sent again, **Then** it passes (exit 0).
7. **Given** that day, **Then** every `hook.refusal` reason is the one `specify first`
   refusal of design 5.10 or names a card (`bin/wuwei decision show D-` or
   `bin/wuwei drafts show draft-`).

### User Story 2: A supervised day asks on each owner-only action (Priority: P1)

The same day under the Supervised answer, plus one deploy after the merge, asks the owner
before each owner-only action.

**Independent Test**: the same test, parametrized with `Supervised`.

**Acceptance Scenarios**:

1. **Given** the Supervised answer, **When** the same day runs, **Then** a card is answered
   for the merge (a `grant.asked` event and a `decision_routes` row with grant action
   `merge`), for the deploy `gh workflow run deploy.yml -R acme/widget` (`grant.asked`,
   action `deploy`), for the Consequential and the Exploratory record (`decision_routes`
   rows with that `cisr`), and the client message is a draft card.
2. **Given** each card answered through its own record command from the planner (the
   allowing option for a grant card, the recommendation for a decision card, `Send now` for
   a draft), **Then** the retried action passes, the item ends `merged` by WUWEI's own merge
   call, and the day reaches `done` with no host-terminal command.
3. **Given** the supervised day, **Then** every `hook.refusal` reason is the `specify first`
   refusal or names a card, as in US1.7.

### User Story 3: The invariant table matches what merged (Priority: P1)

Every rule #524, #526, #528, #529, #533, #552, #556, #557 and #567 added has its row in design 9.2 and its check in
`tests/test_invariants.py`, and no row or `OWNED` entry names an issue that has merged.

**Independent Test**: `python -m pytest -q tests/test_invariants.py`.

**Acceptance Scenarios**:

1. **I3 (#524)**: **Given** posture x grant (none, once, today, a standing line) x head
   (gated and green, moved after the gates, a red required check), **When**
   `merge.execute` runs on the `tests/test_merge.py` case, **Then** the code host `merge`
   call happens exactly when the head is gated and green and the grant matches (once or
   today in every posture, a standing line below strict), and no `grant.used` is written
   otherwise. In the walk, a session `gh pr merge` is refused in every posture and its
   reason names `wuwei merge`. The I3 note drops "asserted today".
2. **I8 (#529)**: **Given** the card asked or not, **Then**
   `bin/wuwei config set cap 2 --from-card D-1` through `protect_state` passes from the
   planner exactly when `decide D-1 once` does, and never from a seat. The note drops
   "#529 extends it".
3. **I19 (#526)**: **Given** a reply in thread `C0TEAM/1.2` whose recorded participant is
   one person of the case's audience, **Then** below strict a team participant sends under
   both umbrellas and a client or public participant is held as a draft (exit 1), never
   blocked.
4. **I20 (#528)**: **Given** free memory (below the floor, one seat above it, eight seats
   above it) x cores (1, 4) x owner `cap` (0, 3) x `budget.tokens_per_day` (0, set with no
   recorded usage), **Then** `calibrate.host` returns the owner's cap when it is set, else
   the host fit (1, 1, and the core count for eight seats), and a budget never raises it.
5. **I21 (#533)**: **Given** an `outward.patterns` word in the text, **Then** a tracker,
   docs or code-host write is never refused or held in any posture; team or company chat is
   never held and is refused only under strict; a client or public chat that an owner row
   would send without the word is held as a draft whose reason names the word.
6. **I22 (#557)**: **Given** every class and no class x a ledger with no kind and with
   every registered kind, **Then** `undo.measured` lets the written door stand only for a
   registered kind the ledger holds, never for a `message`; a seat cannot write
   `memory/rehearsals.json`.
7. **I23 (#556)**: **Given** a two-way Routine record naming a repository the workspace never
   touched, under autonomous, **Then** `wuwei decision route` sends it to the owner and names
   the target; a seat cannot write `memory/targets.json`.
8. **I24 (#552)**: **Given** the fixture's people, channel classes and connector modes,
   **Then** the views of the register built from that config equal the config's sections
   (`graph.drift` is empty).
9. **I15 (#567)**: **Given** an untiered item row, **Then** `dispatch.depth` is `standard`,
   and for a gate reader a builder's prediction never lightens it.
10. **Stale marks**: **Given** any `#<n>` in an `OWNED` note or in the I1 row's `Owned:`
   clause, **Then** no `specs/<n>-*` directory exists; a failure names the entry.
11. **Mutation**: **Given** a deliberately broken rule for each of I19 to I24, **Then**
   the walk fails and prints the full tuple.

### Edge Cases

- Setup cards are not the day's cards. The fixture pre-answers every setup row except
  `autonomy` on an earlier day (as `tests/test_path_day.py` does for all rows), so the
  `calibrate` card holds the autonomy question only. It comes after the gate in
  `wuwei next` (`cli/wuwei/commands/next.py:202`); the gate runs under the shipped defaults
  and everything after it under the answer.
- The autonomous day has no deploy. A deploy is a publish target, and I18 keeps every
  publish target on a card under both answers (`merge.default_tier = "today"` covers only a
  merge on a configured repository). The supervised day adds one deploy to prove it asks.
- The review ping under supervised: the umbrella is `ask`, so the ping may be held as a
  draft. US2 asserts inclusion, so the driver answers that draft card with `Send now` and
  pings again; under autonomous the ping must post with no card.
- A Routine record under supervised goes to the owner (part A). That card is allowed by US2.
- The record ids: the three records take the next free `D-n` when written, so a grant card
  or a rehearsal record written earlier never collides with them.
- Spec mode runs advisory under observe (`specmode.mode`, design 5.10), so the autonomous
  builder meets no spec-first refusal and the fake builder skips the spec steps there; under
  supervised the builder's first source write before its spec is refused once. It is the
  seat's step, not an owner card.
- The review ping is not a `wuwei next` row: the driver runs `wuwei pr ping-check` and
  `wuwei pr ping` on the first `pr` row, as `test_scripted_day` does.

## Requirements

### Functional Requirements

- **FR-001**: The fixture days reuse `tests/fakes/day.py` `Day` and the `wuwei next` walk of
  `tests/test_path_day.py`; the walk loop is extracted once and shared, with no new harness
  and no edit to `tests/fakes/day.py`.
- **FR-002**: The setup answer is given on the `calibrate` card the walk returns: the
  `AskUserQuestion` PostToolUse with the chosen label is recorded before the widget's record
  command runs. The label is read from the widget (`Autonomous` or `Supervised`), never
  hard-coded config keys.
- **FR-003**: The days count the cards answered apart from the setup card: the `gate` row,
  every `decision_routes` row and every `drafts` row. Under autonomous it is the gate plus
  one client draft.
- **FR-004**: WUWEI merges in both days: the fake code host shows the review approved at
  the head with green required checks and allowed squash, `wuwei pr act` merges, and the
  test flips the host's PR to merged only after WUWEI's `merge` call.
- **FR-005**: Under autonomous the report lists each mandate decision with its record and
  reversal command, and the merge under `## Grants`.
- **FR-006**: Under both answers every refusal seen is the spec-first refusal or names a
  card.
- **FR-007**: Design 9.2 gains rows I19 (#526), I20 (#528), I21 (#533), I22 (#557), I23
  (#556) and I24 (#552); I3 (#524), I8 (#529) and I15 (#567) are updated; the I1 note moves the merge family to Exempt with its reason and
  names the walls #529 left as this feature's Deferred follow-up, with no issue number.
- **FR-008**: `tests/test_invariants.py` checks I19 to I24 in the walk, each on only
  the dimensions it declares in `READS`; I3 gains one parametrized test over posture x
  grant x head on the `tests/test_merge.py` case; the walk stays under its 1.0 s CPU
  budget.
- **FR-009**: A test fails when an `OWNED` note or the I1 `Owned:` clause names an issue
  whose spec directory exists under `specs/`.
- **FR-010**: Defects the days expose are fixed only when the fix is a few lines at the
  shared spot, each with its failing step as the test and its invariant row if it changes a
  rule; anything larger is recorded under Deferred with the step and reason, and no
  assertion is weakened, skipped or marked xfail.
- **FR-011**: No new refusal under observe or guarded, and no rule change except an FR-010
  fix.

## Success Criteria

- **SC-001**: `tests/test_path_day.py` and `tests/test_invariants.py` pass, with
  `tests/test_merge.py` and `tests/test_e2e_day.py` unchanged and passing.
- **SC-002**: Each posture day runs in under 60 seconds, like the walking day.
- **SC-003**: When the autonomous day sees an extra card, the failure names the card id and
  what it was for.
- **SC-004**: `test_invariants_hold` stays under 1.0 s CPU.

## Assumptions

- A card is what the owner answers: the morning gate, a decision card (`decision_routes`,
  which includes grant cards, `cli/wuwei/grants.py:93`) or a draft card (`drafts`). Setup
  questions belong to setup, not the day.
- "Client-facing" is a message to a channel of class `client`
  (`outbound.channel_classes`); the fixture adds `C0CLIENT`. Configured channels and
  repositories are seen targets (`cli/wuwei/novelty.py:37`), so the novelty gate adds no
  card in the fixture.
- The publish action of the supervised day is a configured deploy workflow
  (`[deploy] workflows = ["deploy.yml"]`); `gh release create` stays in `permissions.deny`.
- The merge-family refusals are permanent, not walls a later item removes: a session merge
  is coached to `bin/wuwei merge` (#524 US5), and approval, `--admin`, branch protection
  and a shepherd merge are the owner's under constitution VII. They move from `OWNED` to
  `EXEMPT` with that reason; `hook.posture` and the guard texts do not change.
- The five walls #529 left are not defects the day exposes and are larger than FR-010
  allows (each needs a card a guard writes); they stay in `OWNED`, re-noted to the
  follow-up under Deferred.
- Cruise mode may attach a rule and an undo window to a mandate answer; it still records
  `decided_by: mandate` (`cli/wuwei/commands/decision.py:112`), so the report lists it.
- The pinned `test_invariant_*` tests of #556 and #557 and the register test of #552 stay
  where they are; the walk adds one compact check per row over the same runtime functions,
  so nothing is duplicated as a second fixture.
- Neutral fixtures only: `acme/widget`, `example/project`, item `A`, channels `CREVIEW`,
  `C0TEAM` and `C0CLIENT`.

## Deferred

- Follow-up of #530 (to be filed): the walls #529 left. `config add-repo` in
  `commit_push.check` and `pr.check`, the missing default branch and the empty fast check
  through a card and `config set --from-card`, and `integrity reconfirm` under guarded as a
  card. Until then they stay in `OWNED` with this note.
- Follow-up (to be filed): the posture orientation text `cli/wuwei/commands/next.py:13-19`
  still says "merges and approvals stay owner-only" under observe and guarded; since #524
  and part C a merge runs under a grant or the autonomous merge default. Not exposed by the
  days (they walk `next --json`, not the orientation), so not fixed here.
- Any day step that fails for a reason larger than FR-010 allows: named here by the
  builder with the step and the reason.
