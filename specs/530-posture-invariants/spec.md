# Feature Specification: The autonomy principle, the posture sweep, and the invariant table with its exhaustive test

**Feature Branch**: `530-posture-invariants`
**Created**: 2026-10-05
**Status**: Draft
**Input**: GitHub issue #530 part B (Scope bullets "Constitution and design" and "Sweep",
owner comment 3, and the invariants of owner comments 4 and 6). Part P (#547: opaque
commands warn, a branch push, a PR raise and a local merge are never owner-only) is on
main; this part builds on it.

## Root cause

The rules that decide what a guard does under each posture live in two places, and neither
states the owner's principle (under observe and guarded a guard is a warning or a card,
never a wall, except the records floor):

- `cli/wuwei/guards/__init__.py:46` (`OWNER_ONLY = {'deploy', 'pr', 'outward.check_tier'}`)
  and `:67-68` (`level`): every refusal of those three checks is levelled `block` with the
  posture line `posture: <area> = block (owner-only action; no setting lowers it)` in every
  posture. That line is printed even where the reason itself already offers the owner's
  card or a fix the seat runs (a held draft gets its own line since #526, a deploy card
  reason since #478, PR raise since #547). So under observe and guarded a refusal of the
  `pr` guard (an alias change, a malformed `--repo`, a non-opaque parse failure) or a
  non-opaque `deploy: could not inspect` reads as a wall no setting lowers. The canary and
  owner-marker refusals, which belong to the records floor, are labelled owner-only too.
- `cli/wuwei/commands/hook.py:249-318` (`posture`) special-cases reasons one issue at a time
  (`NO_REVIEWER`, `RAISE`, `publish: `, `outward: draft `, `UNPARSED`, opaque calls). Nothing
  lists which refusals still end in a wall under observe or guarded, and nothing checks
  that a new rule does not add one.
- A few hook-reachable reasons send the seat to the owner outside the session although a
  seat path exists: `cli/wuwei/guards/deploy.py:369` (`... or ask the owner to run it`),
  `cli/wuwei/grants.py:135` (`... or the owner runs it in a host terminal`),
  `cli/wuwei/guards/commit_push.py:411` (`only the owner changes them, by hand`) and `:424`
  (`if it is truly needed, ask the owner`).
- The design spec (9.1 posture table and its "Floors no posture and no override lowers"
  list), the security page (`docs/site/security.md:44-58`) and the constitution (Principle
  VII) still say owner-only actions "always block" with no way through, and design section
  9 has no list of the safety invariants the guards are checked against.

## Definitions

- **Wall**: a refusal whose only way out is the owner acting outside the session: its
  posture line says `no setting lowers it`, or its reason sends the seat to a host
  terminal or asks the owner to act (`host terminal`, `ask the owner to`, `only the owner`,
  `by hand` as the owner's step), and it names no card.
- **Card**: a refusal whose reason names the owner's card in the session
  (`bin/wuwei decision show D-<n> --widget` or `bin/wuwei drafts show draft-<id> --widget`);
  the owner's recorded answer lets the same call through.
- **Fix**: a refusal whose reason names the plain form or the check the seat runs itself,
  with no owner step (for example `run it without --force: git push origin
  HEAD:refs/heads/<branch>`). A fix is coaching (#362), not a wall.
- **Records floor**: refusals that protect records the workflow writes and the owner
  answers: state, events, config, generated instructions, verdicts, decisions, traces,
  session records (the `records` area), owner disposition markers (an owner record), and
  canary or honeytoken egress (the markers are workspace security records).
- **Owned row**: a refusal whose wall a later item of this program removes; it keeps
  today's behaviour and is listed by issue in the invariant table's notes: #524 (merge
  grants: the merge policy, admin merge, approvals, branch protection, the shepherd's no
  merge), #529 (config and record commands through the card record).

## User Scenarios and Testing

### User Story 1: under observe and guarded no refusal is a wall except the records floor (Priority: P1)

The planner and the seats run a day under observe or guarded. Every refusal they meet is
a warning, a card, or a fix they can run; only records refusals and the rows owned by
#524 and #529 name a floor.

**Independent Test**: `tests/test_invariants.py`, the reason-corpus walk: every reason
string the guards can return, levelled by the real `hook.posture` under observe and
guarded.

**Acceptance Scenarios**:

1. **Given** observe or guarded, **When** the hook levels any reason of the guard reason
   corpus (the reason strings of `cli/wuwei/guards/*.py`, and of the functions they call
   for a refusal in `grants.py`, `security.py`, `drafts.py`, `outward.py` and
   `integrity.py`) for the guard check that returns it, **Then** no enforced
   refusal is a wall, except the records floor and the rows listed by issue (#524, #529)
   in the design 9.2 table notes.
2. **Given** observe or guarded, **When** an owner-only check (`deploy`, `pr`,
   `outward.check_tier`) refuses with a card or a fix, **Then** the refusal carries no
   `owner-only action; no setting lowers it` line; it still blocks (a card waits for the
   answer, a fix waits for the seat).
3. **Given** observe or guarded, **When** the `pr` guard refuses a merge, an admin merge,
   an approval, a branch protection change or a shepherd merge, **Then** the refusal keeps
   today's `owner-only action; no setting lowers it` line (owned by #524).
4. **Given** any posture, **When** an outbound call carries the canary or the honeytoken,
   or a seat posts an owner disposition marker, **Then** it is refused with the line
   `posture: records = block (floor; no setting lowers it)`.
5. **Given** strict, **When** any owner-only check refuses, **Then** the refusal is
   enforced with today's `owner-only action; no setting lowers it` line (unchanged), except
   the records-floor reasons of scenario 4.
6. **Given** observe or guarded, **When** the deploy guard cannot inspect a non-opaque
   call, or the grant card has no repository target, or the commit/push guard refuses a
   hook configuration change or a `GIT_*` override, **Then** the reason names only the
   seat's fix or the card, never a host terminal or the owner.

### User Story 2: the safety invariants are one table and one exhaustive test (Priority: P1)

The owner reads the safety invariants of the guard and decision rules in one table
(design 9.2); `tests/test_invariants.py` checks every one of them on every case of the
product posture x audience class x topic x kind x grant state x umbrella x connector mode,
against the real `outward.classify` (which runs `outward.decide`), the deploy guard
(`deploy.check`, through `grants.gate`) and the record gate (`decision.record_gate` and
`protect_state` with `sessions.gate_topics`).

**Independent Test**: `python -m pytest -q tests/test_invariants.py`.

**Acceptance Scenarios**:

1. **Given** the walk, **Then** it covers at least 2,000 cases, every value of every
   dimension appears, and the walk (every case with its real calls, after the fixture
   workspaces are built) runs in under one second.
2. **Given** every case, **Then** every invariant of the table holds; a failing case
   reports the full tuple (`posture=<p> audience=<a> topic=<t> kind=<k> grant=<g>
   umbrella=<u> mode=<m>`) and the invariant it broke.
3. **Given** a deliberately broken rule (a default tier row `{'audience': 'team', 'tier':
   'block'}` prepended to `outward.DEFAULT_TIERS`, or `grants.active` returning a grant for
   every target), **When** the walk runs, **Then** it reports failures, and the report
   names the full tuple of a failing case.
4. **Given** an invariant whose rule is not built yet (owned by #524 or #529), **Then** the
   table row names the owning issue and the test asserts what holds today for it; no
   invariant is skipped.

### User Story 3: the principle is written where later items read it (Priority: P2)

**Acceptance Scenarios**:

1. **Given** the constitution, **Then** Principle VII states: under observe and guarded a
   guard is a warning or a card, never a wall, with one floor, records (written by the
   workflow, answered by the owner); under strict refusals stay. The Workflow section
   states: any item that adds or changes a guard or decision rule adds its invariant to
   the design 9.2 table and to `tests/test_invariants.py`, or the review refuses it.
2. **Given** design 9.1 and `docs/site/security.md`, **Then** the posture table and the
   floors list are rewritten from the principle: records is the only floor; owner-only
   actions ask on a card below strict (deploy, release, publish and evidence today; merge
   with #524); a guarded `block` is a card or a fix, never a wall.
3. **Given** `bin/wuwei config check`, `bin/wuwei next` (orientation), `docs/site/concepts.md`,
   `docs/site/daily.md` and `docs/site/agent.md`, **Then** none of them says owner-only
   actions always refuse with no way through below strict.

### Edge Cases

- A records refusal and an owner-only card on the same call: both are enforced; the
  records line stays, the card adds no line.
- The heartbeat probe session (`wuwei-heartbeat`) keeps its enforced refusal
  (`grants.py:126`): it is a synthetic probe, never a real action; listed in the table
  notes, not a wall a seat meets.
- A `permissions.deny` match (`grants.py:129`): Claude Code refuses the call before any
  grant could apply; the reason explains it. Not lowered here; recorded under Deferred (a
  grant cannot lift a deny rule that init writes).
- The owner answered `Keep owner-only` (`grants.py:161`): the refusal is the owner's own
  answer to the card, not a wall the workflow put up; listed in the table notes.
- An owner-written block row (`outbound.tiers` with `tier = "block"`, `outward.modes`
  `refuse`, or `outbound.default_tier = "block"`): the owner's own standing answer; the
  invariant is that no shipped default row blocks.
- A broken `config.toml` fails every hook closed before levelling: records floor
  (config is a record); the config fix through a card is #529.
- The plugin integrity gate under guarded (`integrity.py:189`): the way out is
  `integrity reconfirm`, a record command; owned by #529 (a record command after a card
  answer).
- For non-chat kinds (tracker, docs, other) the owner audience and the thread topic have
  no expression (no owner identity, no thread for that kind); those cases use the
  connector's default class and no thread, and the invariants that need them (owner DM,
  thread) apply to the chat kind only.

## Requirements

### Functional Requirements

- **FR-001**: Under observe and guarded, `hook.posture` MUST print no `owner-only action;
  no setting lowers it` line for a refusal of an owner-only check (`deploy`, `pr`,
  `outward.check_tier`), except a reason in the #524 merge family (prefixes `merge policy`,
  `admin merge`, `PR approval`, `branch protection`, `a shepherd seat never merges`),
  which keeps today's line. Levels (block) are unchanged.
- **FR-002**: In every posture, `hook.posture` MUST print `posture: records = block
  (floor; no setting lowers it)` for the canary and honeytoken egress refusal (reason
  starting `outward: security.`) and the owner-marker refusal (reason starting `owner
  disposition markers must be posted by the owner`), whatever check returned it.
- **FR-003**: Under strict every refusal MUST be levelled and labelled as today, except the
  records-floor label of FR-002.
- **FR-004**: These reasons MUST drop their owner-outside alternative, keeping the seat's
  path: `guards/deploy.py:369` (`write it as plain literal commands; a publish step then
  asks the owner on a card`), `grants.py:135` (`name the repository with -R <org>/<repo>
  or run it from a configured repository so the owner can decide on a card`),
  `guards/commit_push.py:411` (`changing Git hook configuration is refused; read it with
  git config --get; WUWEI's hooks stay as bin/wuwei worktree add set them`) and `:424`
  (`unsupported GIT_* override; remove it from the command`).
- **FR-005**: The design spec MUST gain section 9.2, one table of the safety invariants
  (Invariant, Checked by, Notes), with at least the rows I1 to I10 below; owned rows name
  the issue.
- **FR-006**: `tests/test_invariants.py` MUST walk the product of: posture (observe,
  guarded, strict) x audience class (owner, team, company, client, public) x topic (none,
  sensitive, commitment, disagreement, thread) x kind (chat, tracker, docs, other) x grant
  state (none, asked, keep, once, today, always) x umbrella (send, ask) x connector mode
  (adapter, unlisted, send, draft, refuse), assert every invariant on every case, and
  report the full tuple of each failing case.
- **FR-007**: The walk MUST call the real rules: `outward.classify` (with its `decide`),
  `deploy.check` (with `grants.gate` and `grants.active`), `decision.record_gate`,
  `protect_state.check` (with `sessions.gate_topics`), `hook.posture`, and for I3, I6, I9
  and I10 the real `pr` and `commit_push` guards and hook. Results are memoised per
  projection (the dimensions a rule reads), so each real call runs once per distinct
  input.
- **FR-008**: `tests/test_invariants.py` MUST contain the reason-corpus walk of User Story
  1, with its allowlist of owned and exempt rows mirroring the design 9.2 notes.
- **FR-009**: The constitution MUST state the principle in Principle VII and the
  invariant rule in Workflow (version 1.5.0, amended 2026-10-05).
- **FR-010**: No refusal MAY be added under observe or guarded; no posture level, no
  config key, no state key and no event kind changes.

### The invariants (design 9.2)

| Id | Invariant | Checked on |
| --- | --- | --- |
| I1 | Under observe and guarded no path reaches a wall except the records floor | reason-corpus walk; per case: `classify` never blocks unless the owner wrote the matching row (mode `refuse`) |
| I2 | Every held message has a card path that leads to a send | per case: a held `classify` result is a draft (`check_tier` turns it into `APPROVAL_REQUIRED`, which the outward guard holds as a draft card); per posture: hold, approve on the card, the same call sends |
| I3 | A merge happens only at the head the gates checked with green required checks | #524; today: `gh pr merge` and `gh pr merge --admin` are refused by the `pr` guard in every posture, so `wuwei merge` (fresh head, verdicts and checks) is the only path |
| I4 | A message to the owner's own DM always sends | per case, chat kind, owner audience: `classify` sends in every posture, umbrella, mode and topic |
| I5 | No seat, default or hook creates a grant | per case: after the deploy guard and the record gate run, no grant row gained an answer and `grants.standing` is unchanged; the shipped config has no standing grant |
| I6 | A seat never posts an owner disposition marker | per posture: an MCP payload and a `gh pr comment` carrying `WUWEI parked ` are refused |
| I7 | Docs and tracker writes follow `docs.auto` and `tracker.auto` | per case, WUWEI's own adapter write (mode adapter), team audience, no topic: a kind in `docs.auto` or a category in `tracker.auto` sends, one outside is held; under the send umbrella a connector write sends (#535) |
| I8 | A record command runs from the planner only after a card answer outside strict | per case: `bin/wuwei decide D-<n> <option>` passes `protect_state` only for the planner whose card for D-n was asked, never for a seat, never under strict; #529 extends this to `config set` |
| I9 | A branch push and a PR raise with recorded evidence succeed from the planner and the builder below strict | per posture: push and `gh pr create` with recorded evidence pass the hook (#547) |
| I10 | Under observe and guarded no opaque read-only command is refused | per posture: a script read, a `$(...)` read and a `python3 -c` print pass the hook below strict (#547) |

Grant expectation (I1, I5, deploy guard, per posture x grant state): `once` and `today`
let the call through; `always` lets it through below strict and is ignored under strict;
`none` and `asked` refuse with the card (`bin/wuwei decision show D-<n> --widget`); `keep`
refuses naming the owner's kept answer.

## Success Criteria

- **SC-001**: The reason-corpus walk finds no wall under observe or guarded outside the
  records floor and the rows listed by issue.
- **SC-002**: `tests/test_invariants.py` runs at least 2,000 cases with its walk under one
  second, and the mutation tests fail it with the full tuple printed.
- **SC-003**: The full suite passes (`python -m pytest -q`).

## Assumptions

- A fix (a refusal naming the plain form or check the seat runs itself, with no owner
  step) is coaching, not a wall: the owner's complaint is about having to permit, and a
  fix needs no permission. Turning every fix into a warning under guarded would let a
  force push or a push to the default branch through under the supervised answer, and
  turning each into a card would ask the owner for things a seat can correct. The owner
  can reverse this; the test's wall definition is one regular expression.
- Canary and honeytoken egress and owner disposition markers belong to the records floor:
  the markers are workspace security records, and a disposition marker is an owner record.
  Their behaviour is unchanged; only the posture line names the floor truthfully.
- The guarded `block` level stays as it is for `publish` and `integrity`: under guarded a
  publish refusal is a card (deploy, release, publish, evidence) or a fix, and the
  integrity refusal's way out is a record command (#529). No posture level changes.
- The #524 merge family keeps its owner-only line until #524 makes merging grantable;
  #530 part E removes the owned marks once #524 and #529 are on main.
- The design spec edit is the owner's own request (issue #530), so the constitution's
  "amended only by its owner" holds.
- The constitution carries the "add your invariant" rule; CONTRIBUTING.md already points
  to the constitution, so no CONTRIBUTING.md edit.
- The interview's Observe answer text (`cli/wuwei/interview.py:216`) is rewritten by #530
  part C (the first setup question); this part leaves it.
- The walk's umbrella values are `send` and `ask` (the two setup answers); `block` is an
  owner-written choice covered by `tests/test_outward.py`.
- "Runs in under a second" is measured on the product walk: every case and every real
  call it makes, after the fixture workspaces are written. Building the fixtures and the
  reason-corpus walk (a few hundred `hook.posture` calls that write events) sit outside the
  timed part; the whole file stays within a few seconds.
- Code host kind is left out of the product: its parties need the code-host port; its rows
  are covered by `tests/test_outward.py`.

## Deferred

- `grants.py:129`: `permissions.deny` rules that `init` writes for deploy and release
  verbs (`guards/deploy.py` `PERMISSIONS_DENY`) refuse a call a grant would allow; the
  owner still runs it in a host terminal. A follow-up issue decides whether init writes
  them below strict (relates to #530 part C, the harness allowlist card).
