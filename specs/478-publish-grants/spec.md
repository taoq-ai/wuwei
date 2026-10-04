# Feature Specification: an owner-only action asks the owner instead of blocking, the answer is a decision and a grant, the gate pre-approves planned deploys, and the reason names the action and the target

**Feature Branch**: `478-publish-grants`

**Created**: 2026-10-04

**Status**: Draft

**Input**: GitHub issue #478, "fix(publish): an owner-only action asks the owner instead of
blocking (keep owner-only, once, today, always) and records the answer as a decision; standing
grants in config with revoke; the gate question pre-approves planned deploys; the reason names
the action and target". Owner, 2026-10-04, first real items on 0.15.0: the planner ran
`gh workflow run "<Deploy Production workflow>" -R <org>/<repo> --ref main` and the guard
answered "could not inspect: workflow name or ID requires unavailable workflow resolution".
Owner: "Instead of simply blocking, this should be something that the owner decides on the
day, or a general preference that the harness can ask daily or 'never ask again'."

## Root cause (read and reproduced on main, 6168be8, read-only)

Reproduction: the notes name no dry-run workspace, so a scratch workspace in a temp directory
(one `[[repos]]` entry `fixture-org/app` at `.`, `deploy.workflows = ["deploy-production.yml"]`)
ran `wuwei.guards.deploy.check` in process:

| Command | Result on main |
|---|---|
| `gh workflow run "Deploy Production" -R fixture-org/app --ref main` | `(2, 'deploy: could not inspect: workflow name or ID requires unavailable workflow resolution; write it as plain literal commands, or ask the owner to run it')` |
| `gh workflow run deploy-production.yml -R fixture-org/app --ref main` | `(1, 'deploy: refused by deploy.workflows; deploying is an owner action: stop and ask the owner to run it')` |
| `gh run rerun 123 -R fixture-org/app` | `(2, 'deploy: could not inspect: workflow run requires unavailable workflow resolution; ...')` |
| `gh release create v1.0.0 -R fixture-org/app` | `(1, 'deploy: refused by release create; deploying is an owner action: ...')` |

1. **A quoted workflow name is treated as unparseable.** `workflow()`
   (`cli/wuwei/guards/deploy.py:50-60`) raises `unknown('workflow name or ID requires
   unavailable workflow resolution')` whenever the marked list or the target is not a
   `.yml` filename, and `gh run rerun` (`deploy.py:225-227`) and the API rerun
   (`deploy.py:165-167`) raise the same. `check`'s `except` (`deploy.py:318-319`) turns it
   into `deploy: could not inspect: ...`. The command was parsed fine; the classifier
   only cannot prove the name is not a marked deploy, and the reason names that internal
   instead of the action and the target.
2. **Every owner-only refusal is a wall.** `deny()` (`deploy.py:37-38`) returns "stop and
   ask the owner to run it", and the hook (`cli/wuwei/commands/hook.py:249-289` through
   `guards.level`, `cli/wuwei/guards/__init__.py:46,64-65`) adds `posture: publish = block
   (owner-only action; no setting lowers it)`. Nothing is recorded, no card is printed, and
   the only way through is the owner typing the command in a host terminal, every time.
3. **No grant exists anywhere.** `workspace.SCHEMA` has no `[grants]`
   (`cli/wuwei/workspace.py:52-214`; `protect_state.GUARD_KEYS` at
   `cli/wuwei/guards/protect_state.py:105` already reserves the name), the day state has no
   grant key, and the morning gate card (`cli/wuwei/plan.py:195-218`) carries only
   `Approve` and `Change something`, so a deploy the plan already names still interrupts the
   day.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A deploy refusal asks the owner on a card (Priority: P1)

A seat runs a production deploy command with no grant. The guard records a decision `D-n`
("Allow deploy on fixture-org/app?") with the action, the exact command (redacted), the
target, the item and the seat, and refuses with the #362 reason naming the action, the target
and the one command that prints the card. The planner asks the card with AskUserQuestion and
records the answer with the card's `record` command; the seat reruns the same command and the
guard lets it through on the matching grant.

**Why this priority**: it is the owner's report: the floor stays, but the owner decides once
instead of typing the command.

**Independent Test**: in a fixture workspace, `deploy.check` on
`gh workflow run deploy-production.yml -R fixture-org/app` writes `D-1` and its state row and
returns exit 1 with the reason; `wuwei decide D-1 "Allow today"` (owner confirmation faked);
the same check returns `(0, '')` and appends `grant.used`.

**Acceptance Scenarios**:

1. **Given** a seat running a production deploy command with no grant, **When** the hook runs,
   **Then** the guard records the decision, the reason is `publish: <command> on
   fixture-org/app is a deploy (<rule>), owner-only under <posture>; the owner decides:
   bin/wuwei decision show D-n --widget`, the hook prints it with no posture line and exits
   2, and `bin/wuwei decision show D-n --widget` prints the card.
2. **Given** that card, **When** the owner answers `Allow today` and the planner records it
   with `bin/wuwei decide D-n "Allow today"`, **Then** the same command passes, a
   `grant.used` event names `D-n`, and after `wuwei close` the command is refused again with
   a new card.
3. **Given** the card, **When** the owner answers `Allow once`, **Then** the next run passes
   once and the run after it asks again.
4. **Given** the card, **When** the owner answers `Keep owner-only`, **Then** later runs today
   are refused with a reason that names `D-n` and says the owner runs it in a host terminal,
   and no new card is written.
5. **Given** a seat retries before the owner answers, **When** the guard refuses again,
   **Then** the reason names the same `D-n`; no second record is written.
6. **Given** the card under observe or guarded, **Then** its options in order are `Keep
   owner-only (Recommended)`, `Allow once`, `Allow today`, `Always allow`. **Given** strict,
   **Then** `Always allow` is not offered.

---

### User Story 2 - A standing grant in config, listed and revocable (Priority: P1)

`Always allow` writes one line to `[grants]` in `config.toml` (action class, target pattern,
scope `always`, the decision that created it and the date). `wuwei grants` lists the standing
grants with their decisions and today's day grants; `wuwei grants revoke <n>` removes one in a
host terminal and records `grant.revoked`.

**Why this priority**: "never ask again" is the second half of the owner's request.

**Independent Test**: answer `Always allow` under guarded; `config.toml` holds the line;
move the clock to the next day; the command passes; `wuwei grants revoke 1`; the command asks
again.

**Acceptance Scenarios**:

1. **Given** `Always allow` under guarded, **Then** `[grants]` holds the line with `D-n`,
   `wuwei grants` lists it, the command passes on later days, and `wuwei grants revoke 1`
   returns the action to owner-only (the next run writes a new card).
2. **Given** strict, **Then** the card offers no `Always allow`, a grant line in config is
   ignored by the guard, and `wuwei doctor` prints one warn row per ignored line naming its
   action, target and decision.
3. **Given** a seat, **When** it runs `bin/wuwei grants revoke 1` or `bin/wuwei config set
   grants.standing ...`, **Then** `protect_state` refuses it as an owner action.

---

### User Story 3 - The gate pre-approves planned owner-only actions (Priority: P2)

When the lead's proposal lists an owner-only action for a candidate (a deploy step in its
tasks, a release item), `plan propose` writes one grant decision per action with the options
`Allow today`, `Ask when it happens` and `Keep owner-only`, `plan.md` names it under the
candidate, and `plan gate` prints the gate question followed by one card per open planned
action. The planner asks them in the same AskUserQuestion call and records each answer before
`plan approve`, so an `Allow today` answer is the day grant and the day runs without an
interruption.

**Why this priority**: it removes the mid-day interruption for work the plan already names; the
refusal card (US1) covers everything else.

**Independent Test**: propose a candidate with `owner_actions: [{"action": "deploy",
"target": "repo:fixture-org/app"}]`; `plan gate` prints a list whose second entry is the
`D-n` card with the three labels; record `Allow today`; the deploy guard passes.

**Acceptance Scenarios**:

1. **Given** a planned item with a deploy step, **Then** `plan gate` prints the gate widget
   and a card `D-n: G-1 <item> deploys fixture-org/app: allow today, ask when it happens, or
   keep owner-only? ...` and the answer `Allow today`, recorded before dispatch, creates the
   day grant.
2. **Given** the answer `Ask when it happens`, **Then** no grant exists and the first run
   writes a US1 card.
3. **Given** `plan propose` runs again on the same day, **Then** no second record is written
   for an action whose planned card is still open.

---

### User Story 4 - The reason names the action and the target (Priority: P1)

**Acceptance Scenarios**:

1. **Given** `gh workflow run "Deploy Production" -R fixture-org/app` with
   `deploy.workflows` set, **Then** the reason names the deploy and `fixture-org/app` and
   never mentions resolution.
2. **Given** a deploy command whose repository cannot be named (no `-R`, no `GH_REPO`, a cwd
   outside every configured repository), **Then** the refusal is exit 1 with a reason naming
   the action and asking for `-R <org>/<repo>` or a configured repository's checkout; no card
   is written.

---

### User Story 5 - Docs say the owner decides (Priority: P3)

`docs/site/concepts.md` explains grants in plain words (once, today, always; who can create
one; how to revoke), `docs/site/configuration.md` documents `[grants]`,
`docs/site/security.md` says the floor is that you decide and a grant is how you decide once
instead of every time, and `docs/site/daily.md` shows the gate line.

### Edge Cases

- The watch heartbeat's probe session (`wuwei-heartbeat`) gets the refusal with no record,
  no card and no grant check, so the probe never writes decisions.
- A command matching the workspace's Claude Code `permissions.deny` rules (`PERMISSIONS_DENY`,
  `deploy.py:28-34`, for example `gh release create*`) gets no card: a grant cannot lift a
  host permission rule, so the reason says the owner runs it in a host terminal.
- An unreadable state or a raced `once` spend fails closed (exit 2, reason printed) through
  the guard's existing `except`.
- `gh workflow run` with no `deploy.workflows` configured stays clean, as today; a name equal
  to a marked entry and an unproven name or ID both become a deploy card; a `.yml` target not
  marked while every marked entry is a filename stays clean, as today.
- A refusal that is not an owner-only rule (unparsed input, an unknown git alias, an
  unresolved push destination) keeps today's exit-2 reason and gets no card.
- `close_requested` ends every day grant at once; a refused close still ends them.
- `Always allow` recorded after the posture changed to strict is refused by `wuwei decide`
  with a reason; the card under strict never offered it.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Every `deploy` guard refusal that comes from an owner-only rule (each `deny()`
  site and the three former "workflow resolution" sites) MUST go through one grant gate that
  either lets the call through on a matching grant or refuses with the decision reason.
- **FR-002**: A quoted workflow name or ID is the action's target; when `deploy.workflows` is
  set and the target is not proven to be an unmarked filename, the command MUST be classified
  as a deploy, never as "could not inspect" or "requires resolution".
- **FR-003**: The action class MUST be one of `deploy`, `release` or `publish`, mapped from the
  refusing rule; the target MUST be `repo:<org>/<name>` from `-R`/`--repo`/`GH_REPO`, the API
  path, the pull request, or the configured repository holding the cwd.
- **FR-004**: With no matching grant, the guard MUST write one decision record (class
  `other`, `Decided-by: owner`, `Reversibility: one-way`) through `decision.write`, route it
  through `decision.route_owner`, store a `grants` state row, and reuse an open row for the
  same action and target instead of writing another.
- **FR-005**: The card MUST be the existing `decision show D-n --widget`; its options in order
  are `Keep owner-only` (recommended in every posture), `Allow once`, `Allow today` and,
  outside strict, `Always allow`.
- **FR-006**: The answer MUST be recorded only by `wuwei decide D-n "<label>"` (the planner
  after an asked card outside strict, or the owner in a host terminal), which stores it on the
  row; `Always allow` also appends the `[grants]` line through the owner edit frame. No seat,
  config default or hook creates a grant.
- **FR-007**: A matching grant (standing outside strict; `today` while `close_requested` is
  false; `once` not yet spent) MUST let the call through and append `grant.used` with the
  decision, action, target, scope, session and item; a `once` grant is spent under the state
  lock.
- **FR-008**: `[grants] standing` MUST be a list of `{action, target, scope = "always",
  decision, date}` lines validated by `load_config`; its default is empty.
- **FR-009**: `wuwei grants` MUST list the standing grants numbered from 1 with their
  decisions (marked ignored under strict) and today's day grants; `wuwei grants revoke <n>`
  MUST remove line `n` through the owner edit frame and append `grant.revoked`; it is an owner
  action in `protect_state`.
- **FR-010**: Under strict, the guard MUST ignore standing grants and `wuwei doctor` MUST print
  one warn row per line naming it.
- **FR-011**: A candidate in the lead's proposal MAY carry `owner_actions` (`action`,
  `target`); `plan propose` MUST write one planned grant card per open action and name it in
  `plan.md`; `plan gate` MUST print a JSON list: the gate widget, then each open planned card.
- **FR-012**: The hook MUST print a `publish:` reason without the posture line; every other
  refusal keeps its posture line.
- **FR-013**: The day report MUST show one line per decision that granted runs today, for
  example `- deploys run under grant D-3: 3`.
- **FR-014**: `grants` is a producer-owned state key and `grant.asked`, `grant.used` and
  `grant.revoked` are reserved event kinds.
- **FR-015**: Docs, the plan skill, the common and lead charters, design spec 4.7 and the
  constitution's Principle VII MUST say the owner decides deploys, and how.

### Key Entities

- **Grant card**: a decision record `D-n` written by the guard or by `plan propose`, plus a
  `grants` state row (action, target, rule, command, item, seat, planned, answered, spent).
- **Day grant**: a row answered `today` (until close) or `once` (until spent).
- **Standing grant**: a `[grants] standing` line in `config.toml`, answered `always`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The owner's reported command produces a reason naming the deploy and the target,
  and after one recorded `Allow today` it runs with no further owner step until close.
- **SC-002**: Each of the five acceptance scenarios in the issue has a passing test.
- **SC-003**: A Bash call the deploy guard does not refuse imports no new module (the grant
  module loads only on a refusal).
- **SC-004**: The full suite passes.

## Assumptions

- "Prints the widget" is met by the reason naming `bin/wuwei decision show D-n --widget`, as
  the #493 draft card does; the hook does not dump the widget JSON into the deny reason.
- `Keep owner-only` is the recommendation in every posture (the issue marks it recommended
  under strict and lists it first): the floor's safe default, and the existing card rule
  (recommended first) keeps the issue's order. The planned gate card recommends `Allow today`
  outside strict and `Keep owner-only` under strict.
- The decision evaluator requires a "Do nothing" or "Defer" title; `Keep` joins them as a
  status-quo title (the drafts card already says `Keep as draft`), so the label is exactly
  `Keep owner-only`. The DM's `drop it` uses the same rule.
- A grant matches on action class and target, not on the exact command: `Allow once` lets one
  run of that action on that target through.
- Targets are repositories (`repo:<org>/<name>`, glob characters allowed in a standing
  line). `env:` and `channel:` targets are deferred: environment-branch refusals target the
  repository, and outward messages keep the #493 draft card.
- Scope is the `deploy` guard: deploys, releases and tag pushes, `deploy.deny` publishes, and
  pushes and merges to environment branches (force pushes to them included). The `pr` guard
  (approvals, admin merges, the merge policy) and the outward tier stay as they are.
- A day grant ends when `close_requested` is set, even if close is then refused; no write is
  needed at close.
- A grant lifts only the hook. Claude Code's `permissions.deny` rules from `wuwei init` stay,
  and the code host and the credential layout (design 4.5) still decide.
- The grant row lives in day state, like the #493 draft allowance and `decision_outcomes`; it
  carries the same trust as those records.
- The owner may still write a `[grants]` line with `config set` in a host terminal; that is
  the owner deciding.
- A race of two seats on the same target may write two cards; ponytail, accepted.
- Owner amendment: the issue is the owner's decision to amend design 4.7 ("refused always")
  and the non-goal "Deploying": the guard still refuses, and only the owner's recorded answer
  lets the call through. Constitution Principle VII ("nothing ever deploys") conflicts with it;
  the conflict is raised here and resolved by amending both texts in this feature, dated
  2026-10-04, #478.

## Deferred

- `env:` and `channel:` grant targets.
- Lifting `permissions.deny` for a granted command (would make releases grantable).
- Grants for the `pr` guard's owner-only actions.
