# Adapters and ports

The CLI core asks named ports for plain data. Modules under `adapters/` implement those ports; external tools run there, not in core. Configure them in `.wuwei/config.toml` under `[adapters]`. An adapter result uses 0 clean, 1 findings, 2 could not run. A `none` adapter reports unmeasured when a measurement is required.

| Port | Shipped implementations | Default |
| --- | --- | --- |
| tracker | none, linear | none |
| chat | none, slack | none |
| review_bot | none, greptile | none |
| runtime | none, claude, codex | claude |
| scanner | none, ziran | none |
| code_host | none, github | github |
| vcs | git | git |
| host | none, local | local |
| checks | none, local | local |
| inbound | none, slack | none |
| redactor | builtin | builtin |

The `vcs` port calls git; `code_host.github` calls `gh`. Tracker and chat integrations require their external access and credentials. The Codex runtime uses the configured companion command and timeout. The ZIRAN scanner requires **ZIRAN 0.39.0 or newer** and checks `ziran --version` before each measurement. Older or unavailable versions report unmeasured (exit 2). It supports S4 audit and S2 live traces through the [JSON CLI contract](configuration.md). S3 MCP registry checks run at init, upgrade and morning planning; they preserve snapshots and block launches on findings or incomplete measurement. Inbound text passes through the redactor port, which replaces phone numbers, email addresses and secrets, before it is stored in `.wuwei/inbox/inbox.jsonl`. The control plane is configured under `[control_plane]` (`content`, `owner`) and sends its replies through the chat adapter; see [Remote operation](remote.md).

The read-only VCS operation `pushed_branches(repo)` returns unique branch names
from all local remote-tracking refs, excluding remote HEAD aliases. Close compares
these with the item's current branch. It does not fetch or write repository state;
missing tools, malformed output and timeouts return exit 2.

## Credentials

Store credentials in `.wuwei/env`, created empty by `wuwei init` and
`wuwei init --upgrade`. Keep its permissions at `0600`; WUWEI adds `/env` to
`.wuwei/.gitignore`. Never put credentials in tracked configuration. Edit the file as the owner;
the existing state guard refuses agent writes to it.

Use one `KEY=value` assignment per line. Blank lines and whole-line `#` comments
are allowed. Matching single or double quotes around a value are removed; values
have surrounding whitespace trimmed and are otherwise literal, with no shell execution, variable expansion or inline
comment processing. Existing process environment values take precedence, including
empty values. Malformed files, symlinks, nonregular files and unsafe permissions
stop execution with exit 2 and a diagnostic that does not print values.

CLI commands, hooks and the watch service load this file before adapters run.
The watch plist and systemd unit invoke the same CLI; credentials are not copied
into service definitions. Restart the watch after changing credentials.
Loaded values are redacted from output, events, traces and refusal messages, except
`SLACK_OWNER_DM_CHANNEL`: a channel id is an identifier the listener must match in stored events.

`wuwei config check` prints a credentials section for the effective configured
adapters, including defaults. It names each requirement and reports `set` or
`missing`, never values. Exit 1 means a required credential is missing; exit 2
means a check could not run. Presence checks do not verify remote token validity.
An `Owner:` line reports `owner.name: set` or `owner.name: not set`; it does not change
the exit code.

| Adapter | Required credential or configuration |
| --- | --- |
| code_host.github | `gh auth status --hostname github.com` must succeed. Authenticate gh separately or supply `GH_TOKEN` or `GITHUB_TOKEN`. WUWEI captures and discards gh's account output. A write-scoped `GH_TOKEN` or `GITHUB_TOKEN` in `.wuwei/env` or the environment is readable by seats, and `wuwei config check` reports it. |
| tracker.linear | `LINEAR_API_KEY` |
| chat.slack | `SLACK_BOT_TOKEN` or `SLACK_USER_TOKEN`, plus `SLACK_OWNER_DM_CHANNEL`. With `chat.identity = "custom_app"`, `SLACK_BOT_TOKEN` is required. Optional `SLACK_API_BASE` overrides `https://slack.com/api/` (https, or http to a loopback host). |
| inbound.slack | `SLACK_BOT_TOKEN` or `SLACK_USER_TOKEN`, plus `SLACK_OWNER_DM_CHANNEL`. Mentions in work and external channels need your Slack user id in `owner.handles`. Commands from the owner DM need `control_plane.owner`; `plan` and `ask` with a code need `WUWEI_TOTP_SECRET`. Optional `SLACK_API_BASE` as for chat.slack. |
| review_bot.greptile | `GREPTILE_API_KEY` |
| calendar.ics | `WUWEI_CALENDAR_URL`, a private HTTPS feed URL |
| runtime.codex | `codex.command`, a nonempty command array in config.toml; credentials for the companion are managed by that tool |
| runtime.claude | No WUWEI credential variable; authenticate the Claude CLI separately |
| scanner.ziran | No WUWEI credential variable; install and configure ZIRAN separately |
| vcs.git, host.local, checks.local, tts.say | No WUWEI credential variables |
| Any none adapter | No credentials; measurements remain unmeasured |

The existing `calendar.url` setting remains a runtime fallback for older
workspaces; move private URLs into `WUWEI_CALENDAR_URL` for configuration readiness.
