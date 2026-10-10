# Feature Specification: The agent that asked a card records its answer

**Feature Branch**: `661-asker-records`
**Created**: 2026-10-10
**Status**: Draft
**Input**: GitHub issue #661: fix(records): the agent that asked a card records its answer:
a card answer is the owner's decision, so `decision outcome`, `config set --from-card` and
every record command run from the planner after the answer in every posture below strict.

Owner, 2026-10-10 (item 32): the owner answered a decision card, but recording the outcome
was owner-only, so the owner still had to paste a command in a terminal. Either the answer
is the approval or it is not. Asking twice is friction.

Standing rules (unchanged): a card answer is the confirmation (#357, #529); below strict a
guard is a warning or a card, never a new wall (#530); seats never record (I8); strict keeps
every owner-only action in a host terminal.

## Root cause

Reproduced read-only on main (`66b3720`) in a scratch workspace built with the
`tests/test_decision.py` fixtures (no dry-run workspace was named for this issue): a
supervised day, posture `observe` and then `guarded`, planner `planner-1`, an owner-routed
one-way D-1. The record gate stored `D-1` and `D-1=<sha256 of the answer>` in
`state.sessions.planner-1.gate_asked`. Then, through `protect_state.check_bash` with the
planner's payload:

| Command (from the planner) | observe and guarded |
| --- | --- |
| `bin/wuwei decide D-1 B` | `(0, '')` |
| `bin/wuwei decision outcome D-1 B` | `(1, 'The owner records a decision outcome, outside agent tools; ... The owner runs bin/wuwei decision outcome <id> <option> in a host terminal.')` |
| `bin/wuwei decide D-2 B` (not asked) | `(1, '... Run it in a host terminal: bin/wuwei decide D-2 B')` |

The records area blocks in every posture (`workspace.POSTURES`), so each exit 1 is a wall.

- `decision outcome` and `decide` record through the same writer,
  `commands/decision.owner_outcome` (`cli/wuwei/commands/decision.py:178`, reached from
  `run` at `:357` and from `commands/decide.py`). The CLI treats them the same; the hook
  does not.
- `protect_state._GATE_EDITS` (`cli/wuwei/guards/protect_state.py:188`) lists `('decide',
  '')` but not `('decision', 'outcome')`, so the planner branch at `:268` never runs for
  `decision outcome`, and the table reason at `:47` (a host-terminal line) is returned. The
  asked-id check at `:278` names only the groups `mcp`, `decide` and `drafts`.
- When the planner branch refuses below strict (an id that was not asked, an extra id word,
  a draft answered Keep, goals with no gate answer), `:286` appends `Run it in a host
  terminal: <the command>`: a command for the owner to paste, below strict.
- `commands/build.py:36` and `:497` print, for a parked item, `the owner answers it with
  bin/wuwei decision outcome <decision> <option> in a host terminal`: the line that sends
  the planner to `decision outcome` and the owner to a terminal. `<decision>` is the record
  path (`.wuwei/days/<date>/decisions/D-n.md`, `build.py:455`), where the command takes an
  id.
- Nothing lists a card the owner answered whose record command never ran.

The other record commands the widgets name already pass the hook from the planner below
strict: `config set --from-card D-n` (`:280-284`), `drafts approve` (`:274-278`), and `plan
approve` and `calibrate --answer`, which are not owner-only. Their CLI confirmation reads the
planner session (`sessions.card_answered`, `drafts.py:315`), which #599 makes independent of
`WUWEI_SESSION_ID`.

## User Scenarios and Testing

### User Story 1: The planner records the outcome of a card it asked (Priority: P1)

The owner answers a decision card in the planner session; the planner runs `decision
outcome` (or `decide`), the hook lets it through below strict, and the CLI records it from
the card answer with no prompt and no host-terminal line.

**Independent Test**: `tests/test_owner_edits.py` (hook, in process) and
`tests/test_card_confirms.py` (hook then CLI, `integrity._host_confirm` failing when called).

**Acceptance Scenarios**:

1. **Given** a card for D-1 asked and recorded by the planner and then answered, under
   `observe` and under `guarded`, **When** the planner runs `bin/wuwei decision outcome D-1
   B --from-card <hash>` (the hash `decision.card_hash` gives for the record), **Then** the
   hook returns `(0, '')`, and the CLI records `Decided-by: owner` with Notes `in the
   planner session` and never prompts.
2. **Given** the same card, **When** a seat (a payload with `agent_id`) or another session
   runs it, **Then** the hook refuses it (exit 1) and nothing is recorded.
3. **Given** the same card, **When** the planner runs `decision outcome D-1 B --card
   <hash>`, `decision outcome D-1 B` or `decide D-1 B --from-card <hash>`, **Then** each
   passes the hook the same way.

### User Story 2: Strict keeps the owner's terminal (Priority: P1)

**Acceptance Scenarios**:

1. **Given** strict and the same asked and answered card, **When** the planner runs
   `bin/wuwei decision outcome D-1 B --from-card <hash>`, **Then** the hook refuses it and
   its reason ends `Run it in a host terminal: bin/wuwei decision outcome D-1 B` (the hash
   flag dropped, so the pasted command prompts y/N as today).
2. **Given** strict, **When** the owner runs `bin/wuwei decision outcome D-1 B` in a host
   terminal, **Then** it asks y/N and records as today.

### User Story 3: An unknown hash is refused with the reason (Priority: P1)

**Acceptance Scenarios**:

1. **Given** D-1 asked and answered below strict, **When** the planner runs `bin/wuwei
   decision outcome D-1 B --from-card 000000000000` (not the record's card hash), **Then**
   the hook passes it, the CLI records nothing, prompts nothing, and exits 1 with the #599
   reason naming `bin/wuwei decision show D-1 --widget`.
2. **Given** a D-n the planner never asked, below strict, **When** the planner runs
   `decision outcome D-n B`, **Then** the hook refuses it with a reason that names the card
   (`bin/wuwei decision show <id> --widget`) and contains no `Run it in a host terminal`.

### User Story 4: No command for the owner to paste below strict (Priority: P2)

**Acceptance Scenarios**:

1. **Given** observe or guarded and a planner record command the hook refuses (an unasked
   decision, a draft not answered Send, goals with no gate answer), **Then** the reason is
   the card reason and never contains `Run it in a host terminal`. A `config set` refusal
   keeps its own card-first table reason (#529) without the suffix.
2. **Given** a parked build item, **When** `build check` or `build next` reports the park,
   **Then** the line names `bin/wuwei decision show D-n --widget` (the id, not the path) and
   running the card's record command, and no host-terminal command.

### User Story 5: Doctor lists a card answered but not recorded (Priority: P2)

**Independent Test**: `tests/test_doctor.py`.

**Acceptance Scenarios**:

1. **Given** today's state with `D-2=<hash>` in a session's `gate_asked` and no owner
   outcome for D-2, **When** `wuwei doctor` runs, **Then** the Day section has one
   `answered cards` row, status warn, value naming D-2, fix naming the card's record command.
2. **Given** a draft id with a `:send`, `:edit` or `:text:` answer topic whose draft is still
   pending, **Then** the same row names it.
3. **Given** every answered card recorded (owner outcome present, draft no longer pending),
   or only a Keep or Undo answer on a cruise undo card, **Then** the row is ok.
4. **Given** an unreadable state, **Then** the row is unmeasured with the reason.

### Edge Cases

- A widget printed before #599 carries no hash: `decision outcome D-1 B` passes on the asked
  id alone, as `decide` does today.
- Extra id words: every D-n word in a `decision outcome` command must have been asked, as
  for `decide` (the existing every-id rule at `:272`).
- `decision outcome` through `xargs`, a variable or an opaque wrapper: refused by the
  existing literal and opaque checks, unchanged.
- A Keep or Undo answer on a cruise undo card stores `D-n=<hash of Keep or Undo>`; doctor
  does not count it as an unrecorded decision answer.
- An answer typed as Other on a decision card has no matching option; doctor lists it until
  the planner records an option or writes a new record.
- A Drop answer on a Draft card stores only the id, so doctor cannot see it; not listed.

## Requirements

### Functional Requirements

- **FR-001**: `protect_state._GATE_EDITS` includes `('decision', 'outcome')`, and the
  asked-id check passes the group `decision`, so the planner runs `decision outcome D-n
  <option>` for an asked D-n below strict. Seats and other sessions are unchanged
  (`_gate_edits` returns no planner for them).
- **FR-002**: `decision outcome` takes `--card HASH`, also spelled `--from-card HASH`
  (`dest='card'`), read by `owner_outcome` as #599 reads it for `decide`; `decide` accepts
  the `--from-card` spelling too. The CLI checks the hash (#599 `owner_confirm`); the hook
  checks the asked id.
- **FR-003**: Below strict, a planner record command the hook refuses returns one card
  reason with no host-terminal command; `config set` keeps its table reason without the
  suffix. Under strict the reason stays `<table reason> Run it in a host terminal:
  <command>`, with any `--card` or `--from-card` hash dropped from a `decide` or `decision`
  command.
- **FR-004**: The parked-item line in `commands/build.py` (both places) names `bin/wuwei
  decision show D-n --widget` and its record command, using the record id.
- **FR-005**: doctor's Day section has one `answered cards` row: warn listing each D-n with
  an answer topic in any session's `gate_asked` and no owner outcome (`decision.answered`),
  ignoring Keep and Undo answers, and each draft id with an answer topic whose draft is
  still pending; ok when none; unmeasured on a read error.
- **FR-006**: Design 9.2 row I8 and `tests/test_invariants.py` check `bin/wuwei decision
  outcome D-1 once` with the two commands they check today.
- **FR-007**: `docs/site/reference.md` (host terminal table, doctor Day rows) and
  `docs/site/concepts.md` say the planner records an asked decision with `decide` or
  `decision outcome` outside strict.

### Key Entities

- `state.sessions.<id>.gate_asked`: unchanged; read by the hook (asked ids) and by doctor
  (answer topics `D-n=<sha256>` and `draft-<id>:<suffix>`).
- Card hash: #599's 12 hex characters of the record's Question and Options; carried only on
  the record command.

## Success Criteria

- **SC-001**: The three acceptance lines of the issue pass as in-process tests.
- **SC-002**: I8 holds on every case with `decision outcome` added; the walk stays within
  its CPU budget.
- **SC-003**: The full suite passes.

## Assumptions

- **Depends on #599.** `--card` on `decide`, `decision.card_hash`, `owner_confirm(...,
  card, fields)`, `decision.no_card` and `sessions.caller` come from #599 (in flight, not on
  main at `66b3720`). This item extends them and does not re-implement them; it builds on
  main after #599 merges. The hook, doctor, build-message and docs parts do not need #599.
- Overlap with #599: since #599 has not landed, this item adds the `--card`/`--from-card`
  argument to `decide` and `decision outcome` (unused by the CLI), and the hook checks the
  hash against the owner's answer the gate recorded (`D-n=<sha256 of the answer>`, a prefix
  is accepted). #599's CLI-side `card_hash` check against the record still applies when it
  merges. Merge hazard: #599's `card_hash` hashes the card (Question and Options), not the
  answer, so the hash its widget names will not match a gate topic. Whichever lands second
  reconciles the two: the hook also accepts `card_hash` for the asked id, or the widget names
  the answer hash.
- The issue's `--from-card <hash>` is #599's `--card <hash>`: the same value, so both
  spellings are accepted on `decide` and `decision outcome` with one `dest`. `config set
  --from-card` keeps taking a D-n.
- "The records guard accepts it because the card hash matches" is split as #599 splits it:
  the hook checks that the planner asked the id and that a given hash is the owner's
  recorded answer on that card (state it already reads); the CLI checks the hash against
  the record. The hook does not read or hash the record file.
- Of the record commands the issue lists, only `decision outcome` is refused by the hook
  for the planner today (reproduced above); `config set --from-card`, `drafts approve`,
  `plan approve` and `calibrate --answer` already pass and need no hook change.
- "No command is ever printed for the owner to paste below strict" covers the record
  refusals of `protect_state` and the parked-build line, the two places a planner is sent to
  a host terminal for a card answer. Config-value hints elsewhere that name `config set` in
  a host terminal are other flows and stay.
- Seats keep the table reasons; a seat never asks a card, so the card-first wording is for
  the planner.
- Doctor lists decision and draft cards. Gate cards (`plan approve`, goals, voice) already
  show as an unapproved gate in `next` and status; `calibrate --questions` answers are keyed
  by question text with no record to compare. Not listed.
- I8 is extended rather than a new invariant id, so no id collides with other items in
  flight (#599 holds I29 and I30).

## Deferred

- None.
