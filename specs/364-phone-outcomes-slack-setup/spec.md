# Feature Specification: phone answers to two-way decisions are outcomes, and `wuwei setup slack` connects the DM in one command

**Feature Branch**: `364-phone-outcomes-slack-setup`

**Created**: 2026-10-03

**Status**: Draft

**Input**: GitHub issue #364, from the UX adoption sweep of 2026-10-03 (findings F10, F11),
plus the owner's addition of the same day (ask which communication tools the team uses).
Owner's brief: "I want the adoption to be easiest as possible. The workflow should coach
people with less experience instead of simply blocking." Coaching means: what happened,
why, and the one command with real values; do it for the owner and say so before asking,
and ask before refusing. Depends on #354 (y/N and in-session confirmation, in review, not
on `main`) and #359 (owner questions as widgets, on `main`). See Assumptions for how this
spec builds before and after #354.

## Root cause (read and reproduced on main, b2a4557)

Reproduced in-process in a scratch workspace: one owner-routed decision `D-1` with
`Reversibility: two-way` and `Blast radius: workspace`, pin `T1/U1`, and the DM reply
`option B on D-1` from the pinned sender through `remote.handle` with a fake transport:

```text
exit 0 dm ['Recorded D-1 option B. Confirm it on the host.']
decision_outcomes None
record Outcome line ['Outcome: pending']
status line WUWEI no plan yet | pages 0 | nudges 1 | watch off | phone answers 1 | meeting unmeasured
```

- **F10, a DM answer is evidence only, whatever the decision.** `cli/wuwei/remote.py:267-283`
  (`handle`, the `command is None` branch) appends `decision.replied` and answers
  `Recorded D-n option X. Confirm it on the host.` for every decision. It never reads the
  record's `Reversibility:`, so a two-way decision still needs the owner at a host terminal.
  The only owner-outcome writer is `cli/wuwei/commands/decision.py:90-140`
  (`owner_outcome`), which finds the workspace from the working directory (`:92`) and
  always asks the host terminal (`:114`, `integrity._host_confirm`). Until then
  `cli/wuwei/commands/status.py:209-212` keeps the `D-n answered from the phone` nudge and
  `phone answers N`. `cli/wuwei/control_plane.py:111-137` (`poll_replies`) records the same
  evidence but has no production caller; the listener reaches every DM reply through
  `remote.handle`.
- **F10, the Remote Control path.** The planner's question widget carries
  `record: wuwei decision outcome D-n <label>` (`cli/wuwei/decision.py:146`), which
  `cli/wuwei/guards/protect_state.py:48` refuses in the session. #354 adds `wuwei decide`,
  the session allowance for an asked `D-n` and the y/N prompt; that is the Remote Control
  half of this finding and is not rebuilt here.
- **F11, Slack takes about 14 manual steps.** `bin/wuwei setup slack` gives
  `wuwei: error: unrecognized arguments: slack` (`cli/wuwei/commands/setup.py:26-35`
  registers no target). `docs/site/remote.md` has the owner edit both adapters and the pin
  in `config.toml` by hand (sections 2 and 3, one digest each), find the Slack ids by
  running `listen --once`, which is meant to exit 2 (`:113-124`), make the TOTP secret with
  a pasted Python one-liner (`:146-148`), build the QR themselves, and reinstall the
  listener after each `.wuwei/env` edit (`:191-192`). The CLI has no writer for
  `.wuwei/env` (`cli/wuwei/env.py` only creates it empty and reads it).
- **Owner addition, tools nobody asks about.** `cli/wuwei/interview.py:199-210` offers only
  `None` or `Linear` for the tracker and `None` or `Slack` for chat. An owner on Microsoft
  Teams or Jira picks `None` and is not told that nothing will arrive, or why.
  `discover` (`cli/wuwei/commands/setup.py:159-181`) owes a repository with a GitLab or
  other non-GitHub remote as `config add-repo --name owner/repo ...` without saying the code
  host is the reason.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A DM answer to a two-way decision is the outcome (Priority: P1)

The pinned owner answers a two-way decision from the Slack DM (`approve D-n`,
`option X on D-n` or `drop it`). The listener records the owner outcome at once, exactly
as `decision outcome` does after its confirmation (state, event, record, parked items
resumed), and the DM says so. A one-way or `unsure` decision keeps the host confirmation;
its DM reply says what was noted, why the host is needed, and the exact command.

**Why this priority**: the finding the issue is named after; two-way answers are the common
case and today each one needs a terminal.

**Independent Test**: `python -m pytest -q tests/test_remote.py -k "two_way or one_way"`.

**Acceptance Scenarios**:

1. **Given** an owner-routed decision D-1 with `Reversibility: two-way`, no live remote
   session and the pin `T1/U1`, **When** `T1/U1` sends `option B on D-1` in the owner DM,
   **Then** the handler exits 0, the DM is
   `Recorded D-1 option B as your outcome; it can be undone, so no host step is needed.`,
   state `decision_outcomes.D-1` has `option: B`, `decided_by: owner` and
   `reversibility: two-way`, a `decision.decided` event with `decided_by: owner` and one
   `decision.replied` event are appended, the record's `Outcome:` is `B`, and the status
   line has no `phone answers`.
2. **Given** the same D-1 linked to a parked item (`phase: parked`, `status: blocked`,
   `resume_phase: planned`), **When** the answer is recorded, **Then** the item is back in
   `planned` and `queued`, as with `decision outcome`.
3. **Given** a two-way D-1 raised by a live remote `plan` session, **When** the owner
   answers, **Then** the outcome is recorded, the DM first gets the recorded line, and the
   session resumes with `Decision D-1: option B.` as today.
4. **Given** `approve D-1` or `drop it` on a two-way D-1, **Then** the recommendation, or the
   Do nothing or Defer option, is recorded the same way.
5. **Given** an owner-routed D-1 with `Reversibility: one-way` (or `unsure`), **When** the
   owner sends `option B on D-1`, **Then** nothing is recorded in `decision_outcomes`, one
   `decision.replied` event is appended, and the DM is
   `Noted D-1 option B. D-1 cannot be undone, so confirm it on the host: decision outcome D-1 B.`
   The first answer still stands (`ANSWERED` for a different second answer, unchanged).
6. **Given** a sender other than the pin, or the pinned user id with another team, **Then**
   nothing changes from today: ignored, or refused and paged.
7. **Given** the outcome writer refuses (the record changed under it, or another owner
   outcome landed first), **Then** the handler prints `listen remote unmeasured: <reason>`,
   the DM is the fixed `FAILED` line, it exits 2, and no outcome is half-written.
8. **Given** every new fixed DM line, **Then** it passes the default outward lint addressed
   to the owner (no `wuwei`, no third-person owner words).

---

### User Story 2 - `bin/wuwei setup slack` connects the DM in one command (Priority: P1)

From a host terminal, `bin/wuwei setup slack` reads the bot token with a hidden prompt and
the owner DM channel id, writes both to `.wuwei/env` (mode 0600), waits for one message in
that DM, shows its sender and pins it in one confirmation together with
`adapters.chat = "slack"` and `adapters.inbound = "slack"`, generates `WUWEI_TOTP_SECRET`
and prints the `otpauth://` URI, installs the listener (or restarts it when installed), and
ends with `config check`. Each step prints one line saying what it did. A value already
set is kept and named, so running it again is also the way to restart the listener after
an env edit.

**Why this priority**: the second finding; it replaces about 14 manual steps and four
digests.

**Independent Test**: `python -m pytest -q tests/test_setup.py -k slack` and
`python -m pytest -q tests/test_env_credentials.py -k write`.

**Acceptance Scenarios**:

1. **Given** a workspace with no Slack settings, a fake inbound adapter that returns one DM
   message from `T0123ABC/U0123ABC` sent after the wait starts, and the confirmation
   accepted, **When** the owner runs `setup slack` and types a bot token and `D0123ABC`,
   **Then** `.wuwei/env` has mode 0600 and holds `SLACK_BOT_TOKEN`,
   `SLACK_OWNER_DM_CHANNEL` and a base32 `WUWEI_TOTP_SECRET` that decodes to 20 bytes,
   `config.toml` has `adapters.chat = "slack"`, `adapters.inbound = "slack"` and
   `control_plane.owner = "T0123ABC/U0123ABC"`, the output names the sender, prints
   `otpauth://totp/WUWEI:owner?secret=<secret>&issuer=WUWEI&algorithm=SHA1&digits=6&period=30`
   and the listener install, `config check` ran, and the token never appears in the output.
2. **Given** the token prompt, **Then** it is read with `getpass` (hidden); a value that does
   not start with `xoxb-` is refused without echoing it, naming where the bot token is in
   the Slack app settings; exit 1, nothing written.
3. **Given** an empty token or channel answer, **Then** setup slack writes nothing, says
   how to get the value and to run `bin/wuwei setup slack` again, and exits 1.
4. **Given** the owner declines the confirmation, **Then** `config.toml` is unchanged, no
   TOTP secret is written, the listener is not touched, and the exit is 1.
5. **Given** no DM message arrives within the wait (5 minutes), **Then** it says which Slack
   app settings to check (Messages Tab, `im:history`) and to run it again; exit 1, pin and
   adapters unchanged.
6. **Given** the inbound poll cannot run (bad token, network), **Then** it prints the
   adapter's reason with the same hint and exits 2.
7. **Given** a second run with the token, channel, pin, adapters and TOTP secret already
   set and the listener installed, **Then** nothing is prompted or rewritten, each kept
   value is named, no DM wait happens, and the listener is uninstalled and installed again
   (restarted) so it reads `.wuwei/env` afresh.
8. **Given** an agent tool runs `wuwei setup slack`, **Then** it is refused as today
   (`setup` is a whole owner group in `protect_state`); without a terminal it exits 2 with
   the host-terminal reason.
9. **Given** `setup` (the main command) where this run's interview chat answer is Slack and
   `adapters.inbound` is still `none`, **When** the config is applied, **Then** setup goes
   straight into the same Slack steps; an empty token answer skips them and leaves
   `bin/wuwei setup slack` on the `Optional:` line.

---

### User Story 3 - The interview asks which tools the team uses (Priority: P2)

The chat question asks which tool the team uses for messages and offers Slack, Microsoft
Teams, Discord and None, with any other tool (email, for example) typed as free text. The
tracker question offers None, Linear, GitHub Issues and Jira. A supported answer sets its
adapter (Slack leads into `setup slack`, US2). An unsupported answer is recorded in
`interview.json`, sets the adapter to `none`, and its description says in one line that
the tool is not supported yet and links the integrations backlog issue. Setup's discovery
says in one line when a repository's remote is not on GitHub.

**Why this priority**: the owner's addition; it removes the guess about why nothing
arrives, but changes no runtime behaviour.

**Independent Test**: `python -m pytest -q tests/test_interview.py -k "tools or table"` and
`python -m pytest -q tests/test_setup.py -k other_hosts`.

**Acceptance Scenarios**:

1. **Given** `effects('chat', 'Microsoft Teams')` and `effects('chat', 'Discord')`, **Then**
   each is `{'adapters.chat': 'none'}` and its description contains `not supported yet` and
   `https://github.com/taoq-ai/wuwei/issues/370`.
2. **Given** the free answer `Email` (any case) to chat, **Then** it is kept as typed and its
   effect is `{'adapters.chat': 'none'}`; a Slack channel id such as `C0123ABCD` still gives
   `{'adapters.chat': 'slack', 'shepherd.review_channel': 'C0123ABCD'}`; text that is
   neither (`c-lower!`) is refused naming both forms.
3. **Given** `effects('tracker', 'GitHub Issues')` and `effects('tracker', 'Jira')`, **Then**
   each is `{'adapters.tracker': 'none'}` with the same backlog line in its description;
   `Linear` and `None` are unchanged.
4. **Given** the question table, **Then** every row still fits a widget (2 to 4 choices,
   header at most 12 characters, no first-person labels).
5. **Given** a repository whose `origin` is `git@gitlab.example.test:acme/app.git`, **When**
   setup discovers it, **Then** one line names the host `gitlab.example.test` and says WUWEI
   reads GitHub only today, with the backlog link; the owed `config add-repo` line stays.

---

### User Story 4 - remote.md leads with the one command (Priority: P2)

`docs/site/remote.md` opens with `bin/wuwei setup slack` and what each of its steps does,
keeps the manual steps (Slack app, pin, second factor, listener) as reference, and its
decisions section says which DM answers are outcomes and which still need the host.
`daily.md` and `configuration.md` stop saying that every phone answer needs the host.

**Independent Test**: `python -m pytest -q tests/test_docs.py`.

**Acceptance Scenarios**:

1. **Given** remote.md, **Then** the first section after the introduction is
   `## Connect Slack in one command` with `bin/wuwei setup slack`, before
   `## 1. Remote Control, no setup`, and sections 1 to 8 keep their headings and order.
2. **Given** section 7, **Then** it contains the two-way and the one-way DM lines of US1
   verbatim, and says `phone answers 1` applies to one-way answers only.
3. **Given** the existing docs test, **Then** every `bin/wuwei <command>` on the page still
   names a command module, and the Python secret one-liner and the `otpauth://` URI stay as
   reference.

### Edge Cases

- A two-way record edited after routing so it no longer validates: `control_plane.pending`
  raises as today; the handler exits 2 with FAILED.
- A seat outcome already on an owner-routed decision: the owner outcome replaces it and the
  event is `decision.reversed`, as `decision outcome` does today.
- Two DM answers to the same two-way decision in one poll: the first records the outcome;
  the second finds D-n no longer pending and gets the command list, as for any decision
  that is not waiting.
- MCP decisions are not in `decision_routes`, so they are never pending in the DM;
  unchanged.
- `setup slack` on a platform without a service manager (not macOS or Linux): it says to run
  `bin/wuwei listen` in a terminal that stays open; that step does not raise the exit.
- `setup slack` with `outbound.work_channels` set and no Slack id in `owner.handles`: the
  inbound poll refuses (`owner.handles has no Slack user id for mentions`); exit 2 with that
  reason, as in US2 scenario 6.
- `.wuwei/env` that is a symlink: the env writer refuses with a reason; exit 2.
- `SLACK_BOT_TOKEN` already in the process environment but not in `.wuwei/env`: it is kept
  and named as set; nothing is written for it.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A DM answer from the pinned owner to an owner-pending decision whose
  `Reversibility:` is `two-way` MUST record the owner outcome through the same writer as
  `decision outcome` (validation, state, `decision.decided` or `decision.reversed` event,
  record `Outcome:`, parked items resumed), without a host prompt, and MUST say so in the DM.
- **FR-002**: A DM answer to a `one-way` or `unsure` decision MUST NOT record an outcome; it
  stays `decision.replied` evidence, and the DM line MUST name the host command with the
  real id and option.
- **FR-003**: The sender pin, the `changed` refusal and the one-session-per-thread resume
  MUST be unchanged; no second factor is added to or removed from decision answers.
- **FR-004**: `bin/wuwei setup slack` MUST run only at a host terminal and as an owner
  action, read the bot token without echo, write credentials to `.wuwei/env` with mode
  0600 keeping every other line, and never print the token.
- **FR-005**: `setup slack` MUST wait for one DM message through the inbound port (no new
  Slack API method or scope), show its sender id, and apply the pin and both adapters in
  one owner confirmation through the existing config edit path.
- **FR-006**: `setup slack` MUST generate `WUWEI_TOTP_SECRET` (20 random bytes, base32) only
  when none is set, and print the `otpauth://` URI once.
- **FR-007**: `setup slack` MUST install the listener, or uninstall and install it when its
  unit exists, after the env and config are written, and end with `config check`; its exit
  is the highest of its own steps and `config check`.
- **FR-008**: Every refusal or skip in `setup slack` MUST say what happened, why, and the
  one command or Slack setting that fixes it.
- **FR-009**: The interview MUST offer the tools named in the issue as choices or free text
  within the existing 2-to-4-choice widget shape; an unsupported answer MUST set its adapter
  to `none` and carry the backlog line.
- **FR-010**: `docs/site/remote.md` MUST lead with the one command and keep the manual
  steps as reference.

### Key Entities

- **Owner outcome**: `decision_outcomes.<D-n>` with `decided_by: owner`; written only by the
  CLI (`decision outcome`, and now the listener for a two-way DM answer).
- **`.wuwei/env`**: the private credentials file; gains a writer that sets named lines.

## Success Criteria *(mandatory)*

- **SC-001**: A two-way decision answered in the DM needs zero host steps; the status line
  shows no `phone answers` for it.
- **SC-002**: Connecting Slack from a created Slack app is one command with two typed values
  (token, DM channel id), one DM message and one confirmation.
- **SC-003**: `python -m pytest -q` passes, and no changed file holds an emoji, an em-dash or
  an absolute local path.

## Assumptions

- **Second factor.** "With the second factor where required" is read as the factor rules
  that already exist (design 15.9, remote.md section 6): `plan` and `ask` need one, decision
  answers do not. A two-way outcome is reversible by definition, the pin still applies, and
  today a DM answer already resumes a live session without a factor. If the owner wants
  outcomes behind the factor, the existing `remote.pending` and `confirm` path can carry it
  in a follow-up.
- **Remote Control half.** Answers given in the planner session (the Remote Control window)
  are recorded by #354's `wuwei decide` and session allowance, which follows design 5.2
  ("the owner answers questions in the session, in the DM, or y/N at a terminal") for every
  decision under `observe` and `guarded`. This issue does not narrow that to two-way.
  Raised, not resolved: the issue says "one-way decisions keep the host confirmation"; for
  the DM that holds here, for the planner session it is #354's and design 5.2's call.
- **Before and after #354.** Build after #354 merges when possible. On `main` without it,
  the one-way DM line names `decision outcome D-n X` and the outcome writer takes a
  `confirm` override; after #354 the line names `decide D-n X`, the writer records
  `in the owner DM` through #354's `owner_record`, and the setup slack confirmation is
  #354's y/N. plan.md lists each swap.
- **DM channel id is typed.** Finding the DM channel from the token alone needs
  `conversations.list` with `im:read`, a scope the documented app does not have. Setup slack
  asks for the `D...` id once (it is not a secret) and keeps the four documented scopes.
- **One confirmation for the pin.** "Pins its sender on y/N" is the existing config edit
  confirmation, whose summary shows the `control_plane.owner` line with the sender id; no
  second prompt.
- **Exit code.** `setup slack` returns the highest of its steps and `config check`, so host
  protection findings still show as exit 1; the step lines say the Slack part is done.
- **Communication tools.** The owner asked for a multi-select of every tool the team uses
  plus the one WUWEI should use. Only the latter changes a setting, and a widget holds four
  choices, so the question is single-select over the tool WUWEI should use, with Slack,
  Microsoft Teams, Discord and None as choices and any other tool as free text. The answer
  is kept in `interview.json`, which is the backlog evidence. Multi-select waits for a
  second chat adapter.
- **Backlog link.** No separate integrations issue for Teams, Discord, email, Jira or GitHub
  Issues exists yet; #370 (GitLab, which lists these as follow-ups) is the linked backlog
  issue, `https://github.com/taoq-ai/wuwei/issues/370`.
- **Code host.** "Detected from the remote" stays detection: discovery adds one line for a
  non-GitHub remote; no question is asked and no adapter is proposed (that is #370).
- `control_plane.py` and `listen.py`, named in the issue's scope, need no change: the
  listener reaches every DM answer through `remote.handle`, and `poll_replies` has no
  production caller.
- The pipeline named no dry-run workspace; the reproduction above used a scratch workspace
  built from the `tests/test_remote.py` fixtures.
