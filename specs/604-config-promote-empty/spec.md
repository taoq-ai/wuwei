# Feature Specification: promote keeps owner-set keys, an answer promotes only its keys, and an empty list is written empty

**Feature Branch**: `604-config-promote-empty`
**Created**: 2026-10-09
**Status**: Draft
**Input**: GitHub issue #604: fix(config): promote never overwrites a key the owner set later
and calibrate --answer promotes only its keys, and config set writes an empty list as empty.

Real-day finding (owner, 2026-10-09, first day on 0.23.0, autonomous mode). Two ways the
config write path lost or could not express what the owner chose. Program rules: #530
(autonomous by default; no new refusal under observe or guarded) and #551 (what the planner
does next is a command the CLI prints, not prose).

## Root cause

Both reproduced in a scratch workspace with the CLI functions of this worktree.

### Defect 1: `config promote` overwrites a later owner choice

Reproduction: record `autonomy=Autonomous` (stores `outbound.default_tier = "send"`), then
the host-terminal `config set outbound.default_tier '"ask"'`, then `config promote`. The
promote diff is `-default_tier = "ask"` / `+default_tier = "send"`, and the file ends at
`send`.

- `cli/wuwei/commands/config.py:206-213` (`proposal`): every answer stored today
  (`interview.load`, `interview.settings`) and today's imported profile go to
  `calibrate.propose` on every promote.
- `cli/wuwei/calibrate.py:665-687` (`settle`): a present key whose value differs from the
  answer is replaced in place. Nothing tells it whether the difference is an answer not
  applied yet or an owner change made after calibration set the key, and nothing records
  that today: `COMMENT` (`calibrate.py:409`) marks only newly added sections,
  `.wuwei/calibration.json` (`config.py:258-260`) holds repository facts, and the
  `config.set` event (`setup.py:81`) is appended only for card writes, never for a
  host-terminal `config set` or a hand edit of `config.toml`.
- `cli/wuwei/commands/calibrate.py:152-157` (`_interview`): the Next line sends the owner to
  the whole `config promote`, and `promote` (`config.py:265-279`) cannot be limited: it
  surveys every repository, re-applies every stored answer and the profile, and rewrites
  `calibration.json`. An answer whose effects are charter-only (`carded` is false because it
  has no settings) still prints the config promote line.

### Defect 2: `config set docs.publish '[]'` proposes the default

Reproduction: `setup.merged(config, ['docs', 'publish'], [])` returns
`[(('docs',), 'publish', ['report', 'retro'])]`, and `config set docs.publish '[]'` writes
`publish = ["report", "retro"]`.

- `cli/wuwei/commands/setup.py:132-136` (`merged`): without `--replace`, a list value is
  added to the effective list (#492). The effective list of an absent `docs.publish` is the
  default `["report", "retro"]` (`workspace.py:110`); adding nothing returns the default,
  and `_settle` writes it. The fallback is not in the TOML writer: `configtext.place` writes
  `publish = []` when given `[]` (`--replace` does that today, checked).
- `cli/wuwei/commands/doctor.py:527-529` prints `bin/wuwei config set docs.publish '[]'`,
  which runs into `merged`. The doctor row itself is right.

## User Scenarios and Testing

### User Story 1: promote keeps a key the owner already set (Priority: P1)

The owner answered the interview, then changed one of its keys with `config set` (or by
hand). A later `config promote` keeps the owner's value, says so and prints the command that
applies the answer anyway.

**Independent Test**: record an answer, change its key, run `config promote`; the file keeps
the owner's value and the output names the key, its value and the `--keys` command.

**Acceptance Scenarios**:

1. **Given** a calibration answer stored for `outbound.default_tier = "send"` and a later
   `config set outbound.default_tier '"ask"'`, **When** `config promote` runs and the owner
   confirms, **Then** `config.toml` still says `default_tier = "ask"` and the output has
   the line
   `Skipped outbound.default_tier: kept "ask"; to apply the answer run bin/wuwei config promote --keys outbound.default_tier`.
2. **Given** that state, **When** `config promote --keys outbound.default_tier` runs and the
   owner confirms, **Then** `config.toml` says `default_tier = "send"`.
3. **Given** a stored answer whose key is absent from `config.toml`, **When**
   `config promote` runs, **Then** the key is added as today.
4. **Given** a stored answer whose key already holds the answer's value, **When**
   `config promote` runs, **Then** nothing changes and nothing is listed for it.

### User Story 2: an answer leads to a promote of only its keys (Priority: P1)

**Independent Test**: `calibrate --answer` for one question without its card answered, then
the printed promote command; only that answer's keys change.

**Acceptance Scenarios**:

1. **Given** `calibrate --answer autonomy=Autonomous` (card not answered) and other answers
   stored today, **When** it prints its Next line, **Then** the line is
   `Next: run bin/wuwei config promote --keys security.posture outbound.default_tier merge.default_tier outbound.learn autonomy.mode in a host terminal for these config keys.`
2. **Given** that command, **When** it runs and the owner confirms, **Then** only those keys
   change in `config.toml`: no other stored answer, no profile setting, no repository
   calibration addition, no `calibration.json` write, and no repository survey.
3. **Given** an answer whose effects are only charter or voice proposals, **When** it is
   recorded, **Then** the Next line is
   `Next: run bin/wuwei promote for the charter and voice proposals.` and names no config
   promote.
4. **Given** answers with both config keys and charter effects, **When** they are recorded,
   **Then** the Next line names `config promote --keys <their keys>` first, then
   `bin/wuwei promote for the charter and voice proposals.`
5. **Given** the card path wrote every config key of the answer and it has no charter
   effect, **When** it is recorded, **Then** there is no Next line.

### User Story 3: an empty list is written as an empty list (Priority: P1)

**Independent Test**: `config set docs.publish '[]'` in a host terminal.

**Acceptance Scenarios**:

1. **Given** a markdown docs system with `docs.publish` absent, **When** the owner runs
   `config set docs.publish '[]'`, **Then** the proposed diff and the written file say
   `publish = []`.
2. **Given** that workspace, **When** doctor's printed fix for the docs row is run as
   printed, **Then** doctor's docs row is ok afterwards.
3. **Given** a non-empty list value without `--replace`, **When** `config set` runs,
   **Then** it is still added to the effective list (#492 unchanged).

### Edge Cases

- A present key whose value differs from the answer and from its shipped default is
  skipped; `--keys` applies it. A key at its shipped default (the template ships
  `owner.verbosity.default = "brief"`, `control_plane.content = "summary"`,
  `deploy.deny = []`) is not owner-set, so a plain promote applies the answer (review F1).
- `deploy.deny` and `deploy.workflows` only grow (unchanged); a present deploy list the
  answer would grow is skipped like any other key, so a removed pattern stays removed until
  `--keys` names the list. `config set deploy.deny '[]'` stays a no-op, since deploy lists
  only grow.
- `--keys` names a key no stored answer sets today: the line
  `Not in today's answers: <key>; use a key listed under Interview answers, or answer its question first: bin/wuwei calibrate --questions`, nothing written, exit 1 (review F2).
- `--keys` with nothing to change: `No config.toml changes`, exit 0, no confirmation asked.
- Measured repository facts (`--measure`, the calibration survey) are not interview
  answers and keep today's behaviour.
- `setup` records answers and applies them in one run; it does not apply the skip rule, so
  its fresh answers are written as today.

## Requirements

### Functional Requirements

- **FR-001**: `config promote` never lets a stored interview answer overwrite a key present
  in `config.toml` with a value other than its shipped default, unless `--keys` names the
  key. It prints
  `Skipped <key>: kept <current value as JSON>; to apply the answer run bin/wuwei config promote --keys <key>`
  for each, in the digest the owner confirms. Absent keys are added as today.
- **FR-002**: `setup` does not apply FR-001; its answers are recorded and applied in the
  same run.
- **FR-003**: `config promote --keys KEY [KEY ...]` applies only the stored settings whose
  dotted key is listed, as today. It runs no repository survey, applies no repository
  calibration addition, writes no `calibration.json` and prints no approved-calibration
  block. A listed key no stored setting names prints `Not in today's answers: <key>; use a key listed under Interview answers, or answer its question first: bin/wuwei calibrate --questions`,
  writes nothing and exits 1. With
  nothing to change it prints `No config.toml changes` and exits 0 without asking. `--keys`
  and `--measure` are mutually exclusive. Doctor's call with a bare `Namespace()` keeps the
  full path.
- **FR-004**: `calibrate --answer` and `calibrate --interview` print the Next line from the
  recorded answers: the config keys of answers the card path did not write, as
  `config promote --keys <keys>`; the charter and voice step only when an answer has charter
  or voice effects; no Next line when neither remains.
- **FR-005**: `config set <list key> '[]'` writes an empty list, without `--replace`; a
  non-empty list value is still added to the effective list.
- **FR-006**: The design spec 9.2 table gets a row (next free id, I28 on current main): a
  stored answer never overwrites a key present with a value other than its default unless
  named in `--keys`;
  `tests/test_invariants.py` checks it and a broken-rule case proves the check fails when
  the rule is removed.
- **FR-007**: `docs/site/configuration.md` says that `'[]'` empties a list, that promote
  keeps a present key the owner changed from its default and lists it, and what `--keys`
  does.

## Success Criteria

- **SC-001**: the acceptance scenarios of the item pass as tests: the owner's `ask`
  survives promote and is listed with the command; `--keys outbound.default_tier` applies
  `send`; the Next line and its promote touch only the answer's keys;
  `config set docs.publish '[]'` writes `publish = []` and doctor's docs row is ok.
- **SC-002**: the 9.2 invariant walk passes with the new row, and fails when the skip rule
  is replaced by "keep every setting".
- **SC-003**: the existing tests of the touched modules pass, changed only where they
  assert the old Next line text or a promote that overwrote a present key.

## Assumptions

- Orchestrator override (ponytail): no new state file. The issue's "what calibration last
  wrote" is read as "a key present in `config.toml` with a value other than its shipped
  default": such a value is kept, whoever set it, and the skip line prints the exact
  command that applies the answer. A key at its default counts as untouched (review F1),
  so template keys take the answer through a plain promote. An owner who sets a key to
  exactly its default is not distinguished; the answer then applies, as before this item.
- Imported profile settings keep today's behaviour (not interview answers); a profile key
  an interview answer also sets is dropped before the skip rule, so a skipped answer never
  lets the profile overwrite the key.
- `--keys` takes dotted keys, not question ids, because the Next line names keys (item) and
  a repository answer's keys carry the repository index the owner sees in `config.toml`.
- The digest of `--keys` keeps the full `Interview answers:` block as context; only the diff
  and the write are limited to the named keys.
- `[]` on a list key means "empty it": adding nothing to a list is never the intent. Only a
  list is covered; an empty table `{}` for a named-entry table keeps today's behaviour.
- The item writes `config set outbound.default_tier ask`; the host-terminal `config set`
  takes a TOML value, so the tests use `'"ask"'`. A bare word stays a card-title form only
  (#579); changing that is not part of this item.
- `config set` stays a host-terminal or card action; no guard, posture or refusal changes
  (#530). The Next lines and the skip lines are exact commands (#551).
- #600 (Value row for config cards in `config set --from-card`) changes the card path; this
  item changes `merged`, which both paths call, and nothing in `_from_card`.

## Deferred

- An imported profile (`calibrate import`) is re-applied by every promote the same day and
  can overwrite an owner change; the skip rule covers interview answers only.
- The deploy.deny one-word patterns the interview proposes (separate task, item Out of
  scope).
