# Feature Specification: a thread reply in a work channel sends when the thread's participants are known people

**Feature Branch**: `526-thread-reply`

**Created**: 2026-10-05

**Status**: Draft

**Input**: GitHub issue #526, "fix(outward): a thread reply in a work channel sends when the
thread's participants are known people: the planner learns participants through the
connector on the same card flow, a thread row is configurable in the tier table, and the
reason's posture line stops saying no setting lowers it". Owner's day, 2026-10-05, on
0.17.0: every Slack thread reply through the connector was held with
`approval tier thread for <channel>: chat threads draft until their participants are known`
and the second line `posture: outward = block (owner-only action; no setting lowers it)`.

## Root cause (read and reproduced on main, c75ac88, read-only)

Reproduction: a scratch workspace (`work_channels = ["C1"]`) ran `outward.classify('Thanks',
..., {'channel': 'C1', 'thread_ts': '1.2'}, kind='slack', tool='mcp__slack__slack_send_message')`
in process. With `outbound.default_tier = "ask"` it returns `(1, 'draft')` with the rule
`approval tier thread for C1: chat threads draft until their participants are known`; with
the shipped `default_tier = "send"` (0.18.0, #531) it returns `(0, 'send')` with no row named
in the trace (`party C1: team`, every row `passed`).

1. **Participants are never learned.** `cli/wuwei/outward.py:634-638` (`classify`): a chat
   call with `thread` or `thread_ts` is held by the kind rule `tier('thread', ...)` whenever no
   table row decided. Nothing records who is in the thread: `_parties`
   (`cli/wuwei/outward.py:455-514`) sees only the channel and the mentions in the text, and
   `outbound learn` (`cli/wuwei/commands/outbound.py:397-467`) takes only `--channels`,
   `--people` and `--owner`. The hook cannot read the thread; the planner can (the
   connector's replies tool), but no step asks it to. Under the `send` umbrella the reply goes
   out without any participant evidence and the trace names no row; under `ask` every thread
   reply is a card, even among known team people.
2. **The tier table has no thread key.** `workspace.TOPICS` (`cli/wuwei/workspace.py:49`) is
   `sensitive`, `commitment`, `disagreement`; a row `{ channel = "C1", topic = "thread" }` is
   refused by the schema, and `drafts.always_row` (`cli/wuwei/drafts.py:157-170`) offers no
   Always option for a thread hold.
3. **The posture line is the floor sentence.** `cli/wuwei/guards/__init__.py:46` puts
   `outward.check_tier` in `OWNER_ONLY`, so `level()` (`:64-65`) returns
   `posture: outward = block (owner-only action; no setting lowers it)`, and
   `commands/hook.py:posture` (`:264`) prints it under every held draft. A held draft is one
   card away from being sent, and a tier row lowers it; the floor sentence belongs to the
   publish floor (deploy, merge) and to the security refusals `check_tier` also returns.

## User Scenarios and Testing

### User Story 1 - A team thread reply sends (Priority: P1)

The planner replies in a Slack thread in a work channel. The planner has recorded the
thread's participants with `bin/wuwei outbound learn --tool <tool> --thread <file>`, and every
participant is the owner or a recorded team person. The reply goes out, and
`bin/wuwei outbound explain` (the trace) names the thread row that sent it.

**Why this priority**: the owner's report; every thread reply is held today under `ask`, and
under `send` it goes out with no participant evidence.

**Independent Test**: `python -m pytest -q tests/test_outward.py -k thread`.

**Acceptance Scenarios**:

1. **Given** `default_tier = "ask"`, `work_channels = ["C1"]`, `outbound.people` with
   `slack:U01` and `slack:U02` as `team`, and participants `U01`, `U02` recorded for `C1/1.2`,
   **When** a seat replies `Thanks` to `C1` with `thread_ts = "1.2"`, **Then** `classify`
   returns `(0, 'send')` and the trace has `matched` on the row
   `{ audience = "team", topic = "thread", tier = "send" }` for `C1`, `U01` and `U02`.
2. **Given** the same with `default_tier = "send"`, **Then** the same, with the same row named.
3. **Given** the participants include the owner's `outbound.owner.slack.user`, **Then** the
   owner party matches the owner row and the reply still sends.

### User Story 2 - Unknown participants are learned on the card (Priority: P1)

**Independent Test**: `python -m pytest -q tests/test_outbound_learn.py -k thread`.

**Acceptance Scenarios**:

1. **Given** `default_tier = "ask"` and no participants recorded for `C1/1.2`, **When** the
   seat replies in that thread, **Then** it is a draft whose reason holds
   `participants of thread 1.2 not learned, run bin/wuwei outbound learn --tool <tool> --thread <file>`.
2. **Given** that reason, **When** the planner writes the thread file
   `{"channel": "C1", "thread_ts": "1.2", "participants": [{"id", "name", "email"}, ...]}` from
   the connector's replies tool and runs `bin/wuwei outbound learn --tool <tool> --thread <file>`,
   **Then** the participants are recorded for `C1/1.2` for the day, and a participant not in
   `outbound.people` is proposed on the learn card with a class: `team` when the email domain
   is in `outbound.company_domains`, `client` when an email is outside configured
   `company_domains`, else `company`.
3. **Given** `Approve` on that card, **When** the seat repeats the same reply, **Then** it sends
   (Story 1).
4. **Given** every participant already known, **Then** learn records the participants, writes
   no card, prints that the reply can be sent again and exits 0.
5. **Given** the thread file is unreadable, **Then** exit 2 naming the file; malformed (wrong
   keys, an id or name the listing rules refuse, a `thread_ts` that is not digits dot digits),
   **Then** exit 1 naming the expected shape. A non-slack connector is refused like the other
   listings. `outbound.learn = "off"` refuses as today.

### User Story 3 - A client participant follows the client rows (Priority: P1)

**Independent Test**: `python -m pytest -q tests/test_outward.py -k thread_client`.

**Acceptance Scenarios**:

1. **Given** participants `U01` (team) and `U03` recorded for `C1/1.2` with `slack:U03` as
   `client`, **When** the seat replies, **Then** it is a draft held by the client row for `U03`
   (`ask by rule 5 (audience=client) for U03: U03 in outbound.people as client`), under both
   umbrellas.
2. **Given** a thread reply in an external channel `C2` (`external_channels`), **Then** the
   client row asks for `C2`, as today.

### User Story 4 - Always send in this channel's threads (Priority: P2)

**Acceptance Scenarios**:

1. **Given** the draft of Story 2 scenario 1, **Then** its card offers
   `Always send in this channel's threads`, and `bin/wuwei drafts approve <id> --always` adds
   `{ channel = "C1", topic = "thread", tier = "send" }` to `outbound.tiers`.
2. **Given** that row and no participants recorded, **When** a seat replies in any thread of
   `C1`, **Then** it sends by that owner row.
3. **Given** `{ topic = "thread" }` in an owner row, **Then** the config loads (the schema knows
   the topic).

### User Story 5 - The held reason's second line (Priority: P1)

**Independent Test**: `python -m pytest -q tests/test_outward.py -k hook_refusal_names_draft`.

**Acceptance Scenarios**:

1. **Given** a held draft refused by the outward hook, **Then** its second line is
   `posture: outward = block; a draft is one card away` and the text `no setting lowers it`
   does not appear.
2. **Given** a deploy or merge refusal (publish), **Then** its line is unchanged
   (`posture: publish = block (owner-only action; no setting lowers it)`).
3. **Given** an outward security refusal (a secret or the canary in the text), **Then** its
   line is unchanged: it is not a draft.

### Edge Cases

- A thread reply with zero or several channel destinations gets no thread topic and no
  participants party; the existing kind rules decide it as today.
- `thread` on a code-host comment (review thread id) is not a chat thread: the thread topic
  and the participants apply to kind `chat` and `slack` only.
- A recorded thread is keyed by channel and thread ts (`C1/1.2`); a reply in another thread of
  the same channel is not learned.
- The record is per day (state lives in the day directory); tomorrow the thread is learned
  again.
- `outbound.learn = "off"`: the not-learned reason names no learn command.
- A pending learn card for another connector: learn still records the participants, then
  prints the open card as today.

## Requirements

### Functional Requirements

- **FR-001**: `workspace.TOPICS` gains `thread`; a tier row may carry `topic = "thread"`.
- **FR-002**: `classify` adds the topic `thread` for a `chat` or `slack` call with a non-null
  `thread` or `thread_ts` and exactly one channel destination.
- **FR-003**: for such a call, `_parties` adds one person party per participant recorded for
  `<channel>/<ts>` today, classed by `_person` like a mention (owner, `outbound.people` class,
  internal team, else the connector default), with the unknown evidence
  `unknown thread participant <id>, not an internal person in outbound.people`; when nothing is
  recorded it adds one party `<channel>/<ts>` of kind channel (so channel rows for `<channel>`
  match it) with the connector default class and the evidence
  `participants of thread <ts> not learned, run bin/wuwei outbound learn --tool <tool> --thread <file>`
  (the learn clause dropped under `outbound.learn = "off"`).
- **FR-004**: `DEFAULT_TIERS` gains `{ audience = "team", topic = "thread", tier = "send" }`
  directly after the company row (rule 10; the monitoring row becomes 11). It is not a broad
  row: it stays under the `send` umbrella.
- **FR-005**: `bin/wuwei outbound learn --tool <tool> --thread <file>` (slack only) validates the
  file, records the participant ids under state key `outbound_threads` (`{"C1/1.2": ["U01",
  ...]}`) with one `outbound.thread` event (thread key and count only), and proposes every
  participant not in `outbound.people` on the existing learn card (or writes it directly
  under `learn = "auto"` outside strict) with the class of Story 2 scenario 2. The state key
  and the event kind are reserved for `wuwei outbound learn`.
- **FR-006**: `drafts.always_row` offers `Always send in this channel's threads` with the row
  `{ channel = <destination>, topic = "thread", tier = "send" }` when the held party is
  `<destination>/<ts>`.
- **FR-007**: the hook's posture line for an outward refusal whose reason starts with
  `outward: draft ` is `posture: outward = <decided level>; a draft is one card away`; every
  other posture line is unchanged.
- **FR-008**: docs: `docs/site/concepts.md` (thread row, learn step), `docs/site/security.md`
  (learn `--thread`), `docs/site/reference.md` (posture line), `docs/site/configuration.md`
  (topic list), `templates/workspace/config.toml` (topic list, thread comment) and
  `skills/wuwei-plan/SKILL.md` (the planner's thread step).

### Key Entities

- **Thread participants record**: state key `outbound_threads`, `{ "<channel>/<thread ts>":
  [participant ids] }`, day scoped, written only by `wuwei outbound learn`.
- **Thread file**: `{ "channel": "C1", "thread_ts": "1.2", "participants": [{ "id", "name",
  "email" }] }`, written by the planner under today's day directory from the connector's
  replies tool; participants use the people listing shape and rules.

## Success Criteria

- **SC-001**: the four Acceptance items of #526 pass as tests (Stories 1, 2, 3, 5).
- **SC-002**: no new refusal under observe or guarded: under the shipped `send` umbrella the
  only new hold is a recorded client or public participant, which is a card.
- **SC-003**: the full suite passes.

## Assumptions

- A1: Acceptance "Given an unknown participant, then the draft reason names outbound learn
  --thread" holds under `outbound.default_tier = "ask"`. Under the shipped `send` umbrella
  (#531: only client, public and sensitive ask) a thread with unrecorded or unknown non-client
  participants sends as it does on main today, like an unknown mention; holding it would add a
  new card the owner removed in #531 and the #530 push.
- A2: Under `ask`, a known `company` participant asks through the existing company row, as a
  company mention does. The issue's "team or company ... sends" holds under the shipped `send`
  umbrella, where the company row drops out.
- A3: The `<level>` in the posture line is the decided level of the refusal, which is `block`
  for every held draft (`outward.check_tier` stays owner-only so a card is never shadowed into
  a pass); printing the configured area level would show `warn` for a call that is held.
- A4: The floor sentence stays on non-draft `outward.check_tier` refusals (the secret and
  canary checks of `security.outbound`, which are a floor) and on a table `block` row. A block
  row's "no setting lowers it" is also inaccurate; it is deferred (see Deferred), since the
  issue names only the held draft.
- A5: The issue's "Always send in this thread or channel" is a channel row with
  `topic = "thread"`; the tier table has no thread-id key, and the issue names exactly that
  row.
- A6: The thread file reuses the people listing shape (`id`, `name`, `email`, email may be
  empty) so one validator serves both; the issue says "ids, names", and the email is what
  classes a participant as team.
- A7: A participant record is planner-supplied evidence, the same trust as the `--channels` and
  `--people` listings of #492: the planner is the only session allowed to run learn, the state
  key is reserved to it, and an unknown person still goes through the card.
- A8: The old kind rule (`chat threads draft until their participants are known`) stays for a
  thread reply without exactly one channel destination, its only remaining path.
- A9: `tests/test_invariants.py` does not exist on this base, so no invariant row is added.

## Deferred

- A table `block` row's posture line still says `no setting lowers it` (a follow-up issue to
  file: the outward block line names `bin/wuwei outbound tiers`).
