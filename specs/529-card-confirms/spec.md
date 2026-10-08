# Feature Specification: An answer on an Ask card is the confirmation of a config write

**Feature Branch**: `529-card-confirms`
**Created**: 2026-10-05
**Status**: Draft
**Input**: GitHub issue #529: "fix(records): an answer given on an Ask card is the
confirmation: config set, calibrate answers and every record command run by the planner
after a card never prompt y in a host terminal again". Owner, 2026-10-05: "I don't want to
run commands for setting a config I already answered in the Ask widget."

## Root cause

- `cli/wuwei/commands/setup.py:132-150` (`set_value`) always goes through `_edit` and
  `cli/wuwei/commands/config.py:233-254` (`offer`), which asks `Confirm? [y/N]` on `/dev/tty`
  through `cli/wuwei/integrity.py:316-333` (`_host_confirm`). There is no path that accepts
  the owner's card answer. In a session the read is empty, so `offer` prints `declined;
  nothing written; rerun it in a host terminal and answer y` (`config.py:243`), or
  `_host_confirm` raises `HOST_TERMINAL` and the command exits 2.
- `cli/wuwei/guards/decision.py:149-197` (`record_gate`) records only the `Goals` and
  `Voice` gate topics, the `D-n` ids a card asked, and draft answers. The owner's answer to
  any other card is never recorded, so nothing downstream can trust it as the confirmation.
- `cli/wuwei/guards/protect_state.py:81` makes `config set` an owner action and
  `protect_state.py:171` (`_GATE_EDITS`) has no entry for it, so the planner that asked the
  card is refused the record command too.
- `cli/wuwei/commands/calibrate.py:110-127` (`calibrate --answer`) only writes
  `interview.json` and prints `run bin/wuwei config promote in a host terminal`;
  `cli/wuwei/interview.py:105-315` (`QUESTIONS`) has no row for `cap`, `host.seats`,
  `outbound.default_tier` or `outbound.learn`, and `interview.widgets`
  (`interview.py:572-580`) prints only rows never answered, so a key answered once cannot
  be asked again on a card.

## User Scenarios and Testing

### User Story 1: An interview card answer writes the config (Priority: P1)

The planner asks CAP on a card from `calibrate --questions cap`; the owner answers `5`; the
planner runs the card's record command `wuwei calibrate --answer "cap=5"`. The config holds
`cap = 5`, nothing prompts, and the event names the card.

**Independent Test**: neutral workspace in `tmp_path`, posture `guarded`, today's
`plan.md`, a registered planner session; feed `record_gate` a PostToolUse payload for the
`At once` (CAP) widget answered `5`; run `calibrate --answer cap=5` in process with
`WUWEI_SESSION_ID` set to the planner session.

**Acceptance Scenarios**:

1. **Given** guarded, the planner asked the `At once` (CAP) card and the owner answered `5`, **When**
   the planner runs `wuwei calibrate --answer "cap=5"`, **Then** `config.toml` has
   `cap = 5`, no confirm callable or terminal is touched, the exit is 0, and one
   `config.set` event has payload `{"keys": ["cap"], "card": "cap"}`.
2. **Given** the same for `host.seats` (`Agents`), `outbound.default_tier` (`Outbound`) and
   `outbound.learn` (`Connectors`), **Then** each key is written the same way.
3. **Given** the owner answered `3` on the card, **When** the planner runs
   `calibrate --answer "cap=5"`, **Then** `interview.json` records the answer as today, the
   config is not written and the output names `bin/wuwei config promote` as today.
4. **Given** `cap` was answered on an earlier day, **When** `wuwei calibrate --questions
   cap seats` runs, **Then** it prints the `At once` and `Agents` widgets anyway;
   `calibrate --questions` with no ids keeps printing only unanswered rows.

### User Story 2: A decision card answer writes the config (Priority: P1)

The planner writes a decision record `D-n` (`Class: other`, `Decided-by: owner`) whose
option titles read `<key> = <value>`, routes it and asks its widget; the owner picks `cap = 5`; the planner
runs the widget's record command `wuwei config set cap 5 --from-card D-n`.

**Acceptance Scenarios**:

1. **Given** guarded and the owner answered `cap = 5` on `D-1`, **When** the planner runs
   `bin/wuwei config set cap 5 --from-card D-1`, **Then** the protect-state hook lets it
   through, `config.toml` has `cap = 5` with no prompt, `D-1` is recorded as decided by the
   owner with the matching option (`decision.decided` event), and one `config.set` event
   has payload `{"keys": ["cap"], "card": "D-1"}`.
2. **Given** the owner answered `cap = 3` on `D-1`, **When** the planner runs
   `config set cap 5 --from-card D-1`, **Then** exit 1, nothing written, and the message
   names the recorded card and `bin/wuwei decision show D-1 --widget`.
3. **Given** `D-1` has no option titled `cap = 5`, **Then** exit 1, nothing written.
4. **Given** `D-1` with options titled `<key> = <value>`, **When** `decision show D-1
   --widget` runs, **Then** its `record` is `wuwei config set <key> <value> --from-card
   D-1`; any other record keeps `wuwei decide D-1 "<label>"`.
5. **Given** a seat (payload with `agent_id`) runs `config set cap 5 --from-card D-1`,
   **Then** the hook refuses it as today.

### User Story 3: Strict keeps the host terminal (Priority: P1)

**Acceptance Scenarios**:

1. **Given** strict and the owner answered on the card, **When** the planner runs
   `config set cap 5 --from-card D-1`, **Then** the hook refuses with a reason that ends
   `Run it in a host terminal: ` and the command as typed (printed for a host terminal).
2. **Given** strict, **When** `config set cap 5 --from-card D-1` runs in a session (no
   hook, for example a `!` shell), **Then** exit 1, nothing written, and the message names
   `bin/wuwei config set cap 5` for a host terminal.
3. **Given** strict, **When** the owner runs `config set cap 5 --from-card D-1` in a host
   terminal (no session id), **Then** the card is ignored and the `Confirm? [y/N]` prompt
   runs as today.
4. **Given** strict, **When** the planner runs `calibrate --answer "cap=5"` after the card,
   **Then** only `interview.json` is written and the output names `bin/wuwei config
   promote` as today.

### User Story 4: No empty answer in a session (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a session (`WUWEI_SESSION_ID` set) and no `--from-card`, **When** `config set
   cap 5` runs, **Then** it exits 1 without opening a terminal, nothing is written, and the
   message names the card command: for a key an interview row covers, `bin/wuwei calibrate
   --questions cap` and its record command; for any other key, a decision whose option
   titles read `<key> = <value>` and `bin/wuwei config set <key> <value> --from-card D-n`.
   The text never says `empty answer` or `run it again`.
2. **Given** strict and a session, **Then** the same exit 1 names `bin/wuwei config set
   cap 5` for a host terminal instead.
3. **Given** a host terminal (no session id), **When** `config set` runs without
   `--from-card`, **Then** the `Confirm? [y/N]` prompt runs as today.

### Edge Cases

- The answer is normalised once (whitespace stripped, a trailing ` (Recommended)`
  removed) on both sides, the hook and the record command.
- An `Other` text on a decision card that is not an option title is not a config answer;
  `--from-card` exits 1 and the planner asks again.
- `config set --from-card D-n` reruns after a failed write: the config write is idempotent
  (`No config.toml changes`) and a decision already answered by the owner with the same
  option is not recorded twice.
- A decision record not yet routed: the config is written, then the outcome step reports
  `route this pending owner decision first` and exits 1; a rerun after `decision route`
  completes it.
- Guard keys (`outbound.*`, `outward.*`, `grants.*`, `security.*`) follow the same rule:
  the card answer is the owner's; strict keeps the terminal.

## Requirements

### Functional Requirements

- **FR-001**: `record_gate` records, for the registered planner session only and outside
  strict (as today), one topic per answered card that is a Morning gate question or a
  `D-n` question: `<header>=<sha256 of the normalised answer>`, built by one helper
  `sessions.card_topic(card, answer)`.
- **FR-002**: `sessions.card_answered(root, card, answer)` is true only when that topic is
  among the calling planner session's gate topics; under strict it is always false
  (`gate_topics` already returns nothing).
- **FR-003**: `interview.QUESTIONS` gains four workspace rows: `cap` (header `At once`, key
  `cap`), `seats` (header `Agents`, key `host.seats`), `tier` (header `Outbound`, key
  `outbound.default_tier`) and `learn` (header `Connectors`, key `outbound.learn`), the
  shipped default as the first choice; `cap` and `seats` also take a whole number of 1 or
  more as free text. Every header in the table is unique (the repository row `gates`
  becomes `Review depth`).
- **FR-004**: `calibrate --questions [ID ...]`: with ids, prints those rows' widgets even
  when answered before; without ids, unchanged.
- **FR-005**: `calibrate --answer ID=VALUE`, after recording `interview.json` as today,
  writes the config keys of each workspace-row answer whose card is answered
  (`card_answered(root, row header, VALUE)`), with no prompt, and appends one
  `config.set` event per answer `{"keys": [...], "card": "<question id>"}`. Answers
  without a card answer keep today's promote path and its `Next:` line.
- **FR-006**: `config set KEY VALUE --from-card D-n`, outside strict: the record `D-n` of
  today has an option whose title is the assignment `KEY = VALUE` (same key, equal parsed
  TOML value) and the card's recorded answer is that title; then the config is written
  with no prompt, `D-n` is recorded as the owner's answer through the existing
  `owner_outcome` (unless the owner already answered it with that option), and one
  `config.set` event `{"keys": [KEY], "card": "D-n"}` is appended. Any mismatch exits 1
  and writes nothing.
- **FR-007**: Under strict, `--from-card` is not a confirmation: in a session it exits 1
  naming `bin/wuwei config set KEY VALUE` for a host terminal; in a host terminal the
  normal prompt runs.
- **FR-008**: `config set` in a session (`sessions.current()` set) with no `--from-card`
  exits 1 without opening a terminal and names the card command (FR-004/FR-005 for an
  interview key, FR-006 otherwise; strict names the host terminal command).
- **FR-009**: The protect-state hook lets `config set ... --from-card D-n` through for the
  registered planner session when `D-n` is among its gate topics; under strict, for a
  seat, or without an asked card it refuses as today, and under strict the reason ends
  with `Run it in a host terminal: <command>`. The `config set` reason names the card path.
- **FR-010**: `decision show D-n --widget` prints the record `wuwei config set <key>
  <value> --from-card D-n` when any option title of `D-n` is a config assignment.
- **FR-011**: `config.set` is a CLI-only event kind: listed in the event command's
  producer table and in `signal.py`'s `SILENT` kinds.
- **FR-012**: No new refusal under observe or guarded; every change relaxes an existing
  owner-action refusal or replaces an empty-answer decline with an exit 1 that names the
  next step.
- **FR-013**: Docs: design spec 5.2 `Records` gains one dated sentence (#529);
  `skills/wuwei-plan/SKILL.md`, `docs/site/concepts.md`, `docs/site/security.md` and
  `docs/site/configuration.md` say a card answer writes the config outside strict.

### Key Entities

- **Card topic**: `<header>=<sha256 hex>` in `state.sessions[<planner>].gate_asked`,
  written only by `record_gate` (PostToolUse on AskUserQuestion, `gate.asked` event).
- **Config assignment title**: a decision option title `<dotted key> = <TOML value>`.
- **`config.set` event**: `{"keys": [dotted keys], "card": "<D-n or question id>"}`.

## Success Criteria

- **SC-001**: All acceptance scenarios pass as in-process tests; the full suite passes.
- **SC-002**: Under guarded the owner's cap, host.seats, outbound.default_tier and
  outbound.learn answers reach `config.toml` with zero host-terminal commands.
- **SC-003**: No test asserts `empty answer` or `run it again` for `config set` in a
  session.

## Assumptions

- "Card" means an AskUserQuestion widget a WUWEI command printed: an interview row from
  `calibrate --questions`, or a decision record's widget. The issue's
  `--from-card <decision id>` takes a `D-n`; interview cards are recorded by their own
  record command, `calibrate --answer`, which the issue also names. One recording rule
  (FR-001) serves both.
- The card answer is recorded as a hash, as #493 does for typed draft text, so the state
  never holds free text and the hook needs no interview import (hook latency).
- The trust anchor is the PostToolUse payload, which only the harness writes after the
  owner answers; the topic lives in reserved state written by `record_gate`. A seat
  sharing the planner's session id can run `calibrate --answer`, but it can only write
  exactly what the owner answered.
- Guard keys are not excluded: the card answer is the owner's answer, and a posture
  change from a card cannot leave strict because strict records no card answers.
- A config card record carries `Decided-by: owner`, as the outbound learn record does, so
  #530's mandate never takes it: `decision route` sends it to the owner under autonomous
  and supervised alike. A record taken under mandate has no card answer, so
  `--from-card` on it exits 1 and writes nothing.
- `setup` (#412) asks the four new rows like every other row, at the host terminal; the
  first choice of each is the shipped default.
- The day's CAP stays the lead JSON's `cap` approved at the gate; the config `cap` is the
  default the lead proposes. The planner skill says: after the CAP card, update the lead
  JSON too.
- `WUWEI_SESSION_ID` is set in the planner's Bash calls and in `!` shells of that session
  and unset in the owner's own terminal (`sessions.current()`, existing).
- Deferred: `telemetry proposals --widget` cards keep their host-terminal record
  (`config set` with no card id): a `Yes` there is not bound to one key and value, and
  binding it belongs to the telemetry item. `config add-repo` and `config promote` keep
  their prompt.
- `tests/test_invariants.py` is not on this base; if it is present when the builder
  starts, FR-006, FR-007 and FR-009 get their rows in design section 9 and that test.
