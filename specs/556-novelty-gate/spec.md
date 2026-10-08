# Feature Specification: Novelty gate

**Feature Branch**: `556-novelty-gate`
**Created**: 2026-10-08
**Status**: Draft
**Input**: GitHub issue #556: a decision or guarded action on a target the workspace never
touched runs one level lower (a card under autonomous); the target clears after one owner
answer or one unreversed mandate action; `init --upgrade` seeds the seen set from config and
events.

## Root cause

Blast radius is only known for targets the workspace has touched, but nothing in the CLI
knows which targets those are, so the level earned on familiar targets is applied to every
target:

- `cli/wuwei/commands/decision.py:60-63` (`decide`, the `decision route` command) calls
  `mandate()` under `autonomy.mode = autonomous`, and `mandate()` (`:89-106`) takes any
  Routine, Consequential or scoring Exploratory record as recommended. Nothing reads what the
  record touches: a Routine record about a repository, dependency or channel the workspace
  has never seen is taken without a card.
- `cli/wuwei/grants.py:99-101` (`active`): a standing `[grants]` line matches its target with
  `fnmatchcase`, so `repo:<org>/*` lets a deploy, release or publish through on a repository
  that appeared today.
- `cli/wuwei/outward.py:752-764` (`check_tier`): when the tier table (or
  `outbound.default_tier = "send"`) says send, the call is sent whatever the channel id; a
  channel the owner has never posted to is treated like the team channel used every day.
- There is no seen set: no `memory/targets.json`, no reader, and
  `cli/wuwei/commands/init.py:312` (`upgrade`) seeds nothing;
  `cli/wuwei/guards/protect_state.py:294-324` (`_protected_name`) has no entry that would
  keep a seat from writing one.

## User Scenarios and Testing

### User Story 1: A Routine record on a new repository asks once (Priority: P1)

The owner runs autonomous (the default). A seat writes a Routine record whose Context names
`repo:fixture-org/new`, a repository the workspace never touched. The owner gets one card
that says it is the first time for that repository. After the owner answers, the next
Routine record on that repository is taken under the mandate with no card.

**Independent Test**: neutral workspace in `tmp_path`, default config, two `Class: retry`
records naming `repo:fixture-org/new`, `decision route` on each with the owner's answer in
between.

**Acceptance Scenarios**:

1. **Given** autonomous and a Routine record whose Context names `repo:fixture-org/new`
   (not in config, not in `memory/targets.json`), **When** `wuwei decision route D-1` runs,
   **Then** it exits 0 and prints `owner` on its first line and `first time for
   repo:fixture-org/new; one owner answer on a card clears it` on its second;
   `decision_routes[D-1]` has `novel: ["repo:fixture-org/new"]`; the `decision.routed` event
   carries the same `novel` list; `memory/targets.json` has the target with today's
   `first_seen` and `cleared: null`; no `decision_outcomes[D-1]` exists.
2. **Given** that route, **When** `wuwei decision show D-1 --widget` runs, **Then** the
   card's question ends with `First time for repo:fixture-org/new: your answer clears it.`
3. **Given** that card, **When** the owner records an answer (`wuwei decide D-1 A` with the
   card answered in the planner session), **Then** `memory/targets.json` shows the target
   `cleared: {by: owner, evidence: D-1, at: <now>}`.
4. **Given** the cleared target, **When** a second Routine record D-2 naming the same
   repository is routed, **Then** it prints `mandate` and is taken as recommended.
5. **Given** `autonomy.mode = "supervised"` and the same record, **When** it is routed,
   **Then** routing is as today (`seat` for a two-way own-branch record written for the seat,
   `owner` otherwise); an owner route still records `novel` and an owner answer still clears.

### User Story 2: An outward send to a first-time channel holds once (Priority: P1)

**Acceptance Scenarios**:

1. **Given** autonomous, `outbound.default_tier = "send"` (or a tier row that sends) and a
   chat write to channel `C9` that is not in config and not in the seen set, **When** the
   outward PreToolUse guard runs, **Then** it exits 1 with a draft held whose reason reads
   `first time for channel:C9; approving this draft clears it, then the tier table decides`
   and the draft card (`drafts show <id> --widget`) shows that reason.
2. **Given** the owner approves that draft, **Then** `channel:C9` is cleared with
   `evidence: <draft id>`, the repeated call passes once as today, and a later different
   message to `C9` follows the tier table (sent).
3. **Given** a channel in `outbound.work_channels`, `external_channels`, `channel_classes`,
   a tier row, `shepherd.review_channel` or `outbound.owner.slack.dm`, **Then** it is never
   novel.
4. **Given** a message that only the owner reads (`owner_only`), **Then** novelty is not
   consulted.
5. **Given** a dropped draft, **Then** the channel stays novel.

### User Story 3: A standing grant does not cover a new repository (Priority: P2)

**Acceptance Scenarios**:

1. **Given** autonomous, a standing grant `repo:fixture-org/*` for `deploy` and a deploy
   command naming `-R fixture-org/new` (not configured, not seen), **When** the deploy guard
   runs, **Then** the standing line does not apply: a grant card is written as for an
   ungranted action and the refusal names `first time for repo:fixture-org/new`.
2. **Given** the owner answers that card with Allow once, Allow today or Always allow,
   **Then** the target is cleared and a later deploy on it is matched by the standing line
   again. **Given** Keep owner-only, **Then** the target stays novel, so the standing line
   stays off for it and the kept answer refuses for the rest of the day as today.
3. **Given** a configured repository or an exact standing target, **Then** the standing line
   applies as today.

### User Story 4: An upgraded workspace is not asked about what it already uses (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a workspace with day directories over the last 30 days whose CLI-written events
   name targets (the `target` of a `grant.used` event, or a `repo` value `<org>/<name>` of
   any CLI-written event) and whose day state holds sent or approved chat drafts,
   **When** `wuwei init --upgrade` runs, **Then** it prints `Upgraded memory/targets.json: <n>
   targets seen in the last 30 days`, each target is in the seen set with `cleared: {by:
   seed}`, and no card is asked for them afterwards.
2. **Given** `--dry-run`, **Then** it prints `Would upgrade memory/targets.json: ...` and
   writes nothing.
3. **Given** a `note` event (the one kind any seat may append with `wuwei event`) naming a
   target, or an event older than 30 days, **Then** the seed ignores it.
4. **Given** a workspace without `memory/targets.json` that never ran the upgrade, **When**
   novelty is first consulted, **Then** the same seed runs first, so a plugin update without
   `init --upgrade` is not a wall either.

### User Story 5: A seat cannot write the seen set (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a seat `Write`, `Edit` or Bash redirect to `.wuwei/memory/targets.json`, **When**
   protect_state runs, **Then** it is refused as a record (the records floor), under every
   posture, with a hint that names the CLI writers.

### User Story 6: The owner sees what was new today (Priority: P3)

**Acceptance Scenarios**:

1. **Given** targets first seen today, **When** the day report is built, **Then** a
   `## First time today` section lists each as `- <target>: cleared by owner (<evidence>)`,
   `cleared by seed` or `not cleared`, or `none`.
2. **Given** `wuwei why repo:fixture-org/new`, **Then** it prints the first-seen date and how
   it was cleared (or that config names it, or that it is not cleared and what clears it).
3. **Given** `wuwei why D-1` for a novel route, **Then** one extra line `novel: first time
   for repo:fixture-org/new`.

### Edge Cases

- A record naming two targets, one seen and one novel, is novel (any novel target).
- A damaged `memory/targets.json` (not JSON, wrong shape, an invalid key) fails closed: the
  reader raises `ValueError` naming the file and the fix (the owner moves it aside and runs
  `bin/wuwei init --upgrade`); `decision route` exits 2, the outward guard returns its
  existing could-not-validate draft reason, the grant gate exits 2 as the deploy guard does
  for any internal error.
- A key with trailing sentence punctuation in record text (`repo:org/name.`) is read without
  it.
- Two hooks recording a first-seen target at once: writes go through one lock and an atomic
  replace; the first `first_seen` wins and a cleared row is never un-cleared.
- A record already decided or routed is not re-routed by novelty (`mandate()`'s existing
  "already holds" answer stands).

## Requirements

### Functional Requirements

- **FR-001**: One module `cli/wuwei/novelty.py` MUST own the target keys
  (`repo:<org>/<name>`, `channel:<id>`, `person:<ns>:<id>`, `tool:<server>/<name>`,
  `dependency:<ecosystem>/<name>`, `env:<name>`, `workflow:<name>`), reading keys from text,
  the configured set, the seen set in `memory/targets.json`, `novel(root, config, keys)`,
  `clear(root, key, evidence)` and `seed(root, write)`.
- **FR-002**: A target is seen when the config names it (repos, chat channels, people,
  environments, deploy workflows, exact standing grant targets) or `memory/targets.json` has
  it cleared. `novel()` returns the unseen keys and records `first_seen` for each new one.
- **FR-003**: Under autonomous, `decision route` MUST send a record whose targets include a
  novel one to the owner (route entry and event carry `novel`), print `owner` and the
  first-time line, and never take it under the mandate or the seat route.
- **FR-004**: Every owner route (`route_owner`) MUST record the novel targets of its record,
  under either mode; `decision show --widget` MUST add the first-time sentence to the
  question when the route has them.
- **FR-005**: An owner answer recorded through `owner_outcome` (host, planner card, DM
  listener) MUST clear the route's novel targets with the decision id as evidence, except a
  `keep` answer on a grant card, which leaves them novel.
- **FR-006**: Under autonomous, the outward tier check MUST hold a send to a novel chat
  channel as a draft with the first-time reason; `drafts approve` MUST clear the draft's
  channel with the draft id as evidence. A drop clears nothing.
- **FR-007**: Under autonomous, the grant gate MUST NOT apply a standing grant line to a
  novel target, and the refusal names the first-time target. Answering the card clears it
  unless the answer is Keep owner-only.
  Nothing in this feature writes a `[grants]` line or a grant row.
- **FR-008**: `init --upgrade` MUST seed the seen set from CLI-written records of the last 30
  days (`repo` of every event kind except `note`, `target` of `grant.used`, day-state chat
  drafts sent or approved) and print
  the count; `--dry-run` writes nothing. The same seed runs when the file is missing.
- **FR-009**: `memory/targets.json` MUST be producer-only: protect_state refuses seat writes.
- **FR-010**: The day report MUST show `## First time today`; `wuwei why <target key>` and
  `wuwei why D-n` MUST explain a target's novelty.
- **FR-011**: `decision template` MUST tell the seat, in the Context placeholder, to name a
  target outside the item's repository with its key.
- **FR-012**: No new refusal under observe or guarded: each new stop is a card (decision
  card, draft card, grant card); the only new refusal is the records floor on the seen set.
- **FR-013**: Design 5.8.1 gets a short dated "Novelty" amendment; concepts, daily and
  reference docs describe it.

## Success Criteria

- **SC-001**: The four acceptance bullets of the issue pass as tests on neutral fixtures.
- **SC-002**: The full suite passes. An existing outward or grant test that now holds only
  because its fixture channel or repository is unconfigured gets that channel or repository
  added to its fixture config (or `[autonomy] mode = "supervised"` when its subject is the
  supervised path); no other expectation changes. A report test that pins the full report
  text gains the `## First time today` / `none` lines.

## Assumptions

- Cruise mode (#283) is not on this base: `decision.level()` still reads only the config
  default and no route uses it. So "one level lower" is built in its autonomous form: a
  novel target goes to the owner on a card. When #283 lands, the level form (run the class
  one level lower, never below L0, never above the ceiling) replaces the card at the same
  spot in `decide()`.
- For the same reason no mandate action on a novel target exists on this base (a novel
  target always gets a card), so the "unreversed mandate action within the undo window"
  clearing has no producer yet; `clear()` records `by: owner` or `by: seed` only, and #283
  adds `by: mandate` with its undo window.
- Decision record targets are the keys written in its `Question:`, `Context:` and `Blast
  radius:` lines. A seat that omits a key avoids the card for a decision record; that is a
  known limit. The guarded actions (grant gate, outward sends) take their target from the
  command or the payload, which the seat cannot leave out. The decision template asks for
  the keys (FR-011). Grant cards already write `Target: repo:<org>/<name>` in Context, so
  answering one clears its repository with no extra code.
- Items carry no repository until a build starts, and a build always uses a configured
  repository, so deriving a repo target from the item adds nothing.
- Config is the owner's declaration of what is familiar, so configured targets are always
  seen and are not copied into `memory/targets.json`; a repository added to config later is
  seen at once.
- "Supervised: nothing changes" applies to routing, holds and standing grants. The seen set
  still learns from owner answers under supervised, so switching to autonomous does not
  re-ask what the owner already answered.
- Any owner answer on a decision card clears its targets (the owner has seen the target),
  except Keep owner-only on a grant card: clearing then would let the standing pattern pass
  the next run against the owner's answer. For a draft only approval clears, since a drop
  may mean "not this channel".
- Outward novelty keys only chat channel ids (`channel`, `channel_id`, also inside `draft`)
  for the chat kinds (`chat`, `slack`); people, tracker, docs and mail destinations already
  follow the tier rules for unknown parties. `person`, `tool`, `dependency`, `env` and
  `workflow` keys come from decision record text and config.
- The launch gate is unchanged: a seat launch is not an action on a target, and the MCP
  launch gate (#325) already asks the owner about an unknown server. The issue's "launch"
  gate is read as covered by it.
- The seed reads CLI-written records only: events of every kind but `note` (the one kind the
  event command lets a seat append) whose `repo` value is `<org>/<name>`, the `target` of
  `grant.used` events (a hook-written `target` elsewhere can be command text a seat shapes), and chat drafts with status `sent` or `approved` in day state. A day whose
  files cannot be read is skipped with a warning on stderr (more cards, never fewer).
- No new event kind: the clearing record is the row in `memory/targets.json`, written only by
  the CLI.
- `tests/test_invariants.py` and design 9.2 are not on this base. The three invariants (a
  novel target never runs above L1; clearing needs an owner answer, an unreversed mandate
  action, config or the seed; a seat cannot write the seen set) are tested in
  `tests/test_novelty.py`; if `tests/test_invariants.py` exists when this is built, they go
  there and in the design 9.2 table instead.

## Deferred

- The level form of "one level lower" and clearing by an unreversed mandate action: #283.
- Design 9.2 invariant rows and `tests/test_invariants.py` entries, if #530 part B (PR 555)
  is not on the base this is built on.
