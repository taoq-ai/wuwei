# Feature Specification: Merge grant

**Feature Branch**: `524-merge-grant`
**Created**: 2026-10-08
**Status**: Draft
**Input**: GitHub issue #524: merging a pull request is a grantable owner action like deploy:
the card offers once, today or always per repository, the gate pre-approves planned merges,
and the shepherd merges only at the head the gates checked with green required checks.

## Root cause

A merge has exactly one way through, the auto-merge policy, and nothing the owner can answer
or configure opens a second one:

- `cli/wuwei/merge.py:198-309` (`check`) is the only merge decision. Its first requirement is
  `merge.auto` (`:208`), default off, followed by the rest of the auto-merge eligibility and
  pacing (breaker `:212`, daily cap `:216-218`, quiet hours `:219`, approved plan, risk flags
  and cycle budget in `item_evidence` `:143-166`, diff size `:247`, never-auto paths `:256`,
  soak `:296`). Any miss is `Refused`, printed as `the owner merges; ask the owner` (`:307`).
- `cli/wuwei/merge.py:340-369` (`execute`, behind `wuwei merge` and `wuwei pr act`) merges
  only when `check` passes; on a refusal it stops. There is no grant lookup and no card.
- `cli/wuwei/pr_actions.py:517-523` (`act`, state `approved`) calls `merge.execute` and
  prints `owner merge decision required`, so the planner tells the owner to run the merge in
  a host terminal.
- `cli/wuwei/grants.py:8-10` (`ACTIONS`) holds deploy, release, publish and evidence only;
  `:13-14` says merge is an owner step the plan lists, so `plan()` (`:239`) writes no gate
  card for a planned merge and `cli/wuwei/plan.py:104-117` (`owner_steps`) lists it as a
  line the owner does by hand.
- `cli/wuwei/workspace.py:80` (`grants.standing.action`) accepts only deploy, release and
  publish, so an Always allow answer for a merge could not be stored.
- `cli/wuwei/guards/pr.py:26-33` (`merge_check`) refuses a session `gh pr merge` with the
  policy's `ask the owner` reason, and the hook adds `no setting lowers it`
  (`cli/wuwei/guards/__init__.py:44-46`). Nothing names a command that could merge.
- `adapters/code_host/github.py:554-558` (`merge`) always merges with `--squash`, and
  nothing reads whether the repository or its base allows squash, so a repository without
  squash fails only at the code host, after the merge intent is journaled.

## User Scenarios and Testing

### User Story 1: A granted merge runs without a host terminal (Priority: P1)

The owner allowed merges on `example/project` today. The planner walks `wuwei next`, which
returns `wuwei pr act example/project#7` for an approved PR. The PR's gates passed at its
head, its required checks are green and the required approval is there. `merge.auto` is off.
`pr act` merges the PR at that head and records `grant.used`. Nobody types a command in a
host terminal.

**Independent Test**: the `case` workspace of `tests/test_merge.py` with `auto = false`, a
`grants` row `{action: merge, target: repo:example/project, answered: today}`, the fake code
host.

**Acceptance Scenarios**:

1. **Given** that PR, the gated head, green checks, satisfied reviews and a today grant on
   `repo:example/project`, **When** `wuwei merge example/project#7` (or `wuwei pr act` on the
   approved PR) runs under guarded, **Then** it exits 0, the code host `merge` call carries
   the gated head sha, the day has one `grant.used` event `{decision: D-n, action: merge,
   target: repo:example/project, scope: today}` before `merge.intent`, and `merge.auto`
   follows with status `accepted`.
2. **Given** an `Allow once` grant instead, **When** the first merge runs, **Then** it merges
   and the row is spent; **When** a second PR on the same repository is ready, **Then** the
   guard asks again (a new card).
3. **Given** a planned card answered `today` whose target is `pr:example/project#7`, **When**
   that PR is ready, **Then** it merges under that card; a different PR on the repository
   does not.
4. **Given** a standing `[grants]` line `{action = "merge", target = "repo:example/*"}`
   under guarded, **When** the PR is ready, **Then** it merges with `scope: always`.

### User Story 2: Without a grant the owner gets one card, never a wall (Priority: P1)

**Acceptance Scenarios**:

1. **Given** the same ready PR and no grant under guarded (or observe), **When**
   `wuwei merge` or `wuwei pr act` runs, **Then** it exits 1, writes one decision card
   `Allow merge on example/project?` with `Keep owner-only`, `Allow once`, `Allow today`,
   `Always allow`, stores a pending `grants` row `{action: merge, target:
   repo:example/project}`, makes no code host `merge` call, and the reason ends with
   `the owner decides: bin/wuwei decision show D-n --widget`. A second run names the same
   card and writes no second one.
2. **Given** the card answered `Keep owner-only`, **When** the merge runs again, **Then** it
   exits 1 naming the kept card and the host terminal.
3. **Given** strict and no grant, **When** the merge runs, **Then** it exits 1, writes no
   card, and the reason says merges are owner-only here (`merge.default_tier =
   owner_only`) and prints the exact command for a host terminal:
   `gh pr merge https://github.com/example/project/pull/7 --squash --match-head-commit <sha>`.
4. **Given** strict with `merge.default_tier = "ask"`, **When** the merge runs, **Then** the
   card is written without `Always allow`.
5. **Given** strict and a standing merge line, **Then** the line is ignored (no merge, the
   owner-only reason) and `doctor` warns about it, as for deploy.

### User Story 3: No grant ever merges a PR that is not ready (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a today grant and a head that moved after the gates (the gate verdicts name an
   older sha), **When** the merge runs, **Then** it exits 1, no merge call, no `grant.used`,
   no card, and the reason names the missing gates at the current head (`pre-PR gates not
   passed at current HEAD <sha>: ...; run the named gate for this HEAD`), followed by
   `no grant lifts this; run bin/wuwei pr act example/project#7 once it holds`, never the
   auto policy's `the owner merges; ask the owner`.
2. **Given** a today grant and a required check that is not green, or a missing required
   approval at head, or an outstanding changes request, or an unresolved thread, **Then** no
   merge, and the reason names that condition.
3. **Given** a today grant and a repository or base that does not allow squash merges,
   **Then** no merge, and the reason names the repository, the base and the host-terminal
   command.
4. **Given** a today grant and a repository with `merge_deploys = true` or an environment
   base, **Then** no merge under the merge grant (merging there is a deploy, 4.7).

### User Story 4: A planned merge is pre-approved at the morning gate (Priority: P2)

**Acceptance Scenarios**:

1. **Given** a lead candidate with `owner_actions: [{action: merge, target:
   repo:fixture-org/app}]`, **When** `plan propose` runs, **Then** a planned gate card is
   written (`Allow today`, `Ask when it happens`, `Keep owner-only`), `plan gate` lists it
   with the other planned cards, and `plan.md` no longer lists the merge as an owner step.
2. **Given** a target `pr:fixture-org/app#7`, **Then** the planned card's question names
   `fixture-org/app#7` (not a truncated name) and its row target is
   `pr:fixture-org/app#7`.

### User Story 5: A session `gh pr merge` names the command that can merge (Priority: P3)

**Acceptance Scenarios**:

1. **Given** a session runs `gh pr merge 7 -R example/project --squash` and the auto policy
   does not clear it, **Then** the pr guard still refuses (the merge must run through
   `wuwei merge`, which journals and watches it) and the reason names
   `bin/wuwei merge 7`, which merges under the owner's grant or asks on a card.

### Edge Cases

- `Allow once` is spent before the merge intent is written; a host failure after that does
  not give the grant back (fail closed).
- A pending card for the repository is reused; the PR named in the reason is the current one.
- `merge.default_tier = "owner_only"` under guarded: no card; a grant the owner already
  recorded (planned card or a once or today answer) still lets the merge through.
- An exit 2 from the auto policy (unmeasured evidence) never falls through to the grant path.
- A shepherd seat (`WUWEI_SEAT_ROLE=shepherd`) still never merges.

## Requirements

### Functional Requirements

- **FR-001**: `merge` is a grant action: `grants.ACTIONS['merge'] = ('merge', 'merges')`;
  `grants.action(rule)` returns `merge` for a rule starting with `merge: ` and keeps
  `deploy` for the deploy guard's `merge_deploys` and `environment branch merge` rules.
- **FR-002**: `merge.check(..., granted=True)` checks the 4.6 preconditions at the current
  head and skips only the auto-merge eligibility and pacing: `merge.auto`, the breaker, the
  daily cap, quiet hours, approved-plan membership, risk flags, the cycle budget, the diff
  size, the never-auto paths and the soak window. Everything else holds whatever the grant
  says: a configured repository with `merge_deploys = false`, no open merge intent, measured
  post-merge observations, one linked item, open non-draft PR on a non-environment base,
  gate verdicts PASS at the current head, required checks green, branch protection and
  required approvals at head, no changes requested, threads and reply obligations clear, the
  review bot (when configured) clear at head, squash allowed, and the PR unchanged during the
  check.
- **FR-002a**: A granted-path refusal reads `merge: <condition>; no grant lifts this; run
  bin/wuwei pr act <ref> once it holds`; the auto path's refusal text is unchanged.
- **FR-003**: Both paths require squash: the code host `protection` result carries
  `squash: bool` (the repository's `allow_squash_merge`, narrowed by a ruleset
  `pull_request` rule's `allowed_merge_methods`), validated as a boolean like the other
  protection fields; when false the reason names the repository, the base and the owner's
  host-terminal merge.
- **FR-004**: `merge.execute` tries the auto policy first, unchanged. On its exit 1 (never on
  exit 2) it runs the granted check; on a pass it resolves the merge tier: `owner_only` with
  no recorded grant returns exit 1 with the exact host-terminal command; otherwise it calls
  `grants.gate` for `repo:<org>/<name>` (plus the PR's own `pr:<org>/<name>#<n>` row), and a
  grant is recorded or spent (`grant.used`) before the merge intent; no grant writes or reuses
  the card and returns exit 1 naming it.
- **FR-005**: `[merge] default_tier` is `ask` or `owner_only`; unset follows the posture
  (`owner_only` under strict, `ask` otherwise). It only decides what happens when no grant
  matches; it never creates a grant.
- **FR-006**: `grants.standing.action` accepts `merge`; standing merge lines are ignored under
  strict and `doctor` warns, through the existing generic code.
- **FR-007**: `grants.plan` writes a planned card for a merge owner action, with the repository
  or PR name taken after the target's prefix (`repo:` or `pr:`).
- **FR-008**: `pr act` on an approved PR prints `<ref>: <reason>` from `merge.execute`
  (the card or the missing condition), and the pr guard's `gh pr merge` refusal names
  `bin/wuwei merge <pr>`.
- **FR-009**: Docs say it: design spec 4.6 and 9.1 carry a dated amendment (#524), the
  concepts Grants section and the configuration reference cover merge, `merge.default_tier`
  and the standing action list, and the lead charter (and its generated agent) says a merge
  becomes a card the gate pre-approves.

### Key Entities

- **Grant row** (`state.grants[D-n]`): unchanged shape; `action` may be `merge`, `target` is
  `repo:<org>/<name>` (refusal card) or as planned (`repo:` or `pr:`).
- **Standing line** (`[grants] standing`): unchanged shape; `action` may be `merge`.

## Success Criteria

- **SC-001**: A PR with a today grant, gated head, green required checks and satisfied
  reviews merges from `wuwei pr act` with exit 0 and one `grant.used` event.
- **SC-002**: Without a grant under guarded, exactly one card per repository is written and
  the reason names it; under strict no card and the exact command.
- **SC-003**: With any grant, a moved head, a red required check, missing approvals or no
  squash yields no code host merge call.
- **SC-004**: The auto-merge path's existing tests pass unchanged apart from the `squash`
  field added to protection fixtures.

## Assumptions

- The merge decision the issue names is the owner's recorded answer: a once or today card,
  a planned card or a standing line (or the auto policy clearing the PR, as today). #511's
  headless merge will reuse `merge.execute`; the heartbeat session check in `grants.gate`
  stays as is here.
- The owner's grant replaces what 4.6 calls eligibility and pacing (auto switch, risk flags,
  paths, size, soak, cap, quiet hours, breaker), because those exist to decide whether WUWEI
  may merge without the owner. The 4.6 preconditions stay, including threads, obligations and
  the review bot, since they describe whether the PR is ready.
- The refusal card is per repository (`repo:` target), so `Allow today` covers every ready
  PR there; a planned card may name one PR (`pr:` target).
- WUWEI merges only with `--squash` (4.6 mechanics). A repository without squash is not
  merged by WUWEI; choosing another method is not built.
- Granted merges are journaled, undo-logged and watched like auto-merges; a red base after
  one trips the breaker, which stops only the auto path.
- `gh pr merge` typed in a session stays redirected to `wuwei merge`, which owns the
  journal and the post-merge watch; this is an existing redirect with the command named, not
  a new refusal, so #530 holds. The hook's posture line on it is unchanged.
- Novelty (#556) applies through `grants.gate` as for deploy; a configured repository is
  never novel.
- No new event kind and no new state key: the card, the row and `grant.used` are the #478
  ones.

## Deferred

- #511 (headless merge): `grants.gate` returns the host-terminal reason for the heartbeat
  session before it looks up a grant, so a scheduled run cannot merge under a recorded grant
  until #511 orders that check after the lookup. Recorded here, built there.
