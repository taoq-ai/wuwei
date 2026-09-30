---
layout: default
---

# Remote operation

[Home](index.html)

This page sets up running a day from your phone: Claude Code Remote Control first, then
optionally the Slack listener and the owner DM. Every step runs on the always-on host
that holds the workspace.

## 1. Remote Control, no setup

Remote Control needs no WUWEI setup. Start the planner session with
`claude --remote-control`, or run `/remote-control` inside it; "Enable Remote Control for
all sessions" in `/config` connects every interactive session. The session keeps running
on the host and the Claude mobile app or claude.ai/code is a window into it.

- Plans: Pro, Max, Team and Enterprise; API keys are not supported. On Team and
  Enterprise an organisation Owner must first enable Remote Control in the Claude Code
  admin settings. Zero Data Retention organisations cannot enable it.
- Turn on "Push when actions required" in `/config` (and optionally "Push when Claude
  decides"), and allow notifications for the Claude mobile app. Pushes are skipped while
  you are active in the connected terminal.
- Questions and permission prompts stay open until you answer them from any connected
  device.
- The host must stay on with the `claude` process running. It reconnects after sleep or
  a network drop and needs outbound HTTPS only. A small always-on machine running the
  workspace session is the recommended host; a cloud session frees the laptop but cannot
  read the local workspace.

Not relied on: a guaranteed proactive push, and Remote Control for headless `claude -p`
runs. Sessions started from the Slack DM (section 6) are headless, so they are not
reachable through Remote Control; their questions come to the DM as decisions.

A phone answer is not yet your outcome; see section 7.

## 2. The Slack app

The rest of this page is optional. Set both Slack adapters in `.wuwei/config.toml`; the
listener answers through the chat adapter, so remote operation replaces the
`chat = "none"` the [daily path](daily.html) suggests for a solo owner. With
`shepherd.min_reviewers = 0` the channel-post obligation stays not applicable.

```toml
[adapters]
inbound = "slack"
chat = "slack"
```

Create a Slack app for your Slack workspace and install it to get a bot token. The Slack
adapters call two Web API methods only:

| Method | Used for | Bot scope |
| --- | --- | --- |
| `conversations.history` | reading the owner DM | `im:history` |
| `conversations.history` | reading mentions in public channels | `channels:history` |
| `conversations.history` | reading mentions in private channels | `groups:history` |
| `chat.postMessage` | sending replies to the owner DM | `chat:write` |

Add the scopes under OAuth & Permissions, Bot Token Scopes. In the app settings, open App
Home and turn on the Messages Tab with 'Allow users to send Slash commands and messages
from the messages tab', or Slack will not let you message the app.

The owner DM is the direct message between you and the app. Its channel id starts with
`D` (placeholder `D0123ABC`) and is shown in the conversation's details or link. To have
mentions read, add the app to each channel in `outbound.work_channels` and
`outbound.external_channels` and put your Slack user id in `owner.handles`. Mentions are
stored in the inbox and wake the planner; nothing answers them from the phone.

Put the credentials in `.wuwei/env` on the host (created `0600` by init; edit it
yourself, agents cannot):

```text
SLACK_BOT_TOKEN=<bot token>
SLACK_OWNER_DM_CHANNEL=D0123ABC
```

Leave `SLACK_USER_TOKEN` unset on this host. When it is set, the adapters read and reply
with it instead of the bot token, so replies appear as you.

Run `bin/wuwei config check`. Each Slack line under Credentials must have a `set`:

```text
  chat.slack: SLACK_BOT_TOKEN: set, SLACK_USER_TOKEN: missing (one required)
  chat.slack: SLACK_OWNER_DM_CHANNEL: set
  inbound.slack: SLACK_BOT_TOKEN: set, SLACK_USER_TOKEN: missing (one required)
  inbound.slack: SLACK_OWNER_DM_CHANNEL: set
```

It checks presence only, not whether the token works.

## 3. Pin your identity

Only the sender pinned in `control_plane.owner = "T0123ABC/U0123ABC"` (your Slack team id,
a slash, your user id) can command. There is one owner per workspace.

Find both ids without pasting a token anywhere: leave the pin empty, send any message
in the owner DM, and run `bin/wuwei listen --once` on the host after section 5's setup
(the listener need not be installed). The output contains:

```text
listen remote unmeasured: control_plane.owner must pin <team>/<user>; this message came from T0123ABC/U0123ABC
```

and the DM answers "That command could not run; see the listener log on the host."
Under launchd the same line lands in `.wuwei/listen.stdout.log`. Copy the pair into the
pin. Cross-check the user id with "Copy member ID" on your Slack profile.

With the pin set:

- Messages from other users are ignored; a `remote.ignored` event records each sender
  once a day.
- Your user id with a different or missing team id is refused. The DM answers
  "Refused: this sender does not match the pinned identity. Confirm it on the host." and
  a `remote.refused` event pages on the host. Editing the pin on the host is the
  re-confirmation. `stop all` is still accepted.

## 4. The second factor

`plan` and `ask` need a second factor: a current TOTP code at the end of the message, or
a `confirm` reply within 2 minutes. Generate a secret on the host:

```sh
python3 -c "import base64, secrets; print(base64.b32encode(secrets.token_bytes(20)).decode())"
```

Add it to `.wuwei/env` as `WUWEI_TOTP_SECRET=<printed value>`. Load it into an
authenticator app by manual key entry (time based, SHA1, 6 digits, 30 seconds), or
encode this URI as a QR code with a tool on the host:

```text
otpauth://totp/WUWEI:owner?secret=<printed value>&issuer=WUWEI&algorithm=SHA1&digits=6&period=30
```

Never paste the secret or the URI into a website.

The code must reach the listener within 2 minutes of the message, and each code works
once. The secret is readable by any process running as you on the host (design 9.1): it
guards against a stranger in the DM or a stolen Slack session, not against your own
user. Without `WUWEI_TOTP_SECRET`, `confirm` is the only factor.

## 5. Install the listener

Optional settings in `.wuwei/config.toml`, defaults shown:

```toml
[listen]
poll_seconds = 60
dead_seconds = 300

[responder]
enabled = true
```

Run `bin/wuwei listen install --dry-run` to see the unit, then `bin/wuwei listen install`
from a shell where `claude` is on `PATH` and signed in: the unit records the current
`PATH`, and `plan` and `ask` run `claude` from it. One listener per workspace, labelled
`wuwei-listen-<hash>`.

- macOS: a launchd agent that runs while you are logged in. Logs go to
  `.wuwei/listen.stdout.log` and `.wuwei/listen.stderr.log`.
- Linux: a systemd user unit; logs are in the user journal
  (`journalctl --user -u wuwei-listen-<hash>`). On a host without a login session, run
  `loginctl enable-linger` so the unit keeps running.

The listener reads `.wuwei/env` once at start: after editing it, run
`bin/wuwei listen uninstall` and `bin/wuwei listen install` again. Edits to `config.toml`
apply at the next poll. More detail is in
[running the listener](configuration.html#running-the-listener).

The listener writes a `listen: clock` line every two minutes. Session start reports
`listen dead` when today's latest clock line is older than `listen.dead_seconds`, or when
the listener is installed and wrote none today.

Kill switches, strongest last:

1. `stop all` from the DM (section 6) stops remote sessions.
2. `responder.enabled = false` in `config.toml` takes effect at the next poll: messages
   are still stored, no command is handled and the planner is not woken. Stored commands
   are handled once it is back on.
3. `bin/wuwei listen uninstall` in a host terminal stops polling. Agent tools cannot run it.

## 6. Commands from the DM

Only top-level messages in the owner DM are commands, each handled once, in order. Answer
as a new message, not in a thread. Every reply passes the security check and the outward
lint and is sent, not drafted. The command list the DM sends back:

```text
Commands: plan, status, report, ask <question>, stop <session>, stop all. Decisions: approve D-n, option X on D-n, drop it.
```

One exchange per command (you, then the DM):

```text
status
pages 0 | nudges 1 | implement 1/1 | sessions 1 | meeting unmeasured

report
Report 2026-09-30: merged 1, open 0, parked 0, decisions answered 2.

plan
Reply confirm within 2 minutes to run it, or send it again ending with a current code.
confirm
Session 1a2b3c4d: turn ended, 1 decisions waiting.

plan today 123456
Session 1a2b3c4d: turn ended, 1 decisions waiting.

ask which PRs are waiting on review 123456
<the answer>
Session 1a2b3c4d: turn ended, 0 decisions waiting.

stop 1a2b3c4d
Stopped 1 sessions.

stop all
Stopped 2 sessions.

confirm
Nothing to confirm from the last 2 minutes.

deploy now
Commands: plan, status, report, ask <question>, stop <session>, stop all. Decisions: approve D-n, option X on D-n, drop it.
```

With `control_plane.content = "none"`, `status`, `report` and the answer to `ask` arrive as
"An update is waiting in the workspace." Decisions a turn raises arrive before its
`Session` line (section 7). A sender that fails the pin (section 3) gets
"Refused: this sender does not match the pinned identity. Confirm it on the host."
`stop` takes effect between turns and a stopped session is never resumed; `stop`,
`status`, `report` and decision replies need no factor.

`plan` and `ask` start headless `claude -p` sessions with the role's tools only (`ask`
is read-only). A refused tool arrives as a decision; granting it stays a host change. No
session starts while free memory is below `host.free_memory_mb`. `bin/wuwei sessions`
on the host lists them with role `remote`.

## 7. Decisions on the phone

Remote Control path: the planner asks each decision as a question. With "Push when
actions required" it reaches the phone and stays open until you answer.

DM path, for decisions a `plan` session raises. With `control_plane.content = "summary"`:

```text
D-3: <one-line question>
A: <option>
B: <option>
Not recorded. Reply approve D-n, option X on D-n, or drop it.
```

With `control_plane.content = "none"`:

```text
D-3 options: A, B
Not recorded. Reply approve D-n, option X on D-n, or drop it.
```

A question the outward lint refuses arrives as "D-3 is waiting in the workspace."

Reply with `approve D-3` (takes the recommendation), `option B on D-3`, or `drop it`
(only when exactly one decision is pending; takes its Do nothing or Defer option).
Anything else gets the command list. Replies need no factor.

The reply is recorded as a `decision.replied` event: evidence, not your outcome. If the
`plan` session that raised the decision is live, it resumes with "Decision D-3: option B.";
otherwise the DM answers:

```text
Recorded D-3 option B. Confirm it on the host.
```

Either way, record the outcome in a host terminal with `bin/wuwei decision outcome D-3 B`;
until then nudges and the report list it as pending. Drafts are the same:
`bin/wuwei drafts approve <id>` or `bin/wuwei drafts drop <id>`. Agent tools are refused
these commands, and `decision outcome` and `drafts approve` also read a typed digest from
the terminal, so they run neither through Remote Control nor the DM; from a phone,
use your own remote shell to the host, for example SSH. See
[host terminal actions](reference.html#host-terminal-actions).

## 8. Limits

- One owner per workspace: one pinned sender.
- TOTP replay protection resets at midnight: used codes are read from today's events
  only, so a code accepted in the last minute of a day can be replayed in the first
  minute of the next.
- Slack DM only: no Signal, no WhatsApp, and no responder drafting replies to people.
- `run <routine>` and `cloud <repo> <task>` answer "Not available in this version.
  Commands: plan, status, report, ask <question>, stop <session>, stop all. Decisions:
  approve D-n, option X on D-n, drop it." There are no routines, no cloud sessions, no
  budget governor, no owner quiet hours and no external dead-man ping. `listen dead` at
  session start is the only liveness signal, and it is seen only on the host.
- Thread replies are not read, and a turn blocks the listener poll while it runs.
