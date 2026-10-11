# Feature Specification: delete the setup interview, profiles and calibration cards; the host measure moves into dispatch

**Feature Branch**: `b4-setup-records` (feature directory `specs/832-setup-profiles-out/`)

**Created**: 2026-10-11

**Status**: Draft

**Input**: Issue #832, part 12 of the #789 deletion pass: "chore(setup): delete the setup
interview, profiles and calibration cards; the host measure moves into dispatch".

## Context

`wuwei setup` is a one-shot host-terminal flow. It runs `init`, discovers repositories, asks
the owner interview on stdin (or prints it as cards without a terminal), measures test
runners, applies one config proposal, connects Slack, writes the status line and the
permission allowlist, and offers the watch install. `wuwei calibrate` profiles repositories,
asks the interview again (`--interview`, `--questions`, `--answer`), writes a fast-checks
decision card for each repository without fast checks, and exports or imports shareable
profiles. `wuwei next` gates the day on setup and asks the unanswered interview questions as
cards every day.

Each of these makes the model or the owner reason about configuration as a process: which
question is still open, which card to relay, which host-terminal line to show. The owner
decided (2026-10-11) that nothing runs in a host terminal. `init`, `config set` and
`config add-repo` configure a workspace; the last two are answered on an Owner step card in
the session (#831). The repository survey stays behind `config promote`, which already asks
its own card. The host measure that derives CAP and the seat ceiling (`calibrate.host`) is
process control. It moves into `dispatch` unchanged.

Batches 1 to 3 and #831 are on the base:

- unknown config keys warn, and `workspace.RETIRED` exists;
- grants are gone, and decision classes changed;
- owner steps go through `sessions.needs_owner`.

`tests/test_reasons.py` lists LEFT rows naming part 12, and this part deletes them.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - CAP and seats derive exactly as before (Priority: P1)

Dispatch, the plan proposal, the launch guard and the plan template read CAP and the seat
ceiling from `dispatch.host`. It is the same function that was `calibrate.host`.

**Why this priority**: CAP and host seats are process control kept in code (pass plan
table). `next` never offers a launch past CAP, and the launch guard refuses one.

**Independent Test**: the moved host tests pass against `dispatch.host`. The launch guard,
`plan propose` and `dispatch next` tests pass unchanged.

**Acceptance Scenarios**:

1. **Given** process seats, free memory and today's readings, **When** `dispatch.host` runs,
   **Then** it returns the same `cap`, `seats`, `bound` and `text` the old tests expected.
2. **Given** a running seat count at the ceiling, **When** a seat launches, **Then** the launch
   guard refuses as today, naming CAP or `host.seats`.
3. **Given** the cores cannot be measured, **When** `dispatch.host` runs, **Then** it returns
   the unmeasured fallback. Its text names `bin/wuwei doctor`, not a deleted command.

### User Story 2 - A workspace is configured in the session (Priority: P1)

**Acceptance Scenarios**:

1. **Given** no workspace, **When** `wuwei next` runs, **Then** it returns `no-workspace` with
   the command `bin/wuwei init --shadow` and the run instruction. No text names a host
   terminal.
2. **Given** a workspace with no `[[repos]]`, **When** `wuwei next` runs, **Then** it returns
   `setup` with the command
   `wuwei config add-repo --name <owner/repo> --path <path> --branch <branch>`. Its `then`
   tells the planner to ask the owner for each repository and run the command, which asks its
   Owner step card.
3. **Given** a workspace with repositories and no `.wuwei/calibration.json`, **When**
   `wuwei next` runs, **Then** it does not stop at `setup`, and the day proceeds. `doctor`
   warns `never applied` with the fix `wuwei config promote`.
4. **Given** any day, **When** `wuwei next` runs, **Then** no `calibrate` row appears.

### User Story 3 - The calibration survey stays behind config promote (Priority: P2)

**Acceptance Scenarios**:

1. **Given** configured repositories, **When** `wuwei config promote` runs, **Then** it
   surveys them, prints the proposal and the snapshot, and asks its Owner step card as today.
   It no longer reads interview answers or an imported profile.
2. **Given** `--measure`, **When** `config promote --measure` runs, **Then** it times the test
   runners and proposes only the fast ones, as today.
3. **Given** calibration drift today, **When** `doctor` runs, **Then** the drift row warns
   with the fix `wuwei config promote` and no `--fix` id.

### User Story 4 - Nothing names the interview, profiles or calibration cards (Priority: P2)

**Acceptance Scenarios**:

1. **Given** the CLI, **When** `wuwei setup` or `wuwei calibrate` runs, **Then** argparse
   refuses it as an invalid choice (SystemExit 2).
2. **Given** `doctor`, **When** it runs, **Then**:
   - it has no `interview` or `profile` row;
   - its FIXES have no `calibrate` id;
   - the telemetry row names `config set telemetry.share`.
3. **Given** the retro, **When** it is written, **Then** it has no `## Owner preferences`
   section.
4. **Given** `init --upgrade`, **When** it runs, **Then** it prints no unanswered-questions
   line.
5. **Given** a strict workspace whose repository has no fast checks, **When** `build next`
   runs, **Then** it builds. CI and the gates are the evidence, as outside strict.

### Edge Cases

- A workspace an older `setup` wrote keeps its config values. Every interview effect is a real
  config key, and none is retired.
- Old day files stay in their day directories and age out with the archive:
  `interview.json`, `profile.json`, `proposals/interview-*.json`, `proposals/profile-*.json`
  and `proposals/calibration-*.json`. A pending proposal file still lands through
  `wuwei promote`, which is unchanged.
- A charter override the interview wrote keeps its `## Owner preferences (interview)` block.
  Nothing reads it any more, because the mandate's trust-surface line goes.
- The rules the allowlist answer wrote to `.claude/settings.local.json` stay. Nothing writes
  new ones.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `calibrate.host`, `processes`, `SEAT_MIB` and `_gb` MUST move into
  `dispatch.py`, unchanged except the unmeasured text. Every caller (`dispatch`, `plan`,
  `commands/plan`, `guards/agent_launch`) MUST call `dispatch.host`. The host tests MUST
  move with them.
- **FR-002**: `commands/setup.py`, `commands/calibrate.py`, `interview.py`, `profiles.py`,
  `templates/profiles/` and their tests MUST be deleted. The config edit frame MUST move into
  `commands/config.py`, and every importer MUST import it from there. The frame is `_edit`,
  `card_write`, `_settle`, `_parts`, `write_value`, `effective`, `changed`, `merged`,
  `_choice`, `assignment`, `declared`, `_from_card`, `set_value`, `repo_tables`, `add_repo`,
  `KEY` and `IDENTITY`.
- **FR-003**: `calibrate.py` MUST lose the cards: `CHECKS`, `NOTHING`, `_record`,
  `checks_text`, `checks_record`, `checks_answered` and `propose_checks`. It MUST also lose
  the code only setup or the calibrate command reached: `charter_proposals`, `report`,
  `SECTIONS`, `LABELS`, `_label`, `commit_style`, `CONVENTIONAL`, `SCOPE`, `bot_authors`,
  `kept`, the `style` survey and the `settings` argument of `propose`.
- **FR-004**: `config promote` MUST survey and propose without interview answers or profiles.
  `--keys` MUST go with the answers it applied.
- **FR-005**: `wuwei next` MUST gate the day only on a workspace and at least one repository,
  with the rows of US2. It MUST have no `calibrate` row and no `THEN['calibrate']`.
- **FR-006**: `doctor` MUST drop the `interview` and `profile` rows and the `calibrate` fix.
  The calibration and drift rows MUST point at `wuwei config promote`.
- **FR-007**: `build next` MUST NOT refuse under strict for a repository without fast checks.
- **FR-008**: `init.allow`, `allow_rules`, `ALLOW`, `init.status_line`, `specmode.detect`
  and `docs.detect` MUST go, because setup was their only caller.
- **FR-009**: No module, command, charter, skill or docs page refers to the setup interview,
  profiles or calibration cards. The part 12 LEFT rows in `tests/test_reasons.py` MUST be
  deleted, and the test MUST pass with no new LEFT row.

### Key Entities

- **dispatch.host** result: `cap`, `seats`, `bound` and `text`. When measured it also has
  `cores`, `free_mib`, `seat_mib`, `seat_source` and `reading`; when unmeasured, `unmeasured`.

## Success Criteria *(mandatory)*

- **SC-001**: Every touched test file passes. No test is loosened. Only tests of deleted code
  are deleted, and the host tests are moved, not rewritten.
- **SC-002**: this grep over `cli/`, `charters/`, `skills/`, `agents/`, `hooks/`,
  `templates/`, `scripts/` and `docs/site/` returns only the sensitive keyword `"interview"` in
  `workspace.py` and in its template comment:
  `grep -rnE "interview|profiles\.|calibrate --|wuwei setup|setup --shadow|commands\.setup|commands import setup|checks_answered|propose_checks"`.
- **SC-003**: Every launch the CAP or seat ceiling refused before is still refused, and every
  launch it allowed is still allowed (the moved tests).

## Assumptions

Open questions answered with the recommendation (strict, non-interactive):

1. The whole `setup` command goes, Slack included, because every branch needs stdin at a host
   terminal. Credentials are set in `.wuwei/env`; `config check` and `doctor` already name each
   missing one. `outbound.owner.slack.user` is set with `config set`.
2. The config edit frame moves into `commands/config.py`, which already registers `set` and
   `add-repo`. A module named after a deleted command would mislead. A `commands/` module
   without `register` breaks command discovery.
3. The repository survey is not a card and stays behind `config promote`: the detectors,
   `survey`, `propose`, `drift` and `approved` in `calibrate.py`. The steward's drift check
   reads it. `calibrate.py` keeps its name, and `[calibrate] fast_check_seconds` stays.
4. `.wuwei/calibration.json` stops gating the day. It is the drift baseline, not a process
   check, and `doctor` warns when it is missing.
5. A repository without fast checks builds under strict. The refusal existed only to ask the
   fast-checks card once (#600), so it is (a) machinery.
6. The permission allowlist writer and the status line writer go with setup, their only
   callers. `init` keeps printing the status line JSON for the owner to place. The allowlist
   was a convenience, not a guard.
7. No config key is retired. Every interview effect is a real key, and `calibrate` stays.
8. The retro's `## Owner preferences` section goes with `interview.reask`. It proposed
   `merge.auto` from decision records. Promotion of retro proposals is untouched.
9. `profiles.ABSOLUTE` moves into `tracker.py`, and `commands/note.py` imports it from there
   until part 13 deletes it. `decision.py` takes `ROLES` from `commands.agents` until part 14.
10. The design spec, README and docs pages are edited only where they describe the deleted
    units. The site rewrite is part 24.
