# Implementation Plan: Remote operation runbook

**Branch**: `055-remote-docs` | **Spec**: `specs/055-remote-docs/spec.md`

## Summary

One new docs page, `docs/site/remote.md`, the operator runbook for running a day from the
phone, in the order an operator does it. Two one-line links (index, daily path). One docs
test that pins the page to the code it describes, reusing the existing site-pages test for
front matter and the index link. No runtime code changes.

## Technical Context

Markdown under `docs/site/` (Jekyll, `layout: default` front matter like every other page).
Test in `tests/test_docs.py`, stdlib plus pytest, in-process. The release build already
ships every `docs/site/*.md` (`scripts/build-release.py:15` includes `docs`), and
`test_release_asset_ships_every_linked_doc` globs `SITE/*.md`, so the new page needs no
packaging change.

## Constitution Check

- I Stdlib only: no runtime change. The TOTP one-liner on the page is stdlib
  (`base64`, `secrets`).
- III One behaviour, one test: the page's contract lives in one new test; front matter and
  the index link reuse `test_site_pages_and_links`.
- IV Test first: the test is written and seen failing (`remote.md` missing) before the page.
- V Ponytail: no new helper, no generated docs, no change to `configuration.md`
  (the page links its "Running the listener" section for detail instead of copying it).
- VII Security: the page never shows a token or a real id, warns against pasting the TOTP
  secret into a web service, and keeps drafts and outcomes as host actions.

## Sources the builder must read before writing (and verify every claim against)

- `specs/057-control-plane-default/research.md` (section 1, nothing beyond it).
- `docs/site/configuration.md` lines 83-120 (listen, responder, adapters, control_plane
  rows) and 288-398 ("Running the listener" onward).
- `docs/site/adapters.md` "Credentials"; `docs/site/reference.md` "Host terminal actions".
- `adapters/inbound/slack.py`, `adapters/chat/slack.py`, `cli/wuwei/remote.py`,
  `cli/wuwei/control_plane.py`, `cli/wuwei/listen.py`, `cli/wuwei/commands/watch.py`
  (`service`), `cli/wuwei/commands/config.py` (`requirements`), `cli/wuwei/env.py`
  (`CREDENTIALS`), `cli/wuwei/workspace.py` (`SCHEMA`, `watch_unit`),
  `templates/wuwei-watch.plist`, `templates/wuwei-watch.service`.

## Changes

### 1. New page `docs/site/remote.md`

Front matter `---\nlayout: default\n---\n`, then `# Remote operation`, `[Home](index.html)`,
and a two-sentence intro: what this page sets up (Remote Control, then optionally the Slack
listener and owner DM), and that every step runs on the always-on host. Use `bin/wuwei`
as the other pages do. Then eight sections, exactly these headings, in this order:

**`## 1. Remote Control, no setup`** (only what #57 research verified, plus design 15.4)
- Needs no WUWEI setup. Start the planner session with `claude --remote-control` (or
  `/remote-control` inside the session); `/config` "Enable Remote Control for all sessions"
  connects every interactive session. Plans: Pro, Max, Team and Enterprise; API keys are not
  supported. On Team and Enterprise an organisation Owner must first enable Remote Control
  in the Claude Code admin settings; Zero Data Retention organisations cannot.
- Turn on "Push when actions required" in `/config` (and optionally "Push when Claude
  decides"); install the Claude mobile app with notifications allowed. Pushes are skipped
  while you are active in the connected terminal.
- Questions and permission prompts stay open until answered from any connected device.
- The host must stay on with the `claude` process running; it reconnects after sleep or a
  network drop; outbound HTTPS only. Recommended host: a small always-on machine running the
  workspace session (design 15.4). Cloud sessions free the laptop but cannot read the local
  workspace.
- Not relied on: a guaranteed proactive push; Remote Control for headless `claude -p` runs
  (so sessions started from the Slack DM, section 6, are not reachable through Remote
  Control; their questions come to the DM as decisions).
- Close with: a phone answer is not yet your outcome; see section 7.

**`## 2. The Slack app`**
- Set in `.wuwei/config.toml`: `[adapters] inbound = "slack"` and `chat = "slack"` (the
  listener answers through the chat adapter; `daily.md` suggests `chat = "none"` for a
  solo owner, which remote operation replaces). With `shepherd.min_reviewers = 0` the
  channel-post obligation stays not applicable.
- A Slack app you create for the workspace, with a bot token. A table "Method | Used for |
  Bot scope": `conversations.history` reads the owner DM (`im:history`), mentions in public
  channels (`channels:history`) and private channels (`groups:history`);
  `chat.postMessage` sends replies to the owner DM (`chat:write`). State that these are the
  only two Web API methods the Slack adapters call.
- The owner DM is the direct message between you and the app; its channel id starts with
  `D` (placeholder `D0123ABC`) and is shown in the conversation's details or link. Add the
  app to each channel in `outbound.work_channels` (internal) and
  `outbound.external_channels` (client-facing) whose mentions it should read; mentions
  need your Slack user id in `owner.handles`. Internal versus external marking decides what
  may auto-send (link `configuration.md`); every DM, acknowledgement included, drafts.
- `.wuwei/env` (created `0600` by init, edited by you on the host): a `text` block with
  `SLACK_BOT_TOKEN=<bot token>` and `SLACK_OWNER_DM_CHANNEL=D0123ABC`. Leave
  `SLACK_USER_TOKEN` unset on this host: when set, the adapters read and reply with it
  instead of the bot token, so replies appear as you.
- Run `bin/wuwei config check`: the `chat.slack` and `inbound.slack` lines must read `set`.
  It checks presence only, not token validity.

**`## 3. Pin your identity`**
- `control_plane.owner = "<team id>/<user id>"`, placeholder `T0123ABC/U0123ABC`. Only this
  sender can command; one owner per workspace.
- Finding both ids without pasting a token anywhere: leave the pin empty, run
  `bin/wuwei listen --once` on the host after sending any message in the DM; the output
  contains `this message came from T0123ABC/U0123ABC` (the error `remote.sender` raises,
  printed as `listen remote unmeasured: ...`; the page quotes the output line, not the
  function), and the DM gets the `remote.FAILED` text. Under launchd the same line is in
  `.wuwei/listen.stdout.log`. Copy the pair into the pin. Cross-check the user id with your Slack profile's "Copy member ID".
- What the pin does, from `configuration.md` "Commands from the owner DM": other users are
  ignored (one `remote.ignored` event per sender per day); your user id with a different or
  missing team id is refused with `remote.CHANGED` and a `remote.refused` page on the host;
  editing the pin on the host is the re-confirmation; `stop all` is still accepted.

**`## 4. The second factor`**
- `plan` and `ask` need a factor: a current TOTP code at the end of the message, or a
  `confirm` reply within 2 minutes.
- Generate a secret on the host with exactly this one-liner (the test executes it):
  `python3 -c "import base64, secrets; print(base64.b32encode(secrets.token_bytes(20)).decode())"`
  and add `WUWEI_TOTP_SECRET=<printed value>` to `.wuwei/env`.
- Load it into an authenticator app by manual key entry (time based, SHA1, 6 digits,
  30 seconds), or as the URI
  `otpauth://totp/WUWEI:owner?secret=<printed value>&issuer=WUWEI&algorithm=SHA1&digits=6&period=30`
  rendered as a QR code on the host. Never paste the secret or the URI into a website.
- Rules from `remote.code_step`: the code must reach the listener within 2 minutes of the
  message; each code works once. The secret is readable by any process running as you on
  the host (design 9.1); it guards against a stranger in the DM or a stolen Slack session,
  not against your own user.
- Without `WUWEI_TOTP_SECRET`, `confirm` is the only factor.

**`## 5. Install the listener`**
- Optional config (defaults shown): `[listen] poll_seconds = 60`, `dead_seconds = 300`;
  `[responder] enabled = true`.
- Run `bin/wuwei listen install --dry-run` to see the unit, then `bin/wuwei listen install`
  from a shell where `claude` is on `PATH` and signed in: the unit records the current
  `PATH`, and `plan` and `ask` run `claude` from it. macOS: a launchd agent that runs while
  you are logged in; logs in `.wuwei/listen.stdout.log` and `.wuwei/listen.stderr.log`.
  Linux: a systemd user unit, logs in the user journal
  (`journalctl --user -u wuwei-listen-<hash>`); on a host without a login session enable
  lingering with `loginctl enable-linger`. One listener per workspace, labelled
  `wuwei-listen-<hash>`.
- After editing `.wuwei/env`, reinstall (`bin/wuwei listen uninstall`, then
  `bin/wuwei listen install`): the listener reads it once at start. Edits to
  `config.toml` apply at the next poll.
- Clock and dead rule: a `listen: clock` line every two minutes; session start reports
  `listen dead` when today's latest clock line is older than `listen.dead_seconds`, or the
  listener is installed and wrote none today.
- Kill switches, strongest last: `stop all` from the DM (section 6); `responder.enabled =
  false` in `config.toml` (next poll: messages are still stored, no command is handled and
  the planner is not woken; stored commands are handled once it is back on);
  `bin/wuwei listen uninstall` in a host terminal (stops polling; refused from agent tools).

**`## 6. Commands from the DM`**
- One short paragraph: top-level messages in the owner DM only, handled once, in order;
  answer as a new message, not in a thread. Every reply passes the security check and the
  outward lint and is sent, not drafted.
- A table or `text` blocks with one exchange per command. Reply text must be the code's
  literal text; placeholders only for values:
  - `status` -> the status line without its `WUWEI ` prefix, for example
    `pages 0 | nudges 1 | implement 1/1 | sessions 1 | meeting unmeasured` (shape from
    `status.line`; with `control_plane.content = "none"`: `An update is waiting in the
    workspace.`).
  - `report` -> `Report <date>: merged 1, open 0, parked 0, decisions answered 2.`
  - `plan` -> `remote.CONFIRM` verbatim; then `confirm` -> any decisions (section 7) and
    `Session 1a2b3c4d: turn ended, 1 decisions waiting.` Also show `plan 123456` (code
    form) starting at once.
  - `ask which PRs are waiting on review 123456` -> the answer text, then
    `Session 1a2b3c4d: turn ended, 0 decisions waiting.` Read-only tools only.
  - `stop 1a2b3c4d` -> `Stopped 1 sessions.`; `stop all` -> `Stopped 2 sessions.` (literal
    code text; stops between turns, a stopped session is never resumed; no factor needed).
  - Refused: an unknown message such as `deploy now` -> `remote.VOCABULARY` verbatim; a
    `changed` sender -> `remote.CHANGED` verbatim.
  - `confirm` with nothing pending -> `remote.NOTHING` verbatim.
- One sentence: `plan` and `ask` sessions are headless `claude -p` runs with the role's
  tools only; a refused tool arrives as a decision, and granting it stays a host change;
  no session starts while free memory is below `host.free_memory_mb` (`remote.LOW_MEMORY`).
  `bin/wuwei sessions` on the host lists them with role `remote`.

**`## 7. Decisions on the phone`**
- Remote Control path: the planner asks each decision as a question; with "Push when
  actions required" it reaches the phone and stays open until answered.
- DM path (a `plan` session's decisions): the message is what `control_plane.render`
  produces plus the `control_plane.HELP` line (builder's source; the page shows the text,
  not the names). Show both forms in `text` blocks:
  `content = "summary"`: `D-3: <one-line question>` / `A: <option>` / `B: <option>` /
  `Not recorded. Reply approve D-n, option X on D-n, or drop it.`;
  `content = "none"`: `D-3 options: A, B` plus the same line. A question the outward lint
  refuses arrives as `D-3 is waiting in the workspace.`
- Replies: `approve D-3` (takes the recommendation), `option B on D-3`, `drop it` (only when
  exactly one decision is pending; takes its Do nothing or Defer option). Anything else gets
  the vocabulary. No factor needed.
- Recording: the reply is a `decision.replied` event, evidence and not your outcome. If the
  `plan` session that raised the decision is live, it resumes with
  `Decision D-3: option B.`; otherwise the DM answers
  `Recorded D-3 option B. Confirm it on the host.` Either way, record the outcome in a host
  terminal with `bin/wuwei decision outcome D-3 B`; until then nudges and the report list
  it as pending. Same for drafts: `bin/wuwei drafts approve <id>` or
  `bin/wuwei drafts drop <id>`. These read a typed digest from the terminal, so they run
  neither through Remote Control nor the DM; from a phone, use your own remote shell to the
  host (for example SSH). Link `reference.html#host-terminal-actions`.

**`## 8. Limits`**
- One owner per workspace (one pinned sender).
- Replay protection resets at midnight: used TOTP steps are read from today's events only,
  so a code accepted in the last minute of a day can be replayed in the first minute of the
  next (`ponytail:` note in `remote.py`).
- Slack DM only: no Signal, no WhatsApp, no responder drafting replies to people.
- `run <routine>` and `cloud <repo> <task>` answer with the `remote.UNAVAILABLE` text
  verbatim (it starts `Not available in this version.` and repeats the vocabulary): no
  routines, no cloud sessions, no budget governor, no owner quiet hours, and no external
  dead-man ping; `listen dead` at session start is the only liveness signal, and it is
  seen only on the host.
- Thread replies are not read; a turn blocks the listener poll while it runs.

Style: no em-dashes, no emojis, no absolute local paths, no real tokens or ids. Keep the
page under about 200 lines; link `configuration.md#running-the-listener` for detail rather
than repeating it.

### 2. `docs/site/index.md`

After the "Daily path" bullet (line 9), add:
`- [Remote operation](remote.html): run a day from the phone with Remote Control and the Slack owner DM`

### 3. `docs/site/daily.md`

At the end of section 5's Remote Control paragraph (line 102), add one sentence:
`To command the workspace and answer decisions from Slack as well, follow [remote operation](remote.html).`

### 4. `tests/test_docs.py`

- `test_site_pages_and_links`: add `'remote'` to `pages` (checks the file, front matter and
  `(remote.html)` in the index).
- New `test_remote_runbook_matches_the_code`, placed after `test_daily_path_and_recovery_pages`:
  1. `page = (SITE / 'remote.md').read_text()`, `flat = ' '.join(page.split())`.
  2. `(remote.html)` in `daily.md`.
  3. The eight headings of FR-001 are present and their `page.index` values are increasing.
  4. For `conversations.history` and `chat.postMessage`: present in
     `adapters/chat/slack.py` source and backticked in the page. Each of `channels:history`,
     `groups:history`, `im:history`, `chat:write` backticked in the page.
  5. Each of `SLACK_BOT_TOKEN`, `SLACK_USER_TOKEN`, `SLACK_OWNER_DM_CHANNEL`,
     `WUWEI_TOTP_SECRET` is in `env.CREDENTIALS` and in the page.
  6. Every backticked `a.b` or `a.b = value` in the page (regex
     ``r'`([a-z_]+)\.([a-z_]+)(?: = [^`]*)?`'``) is a config key in `workspace.SCHEMA`
     (`b in SCHEMA.get(a, {})`), an event kind in `wuwei.commands.event.EVENT_PRODUCERS`
     (`decision.replied`, `remote.refused`, ...), or one of `conversations.history` and
     `config.toml`. So a renamed
     key or event kind fails, and the page must not name Python functions or constants
     such as `remote.sender` in backticks.
  7. Every `bin/wuwei <word>` names an existing `cli/wuwei/commands/<word>.py`.
  8. `remote.VOCABULARY`, `remote.CONFIRM`, `remote.CHANGED`, `remote.NOTHING`,
     `remote.UNAVAILABLE` and `control_plane.HELP` each appear in `flat` (whitespace
     joined, so wrapped lines still match).
  9. Phrases in `flat`: `Push when actions required`, `organisation Owner`,
     `Recorded D-3 option B. Confirm it on the host.`, `decision.replied`,
     `decision outcome`, `drafts approve`, `listen install`, `listen uninstall`,
     `listen dead`, `responder.enabled = false`, `stop all`, `loginctl enable-linger`,
     `resets at midnight`, `otpauth://totp/`, `algorithm=SHA1&digits=6&period=30`.
  10. The one-liner: `code = re.search(r'python3 -c "([^"]+)"', page)[1]`; run it with
      `exec` under `contextlib.redirect_stdout(io.StringIO())`; the output, stripped,
      `base64.b32decode`s to 20 bytes.
  11. Hygiene: no `xox` token prefix followed by `-`; every Slack-shaped id
      (``re.findall(r'\b[CDTUW][A-Z0-9]{6,}\b', page)`` containing a digit) is one of
      `T0123ABC`, `U0123ABC`, `D0123ABC`; no `\N{EM DASH}`. Absolute paths are left to `tests/test_hygiene.py`, which flags a literal home prefix in the test itself.
  Imports local to the test (`base64`, `contextlib`, `io`, and `control_plane`, `env`,
  `remote`, `workspace` from `wuwei`).

## Must not change

Everything under `cli/`, `adapters/`, `templates/`, `skills/`, `hooks/`, `agents/`;
`docs/site/configuration.md`, `adapters.md`, `reference.md`, `concepts.md`; the design spec;
existing tests other than the one-word addition to `pages`. If writing the page exposes a
code bug, report it; do not fix it here.
