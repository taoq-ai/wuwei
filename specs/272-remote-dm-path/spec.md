# Feature Specification: The DM path works from the runbook alone

**Feature Branch**: `272-remote-dm-path`

**Created**: 2026-09-30

**Status**: Draft

**Input**: GitHub issue #272, "fix(remote): the DM path works from the runbook alone".
Evidence: the operator dry run of `docs/site/remote.md` against a simulated Slack on main
d555d10 (verdict no, findings F1 to F11). This feature covers F1, F2, F7, F10 and F11.

## Root cause (reproduced before specifying)

- **F1, every DM command is dropped silently.** `cli/wuwei/env.py:12-14` lists
  `SLACK_OWNER_DM_CHANNEL` in `CREDENTIALS`, and `env.load` (`cli/wuwei/env.py:79` and
  `:85`) adds every `.wuwei/env` value to `redact.VALUES`. `state._append_jsonl`
  (`cli/wuwei/state.py:174`) stores every record through `redact.known_values`, so the
  inbox line for a DM is stored as `{"id": "[REDACTED]/<ts>", "channel": "[REDACTED]", ...}`
  (seen in the dry-run workspace inbox). `remote.handle` (`cli/wuwei/remote.py:200`)
  compares `event['channel']` with the raw `SLACK_OWNER_DM_CHANNEL`, never matches, and
  returns 0 with no output, after the listener has already advanced `handled`. A second
  break has the same cause: `sent.json` stores the raw `D.../<ts>` ids that `remote.dm`
  sent, so the own-reply guard at `remote.py:203` can never match a redacted inbox id.
  Setting the variable in the process environment does not help: `env.session`
  (`env.py:33`) redacts `CREDENTIALS` read from the environment too. The existing tests
  missed it because every one sets the channel with `monkeypatch.setenv` after the
  redaction set is built, never through `.wuwei/env` and `main`.
- **F2, every reply is refused when `owner.name` is unset, and some when it is set.**
  `remote.dm` (`cli/wuwei/remote.py:153-155`) runs `outward.check_lint`, whose `lint`
  (`cli/wuwei/outward.py:38-40`) returns exit 2 `outward: owner name must be configured`
  for an empty `owner.name` (the template default), and whose third-person rule
  (`outward.py:59-62`) refuses a fixed line whose words collide with the owner's name:
  with `owner.name = "Dry Run Operator"`, `remote.CONFIRM` ("...to run it...") is refused
  as `outward: third-person owner reference`. Both reproduced in-process on this branch.
- **F7.** `listen.tick` (`cli/wuwei/listen.py:51`) returns 1 whenever new events were
  stored, and `listen.py:70` folds each handled command's 1 (refused, or answered with the
  command list) into the result, so `listen --once` exits 1 on a normal poll.
- **F11.** `adapters/chat/slack.py:14` hard-codes `URL = 'https://slack.com/api/'`; the
  dry run had to patch the module in memory to reach a fake Slack.
  `adapters/inbound/slack.py` reads through `chat.slack.history`, so one base serves both.
- **F10.** `docs/site/adapters.md:25` says control planes are planned with no config keys;
  `[control_plane]` ships in the template and `remote.md` documents it.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A DM command is answered with only `.wuwei/env` configured (Priority: P1)

The owner follows `docs/site/remote.md` on a fresh workspace: sets both Slack adapters,
writes `SLACK_BOT_TOKEN` and `SLACK_OWNER_DM_CHANNEL` into `.wuwei/env`, sends `hello` in
the owner DM and runs `bin/wuwei listen --once`. The DM answers exactly as the page says.

**Why this priority**: F1 is a blocker; without it no remote command ever runs.

**Independent Test**: in-process `main(['init', ...])`, `.wuwei/env` written as a real
`0600` file, a fake Slack behind `urllib.request.urlopen`, then `main(['listen', '--once'])`.

**Acceptance Scenarios**:

1. **Given** the runbook followed exactly against a fake Slack with a fresh workspace and
   no pin, **When** the owner sends `hello` in the DM and runs `listen --once`, **Then** the
   output contains the section 3 pin line naming the sender and the DM receives
   "That command could not run; see the listener log on the host."
2. **Given** the pin copied into `control_plane.owner`, **When** the owner sends `hello`
   again and runs `listen --once`, **Then** the DM receives the command list and the exit
   is 0.
3. **Given** a stored inbox line, **Then** its `channel` and `id` carry the real DM channel
   id, not `[REDACTED]`, and every real credential in `.wuwei/env` (tokens, the TOTP
   secret, `SLACK_API_BASE`) is still redacted in stored records and output.
4. **Given** an inbox line from any channel other than `SLACK_OWNER_DM_CHANNEL`, **When** the
   listener handles it, **Then** it is not a command and the listener log has one
   `remote.unmatched` line naming the event id.

### User Story 2 - Replies to the owner do not depend on `owner.name` (Priority: P1)

**Why this priority**: F2 is a blocker; the template ships `owner.name = ""`.

**Independent Test**: `remote.dm` and `listen --once` with `owner.name` unset and with a
name whose words occur in the fixed reply lines.

**Acceptance Scenarios**:

1. **Given** an unset `owner.name`, **When** `config check` runs, **Then** it prints one
   `owner.name: not set` line saying outward messages other than owner DM replies are
   refused.
2. **Given** an unset `owner.name`, **When** the listener starts (`listen --once` or the
   loop), **Then** its log says so exactly once, however many messages it handles.
3. **Given** an unset `owner.name`, **Then** the DM still gets the documented replies.
4. **Given** `owner.name = "Dry Run Operator"`, **When** the owner sends `plan`, **Then**
   the DM receives `remote.CONFIRM` unchanged.
5. **Given** any message to anyone but the pinned owner (MCP hooks, chat-port drafts,
   posts), **Then** the outward lint is unchanged: an unset name is still exit 2 and a
   third-person owner reference is still a finding.

### User Story 3 - `listen --once` exit codes are sane and documented (Priority: P2)

**Acceptance Scenarios**:

1. **Given** `listen --once` with no new events, **Then** exit 0.
2. **Given** `listen --once` that stores new events and handles commands, including a
   refused one, **Then** exit 0.
3. **Given** a configuration error (no inbound adapter, a missing credential, no pin, a
   poll or store that could not run), **Then** exit 2 with the reason printed.

### User Story 4 - The Slack API base can point at a fake or a proxy (Priority: P2)

**Acceptance Scenarios**:

1. **Given** `SLACK_API_BASE` in `.wuwei/env`, **When** the listener polls and replies,
   **Then** every request goes to that base and the base never appears in any output.
2. **Given** no `SLACK_API_BASE`, **Then** requests go to `https://slack.com/api/`.
3. **Given** a `SLACK_API_BASE` that is neither `https://` nor `http://` to a loopback
   host, **Then** the adapter call fails closed (exit 2) with a reason that does not
   contain the value, and no request is made.

### User Story 5 - adapters.md no longer calls control planes planned (Priority: P3)

1. **Given** `docs/site/adapters.md`, **Then** it names `[control_plane]` and links the
   remote page, and does not say control planes are planned with no config keys.

### Edge Cases

- Inbox lines stored before this fix keep `[REDACTED]` channels. They are not rewritten
  (the inbox is append-only); they log `remote.unmatched` and are never commands.
- A reply sent with `SLACK_USER_TOKEN` polls back as an owner message; with the channel no
  longer redacted its id matches `sent.json` and it is skipped, so the existing guard now
  works on the real path.
- `SLACK_API_BASE` with or without a trailing slash resolves to the same method URLs.
- `SLACK_OWNER_DM_CHANNEL` set only in the process environment is not redacted either.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `SLACK_OWNER_DM_CHANNEL` MUST NOT be added to the redaction set, whether it
  comes from `.wuwei/env` or the process environment. It stays in `CREDENTIALS`, so it is
  still kept from seat subprocesses. Every other `.wuwei/env` value and every other
  `CREDENTIALS` name MUST still be redacted.
- **FR-002**: `remote.handle` MUST print one `listen remote.unmatched: <event id> ...` line
  for each inbox line it skips because the channel is not the owner DM. The line carries
  no message text.
- **FR-003**: Messages `remote.dm` sends to the owner DM MUST pass the outward lint with the
  third-person rules (owner name, handles, pronouns) and the owner-name-configured
  requirement skipped; every other check (security check, internal-state patterns, emoji,
  banned characters, length, voice) MUST still apply.
- **FR-004**: Every other caller of the outward lint MUST behave exactly as before; the
  owner-addressed path is a keyword argument no hook payload can set.
- **FR-005**: `config check` MUST print an `Owner:` section with `owner.name: set` or the
  `owner.name: not set; ...` line. Its exit code is unchanged by this line, like
  `GH_TOKEN: not set`.
- **FR-006**: The listener MUST print the same `owner.name: not set` line once per start.
- **FR-007**: `listen.tick` MUST return 0 after a successful poll and store, whatever was
  stored or answered, and 2 when a poll, a store or the handling of a command could not
  run.
- **FR-008**: The Slack chat and inbound adapters MUST use `SLACK_API_BASE` when set and
  `https://slack.com/api/` otherwise. Only `https://` bases, or `http://` to `127.0.0.1`,
  `localhost` or `::1`, are accepted. `SLACK_API_BASE` is a redacted credential kept from
  seats.
- **FR-009**: `docs/site/remote.md` MUST name `owner.name` in section 3, document
  `SLACK_API_BASE` as optional in section 2 and the `listen --once` exit codes in section
  5; `docs/site/configuration.md` and `docs/site/adapters.md` MUST match; the docs test
  pins the new remote.md text.
- **FR-010**: A test MUST drive the listener through `main` with a real `0600`
  `.wuwei/env` (not `monkeypatch.setenv`) and a fake Slack, covering User Story 1.

## Success Criteria *(mandatory)*

- **SC-001**: The dry run's steps 3a to 3d need no workaround and no step outside the page.
- **SC-002**: The full suite passes with `python -m pytest -q`.
- **SC-003**: No redaction or outward-lint rule is weakened for any destination other
  than the pinned owner's DM.

## Assumptions

- **A channel id is an identifier, not a secret** (issue text). It stays in `CREDENTIALS`,
  so seats still do not inherit it; only redaction changes. Chosen over "match on a value
  that survives storage" because a redaction-aware compare would leave `sent.json` ids
  (raw) and inbox ids (redacted) unequal, which breaks the own-reply guard under
  `SLACK_USER_TOKEN`, and `[REDACTED]` would match any channel carrying any secret.
- **Third-person rules cover pronouns too.** The issue names the owner-name rule; the
  pronoun rule is the same third-person check in the same loop and would refuse `ask`
  answers containing "they" for an owner with they/them pronouns. Both are skipped for
  owner-DM replies only.
- **Only `remote.dm` is owner-addressed.** Chat-port `dm` drafts and `drafts approve` keep
  the full lint; widening them is not in this issue.
- **A missing `owner.name` is reported, not scored.** `config check` keeps its exit code
  for it, following the `GH_TOKEN: not set` precedent: without a name every other outward
  message already fails closed (exit 2), and a fresh `init` still passes `config check`
  (pinned by `tests/test_workspace.py::test_initialized_config_checks`).
- **"Once in the listener log" means once per listener start**, not once per day.
- **`listen --once` keeps a handled command's exit 2**: the section 3 no-pin run exits 2
  and prints the pin line. A refused command or a command-list reply is a normal poll,
  exit 0. The loop ignores tick codes, so only `--once` changes.
- **`http://` is accepted only for loopback** so a fake Slack on the host works while a
  typo cannot send the bot token in clear across the network.
- **Pre-fix inbox lines are not migrated**; the owner resends a lost command.
- F3 to F6, F8 and F9 from the same dry run are out of scope (other issues).
