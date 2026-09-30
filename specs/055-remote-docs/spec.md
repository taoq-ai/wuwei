# Feature Specification: Remote operation runbook (Remote Control, Slack listener, owner DM)

**Feature Branch**: `055-remote-docs`
**Created**: 2026-09-30
**Status**: Ready for implementation
**Input**: Issue #55, "docs: remote operation, listener and responder setup". Design
sections 15.4 to 15.7 (with 15.9 for the command vocabulary). Scoped by the orchestrator
notes to what wave G shipped: #48, #49, #50, #57, #65, #66 and #260 are on `main`.

## Root cause (read-only, in this worktree at 5ca6e51)

There is no failing behaviour to reproduce; the gap is documentary. Every piece an operator
needs exists on `main`, but no page takes an operator from nothing to a day run from the
phone:

- `docs/site/index.md:9-18` links no remote page. `docs/site/daily.md:98-102` covers Remote
  Control in five lines and says nothing about the listener or the owner DM.
- `docs/site/configuration.md:288-356` ("Running the listener", "Commands from the owner
  DM") is a correct reference, but in reference order, not setup order, and it names only
  the reading scopes (`channels:history`, `groups:history`, `im:history`, line 311). The
  listener also posts to the owner DM through `chat.postMessage`
  (`adapters/chat/slack.py:22`, reached from `remote.dm`, `cli/wuwei/remote.py:143`), which
  needs `chat:write`; no page says so.
- No page says how to find the team id and user id for `control_plane.owner`, how to
  generate `WUWEI_TOTP_SECRET` or load it into an authenticator app, or that
  `adapters.chat` must be `"slack"` for the listener to answer (`remote.dm` sends through
  `registry.load('chat', config).dm`, `cli/wuwei/remote.py:158`), while `daily.md:44` tells
  a solo owner to set `adapters.chat = "none"`.
- `adapters/chat/slack.py:21` and `:49` prefer `SLACK_USER_TOKEN` over `SLACK_BOT_TOKEN`
  for the DM send and the history read, whatever `chat.identity` says, so an operator who
  sets a user token has the listener reply as themselves. `remote.sent`
  (`cli/wuwei/remote.py:176`) keeps that from looping, but nothing tells the operator.
- The listener loads `.wuwei/env` once at process start (`cli/wuwei/__main__.py:31-36`) and
  re-reads `config.toml` every tick (`cli/wuwei/workspace.py:393-399`, memo keyed on the
  file text): an env change needs a reinstall, a config change (the kill switch) does not.
  Undocumented for the listener.
- The service captures `PATH` at install time (`cli/wuwei/commands/watch.py:59`), and the
  headless sessions call `claude` from that `PATH` (`adapters/runtime/claude.py:82`).
  Undocumented.

## User Scenarios & Testing

### User Story 1 - Operate a day from the phone using only the docs (Priority: P1)

An owner with an always-on host follows one page, in order, and then runs a day from the
phone: answers decisions through Claude Code Remote Control and, optionally, through the
Slack owner DM; sends `plan`, `status`, `report`, `ask` and `stop` from the DM; and knows
which owner actions still need a terminal on the host.

**Independent Test**: `tests/test_docs.py` checks that `docs/site/remote.md` exists with the
site front matter, is linked from `index.md` and `daily.md`, has its eight sections in
operator order, and that every Slack method, scope, `.wuwei/env` key, config key, CLI
subcommand and fixed reply the page names exists in the code on `main`.

**Acceptance Scenarios** (from the issue's Acceptance, narrowed per Assumptions):

1. Given a fresh workspace and the docs only, when the owner follows `remote.md` sections 1
   to 5, then Remote Control with "Push when actions required" is on, the Slack app has the
   four scopes the adapters need, `.wuwei/env` holds `SLACK_BOT_TOKEN`,
   `SLACK_OWNER_DM_CHANNEL` and `WUWEI_TOTP_SECRET`, `control_plane.owner` pins
   `<team id>/<user id>`, `bin/wuwei config check` reports the Slack credentials `set`, and
   `bin/wuwei listen install` has started the listener.
2. Given the listener is running, when the owner sends `status` in the DM, then the page's
   example reply shape is what arrives; when the owner sends `plan` without a code, the DM
   answers with the confirm prompt quoted on the page, and `confirm` within 2 minutes starts
   the session.
3. Given a pending decision, when it reaches the phone (as a Remote Control push of the
   planner's question, or as a DM), then the page shows what the message contains under
   `control_plane.content = "summary"` and `"none"`, how to reply (`approve D-n`,
   `option X on D-n`, `drop it`), that the reply is recorded as `decision.replied`
   evidence, and that `bin/wuwei decision outcome` on the host records the owner outcome.
4. Given anything goes wrong, when the owner sends `stop all`, sets
   `responder.enabled = false`, or runs `bin/wuwei listen uninstall` on the host, then the
   page says what each one stops and when it takes effect.
5. Given the daily path page, then its owner decisions section links the remote runbook.

### Edge Cases

- A sender with the owner's user id and another or no team id (`changed`) is refused; the
  page's refused example uses the exact `remote.CHANGED` text.
- `run <routine>` and `cloud <repo> <task>` parse but answer `remote.UNAVAILABLE`; the page
  lists them under Limits, not as commands.
- A decision question the outward lint refuses arrives as "D-n is waiting in the
  workspace." (`cli/wuwei/remote.py:340`); the page says so.
- No real token, team id, user id or channel id appears on the page: only the placeholders
  `T0123ABC`, `U0123ABC` and `D0123ABC`, the shape `configuration.md:120` already uses.

## Requirements

- **FR-001**: New page `docs/site/remote.md` with the site front matter and these sections,
  in this order: `## 1. Remote Control, no setup`, `## 2. The Slack app`,
  `## 3. Pin your identity`, `## 4. The second factor`, `## 5. Install the listener`,
  `## 6. Commands from the DM`, `## 7. Decisions on the phone`, `## 8. Limits`.
- **FR-002**: Section 1 states only what `specs/057-control-plane-default/research.md`
  verified, plus design 15.4's always-on host and cloud-session limit.
- **FR-003**: Section 2 names the two Slack Web API methods the adapters call
  (`conversations.history`, `chat.postMessage`) and derives the bot scopes from them
  (`channels:history`, `groups:history`, `im:history`, `chat:write`), plus
  `adapters.inbound = "slack"`, `adapters.chat = "slack"`, the `.wuwei/env` keys that
  `bin/wuwei config check` names, and membership of the polled channels.
- **FR-004**: Sections 3 to 8 cover the notes' items (3) to (8); every statement is
  traceable to code on `main`, and every command, key and quoted reply exists on `main`.
- **FR-005**: `docs/site/index.md` and `docs/site/daily.md` link `remote.html`.
- **FR-006**: `tests/test_docs.py` adds `remote` to the site pages and one new test that
  fails when the page drifts from the code (plan.md lists the checks).
- **FR-007**: Nothing under `cli/`, `adapters/`, `templates/`, `skills/` or `hooks/` changes.

## Success Criteria

- **SC-001**: An owner reaches a working phone setup from `remote.md` alone; the page links
  `configuration.md` for detail, never for a required step.
- **SC-002**: Renaming a vocabulary reply, a credential variable, a config key or a Slack
  method in the code fails `tests/test_docs.py`.
- **SC-003**: `python -m pytest -q` passes; the new test runs in-process.

## Assumptions

- **Wave G scope (notes, binding).** One channel, Slack DMs. Signal, WhatsApp and the
  responder are not built; the issue's bullets for them (Signal and WhatsApp onboarding,
  "optionally through Signal" in Acceptance) are left for later issues. The Acceptance's
  "optionally through Signal" is read as "optionally through the Slack owner DM".
- **Drafts and outcomes stay host actions.** `drafts approve` and `decision outcome` read a
  typed digest from `/dev/tty` (`docs/site/reference.md`, "Host terminal actions"), so
  neither can run through Remote Control or the DM, and a phone answer is evidence, not an
  outcome (#57). The Acceptance's "approves drafts ... through Remote Control" is therefore
  documented as: answer on the phone, confirm in a terminal on the host. From a phone that
  terminal is the operator's own remote shell to the host (for example SSH), which WUWEI
  neither provides nor documents beyond one sentence.
- **Bot token only for remote operation.** The page recommends `SLACK_BOT_TOKEN` and leaving
  `SLACK_USER_TOKEN` unset on the listener host, so reads and DM replies come from the app
  (its posts carry `bot_id` and are skipped on read). Guidance only; the code's user-token
  preference is left as is.
- **The owner DM is the DM between the owner and the app** (a `D...` channel id), read with
  `im:history` on the bot token. How to open it and read its id in Slack's UI is described
  generically; Slack UI labels change and are not pinned by the test.
- **Finding the ids.** The page's primary method uses WUWEI itself: with
  `control_plane.owner` empty, a DM makes the listener log
  `control_plane.owner must pin <team>/<user>; this message came from <team>/<user>`
  (`cli/wuwei/remote.py:101`, printed at `:268` as `listen remote unmeasured: ...`), so the
  operator copies the pair from the log and never pastes a token into a shell command.
  Slack's profile "Copy member ID" is mentioned to cross-check the user id.
- **TOTP secret generation** is a stdlib one-liner on the page; the test executes it
  in-process and checks it prints base32 that decodes to 20 bytes. The otpauth URI states
  SHA1, 6 digits, 30 seconds, matching `remote.totp` and `remote.code_step`. Loading it into
  an authenticator is by manual key entry or a QR code rendered locally; the page warns
  never to paste the secret or the URI into a web service.
- **Host OS guidance is limited to what the shipped units imply**: the launchd agent is
  bootstrapped into the `gui/<uid>` domain, so it runs while the owner is logged in; a
  systemd user unit on a headless Linux host needs lingering (`loginctl enable-linger`) to
  run without a login. One sentence each; no other OS tuning.
- **Placeholders.** `T0123ABC/U0123ABC` as in `configuration.md:120`, plus `D0123ABC` for
  the DM channel. Session ids in examples are shown as `1a2b3c4d`.
- **`adapters.md:25` still calls control planes "planned"**; stale since #57 and #65, but
  outside this issue's deliverable (notes: remote.md, index.md, daily.md, test). Left as is
  and reported.
- **No budget governor, routines, dead-man ping, owner quiet hours or responder** exist
  (15.8 not built); section 8 says so plainly instead of documenting config that does not
  exist.
