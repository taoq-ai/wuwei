# Feature Specification: delete grants; the merge policy alone decides a merge

**Feature Branch**: `b3-decision-framework` (feature directory `specs/816-grants-out/`)

**Created**: 2026-10-11

**Status**: Draft

**Input**: Issue #816, part 11 of the #789 deletion pass: "chore(grants): delete grants; the merge policy alone decides a merge".

## Context

Grants (#478, #524, #530) turn an owner-only refusal into a decision card. The owner answers
`Keep owner-only`, `Allow once`, `Allow today` or `Always allow`, and the answer is a grant
that lets the same action through. Four paths raise these cards:

- deploy, release and publish (deploy guard);
- a push or PR raise without recorded evidence (push, PR and `pr raise` guards);
- a merge the policy does not clear (`merge.execute` falls back to `merge.by_grant`, which
  reruns `merge.check(granted=True)` and skips eligibility and pacing);
- a planned owner action the lead lists, as a gate card.

`merge.default_tier` adds `ask`, `owner_only` and a `today` auto-grant. `[grants] standing`
holds the Always lines, and `wuwei grants` lists and revokes them.

Each card asks the model and the owner to reason about the process: which grant scope to pick,
whether a grant still applies, when to rerun. The pass keeps the edges in code instead. A merge
happens only through the merge policy. Deploy, release and publish refuse from the session,
and the owner runs them in a host terminal. A missing evidence check is the seat's to run.

Parts 9 (#814) and 10 (#815) are already done in this batch. Cruise, novelty and the undo
door are gone, so `grants.py` no longer has a novelty branch, cruise no longer calls
`grants._record`, and `novelty.py` (which imported `grants.REPO`) no longer exists.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The merge policy alone decides a merge (Priority: P1)

The planner runs `wuwei pr act <pr>` on an approved PR. `wuwei merge` merges when the policy
clears it. When it does not:

- a condition the policy clears later (soak, quiet hours, daily cap, a gate to wait on,
  reviews, checks) is a wait;
- every other refusal, which a grant used to lift, is an owner block. `wuwei next` turns it
  into exactly one owner decision for that PR.

**Why this priority**: "When to merge" is process control kept in code (pass plan). Every
merge a grant cleared before must still be decided deterministically. The policy clears it,
or `next` names one owner decision.

**Independent Test**: execute a merge with `merge.auto = false`, and one in quiet hours, then
read the `merge.policy_blocked` payloads and the `next` row.

**Acceptance Scenarios**:

1. **Given** a raised PR whose repository has `merge.auto = false`, **When** `wuwei merge`
   runs, **Then** it exits 1 and makes no merge call. It writes no decision record and no
   `grant.*` event. It writes `merge.policy_blocked` with `owner: true`. The reason starts
   `merge policy: owner decides:` and names the condition.
2. **Given** the same for `merge.auto` off, a tripped breaker, an item not in the approved
   plan, a risk flag, a trust-surface item without a security gate, a spent cycle budget, a
   never-auto path, or a diff over `max_changed_lines`, **When** `wuwei merge` runs, **Then**
   the event carries `owner: true`.
3. **Given** quiet hours, the daily cap, the soak window, a gate not passed at head, missing
   approvals, red checks or an owner path, **When** `wuwei merge` runs, **Then** it exits 1
   and the event carries `owner: false`. The policy clears it later, or (owner path,
   owner_merge) the reason already names the owner's host-terminal command, as today.
4. **Given** a raised item whose PR's latest merge event today is a `merge.policy_blocked`
   with `owner: true`, **When** `wuwei next` runs, **Then** it returns one row with state
   `merge`, item set, and the command `wuwei plan park <item> --reason "the merge policy does
   not clear <pr>"`, instead of the `pr` row.
5. **Given** the latest block has `owner: false`, or a later `merge.intent` exists, **When**
   `wuwei next` runs, **Then** it returns the `pr` row as today.
6. **Given** `owner_merge` set on the item, **When** `wuwei merge` runs, **Then** it refuses
   as today: `owner merges: owner_merge set by ...`, `owner: false`.

### User Story 2 - Owner-only edges refuse without a grant path (Priority: P1)

**Acceptance Scenarios**:

1. **Given** observe, guarded or strict, **When** a seat runs a deploy, a release (`gh
   release create`, a tag push through `gh`) or a `deploy.deny` command, **Then** the deploy
   guard refuses with `publish: <command> (<rule>) is owner-only: ask the owner to run it in
   a host terminal`. It writes no decision record, no `grants` state and no `grant.*` event.
2. **Given** guarded, **When** a seat pushes without fast-check evidence at HEAD, **Then** the
   push guard refuses with the evidence reason (`fast check "<c>" has not passed for HEAD
   ...; run bin/wuwei build check <item>`) and no card. Under observe it warns, and under
   strict it refuses, as today.
3. **Given** guarded, **When** `gh pr create` or `wuwei pr raise --item` runs before the gates
   pass at HEAD, **Then** it refuses with the gate reason and no card. Under observe it warns
   and raises, as today.

### User Story 3 - Planned owner actions are plan lines (Priority: P2)

**Acceptance Scenarios**:

1. **Given** a lead candidate whose `owner_actions` lists a deploy, release, publish or merge,
   **When** `wuwei plan propose` runs, **Then** `plan.md` lists it as `Owner-only: <action>
   <target> (owner step)`, and no decision record or gate card is written.
2. **Given** `wuwei plan gate`, **When** it prints, **Then** the widget list holds the gate
   question only (plus MCP cards).

### User Story 4 - Nothing names grants (Priority: P2)

**Acceptance Scenarios**:

1. **Given** the CLI, **When** `wuwei grants` runs, **Then** argparse refuses it as an invalid
   choice (SystemExit 2).
2. **Given** a config with `[grants]` standing lines or `merge.default_tier`, **When** it
   loads, **Then** it loads with an unknown-key warning (after #799). `init --upgrade`
   removes both once `workspace.RETIRED` names them, and no line is honoured.
3. **Given** a day, **When** the report is written, **Then** it has no `## Grants` section.
4. **Given** the autonomy setup answer, **When** it is applied, **Then** it writes no
   `merge.default_tier`.

### Edge Cases

- Day state may still hold `grants` rows and old `grant.asked`, `grant.used` and
  `grant.revoked` events. Nothing reads them. Their kinds leave `signal.SILENT`, so on the
  upgrade day an old row may classify as a nudge.
- An open grant card from before the upgrade stays a pending decision route. `next` keeps
  asking it until the owner answers, and the answer records only the option.
- A PR blocked for the owner and then fixed by a new push needs `wuwei plan park` undone by
  the owner, or a new item. The park row comes only from today's latest merge event for that
  PR.
- A workspace that relied on `merge.default_tier = "today"` to merge its own repositories
  merges only where `repos.<n>.merge.auto = true` after the upgrade. Its other merges become
  owner blocks.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `merge.check` MUST take no `granted` input. A refusal that a grant lifted before
  MUST raise `Owner(Refused)`: `merge.auto` off, breaker tripped, the item evidence rules
  (approved plan, risk flags, trust-surface gate set, cycle budget), a never-auto path, and
  the size rule. Quiet hours and the daily cap MUST stay plain `Refused` (waits), and the
  soak MUST stay a wait result.
- **FR-002**: `merge.execute` MUST NOT call a grant path. On exit 1 it MUST append
  `merge.policy_blocked` with `owner: true` exactly when `check` refused with `Owner`.
- **FR-003**: `wuwei next` MUST return one owner row (the park row of US1 scenario 4) for a
  raised item whose PR's latest merge event today is an owner block, and MUST otherwise
  return the `pr` row unchanged.
- **FR-004**: The deploy guard MUST refuse every owner-only rule in every posture with a
  reason naming the host-terminal step, and MUST NOT write decision records, state rows or
  events.
- **FR-005**: The push guard, the PR guard and `pr raise` MUST return the evidence or gate
  reason under the posture's publish level (off passes, warn records and warns, block
  refuses), with no card.
- **FR-006**: `plan propose` MUST write no planned grant card. Every understood owner action
  is an `(owner step)` line. `understood` and `OWNER_ACTIONS` move into `plan.py`.
- **FR-007**: These MUST be gone:
  - `grants.py` and `commands/grants.py`;
  - the config `[grants]` and `merge.default_tier`;
  - the state key `grants`;
  - the events `grant.asked`, `grant.used` and `grant.revoked`;
  - `merge.by_grant` and `grants.standing`;
  - the report `## Grants` section;
  - the autonomy answer's `merge.default_tier` key;
  - the doctor standing-grant row.
- **FR-008**: The `_record` builder MUST move into `calibrate.py`, its only remaining caller,
  with `revisit` required.
- **FR-009**: No charter, skill, generated agent, docs page or design spec section describes
  grants, grant cards or `merge.default_tier`.

### Key Entities

- **merge.policy_blocked** payload: `pr`, `exit`, `reason`, `owner` (bool).

## Success Criteria *(mandatory)*

- **SC-001**: Every touched test file passes. No test is loosened; only tests of deleted code
  are deleted.
- **SC-002**: `grep -rniE '\bgrants?\b|by_grant|granted|default_tier|Allow once|Allow today|Always allow'`
  over `cli/`, `charters/`, `skills/`, `agents/`, `hooks/`, `templates/`, `scripts/`,
  `docs/site/` and the design spec returns only three kinds of hit:
  - the ZIRAN role-grant audit;
  - the AUTH path heuristic `'grants*'` in `dispatch.CLASS_PATHS`;
  - `outbound.default_tier`, which is unrelated.
- **SC-003**: Every merge `wuwei merge` performs passed `merge.check` with no input but the
  PR, workspace and code host. Every refused merge that a grant cleared before produces
  exactly one owner row in `next`.

## Assumptions

Open questions answered with the recommendation (strict, non-interactive):

1. The owner decision for a blocked merge is the park row (the escalate pattern `next`
   already uses for a spent round budget). The owner then merges in a host terminal (the hook
   refuses `gh pr merge` in session) or leaves it parked. No new command.
2. Quiet hours, the daily cap and the soak are waits. The policy clears them later, so they
   need no owner decision. That matches the rule "the policy clears it, or `next` names one
   owner decision".
3. `owner_merge` and the owner-path rule are unchanged. They never had a grant path.
4. The heartbeat and `permissions.deny` special cases in the deploy refusal collapse into
   the one host-terminal reason.
5. Tag pushes: the deploy guard's `tag push` rule refuses a tag push from the session in every
   posture. `commit_push` keeps its below-strict `continue` for tags (only its comment
   changes), because the native pre-push hook runs the same check for the owner's own
   host-terminal push.
6. The refusal-string lint (`test_reason_corpus_has_no_wall`, kept by #798) gets one EXEMPT
   row for the deploy guard's owner-only reason. Constitution VII names owner-only publishing
   as a floor next to records. This is the pass plan's edge list (deploy and force push stay
   refused by the hook).
7. `'grants*'` stays in `dispatch.CLASS_PATHS` AUTH. It is a generic auth heuristic for a
   target repository's files. It leaves `GUARD_CODE`, which named this module.
8. An answer to an old grant card records the option only. It writes no `[grants]` line.
9. The design spec and constitution edits are part of the owner-approved #789 pass.
10. The hero image text (`scripts/build-hero.py`, `Allow once`) is a picture of a card. It is
    left for the site rewrite in pass part 24.
