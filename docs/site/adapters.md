# Adapters and ports

The CLI core asks named ports for plain data. Modules under `adapters/` implement those ports; external tools run there, not in core. Configure them in `.wuwei/config.toml` under `[adapters]`. An adapter result uses 0 clean, 1 findings, 2 could not run. A `none` adapter reports unmeasured when a measurement is required.

| Port | Shipped implementations | Default |
| --- | --- | --- |
| tracker | none, linear, jira, github | none |
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
`.wuwei/.gitignore`. Never put credentials in tracked configuration. Edit the file yourself;
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
adapters, including defaults. It names each requirement and reports `set`,
`missing` or `malformed (<why>)`, never values. A token is malformed when it contains
whitespace, as a pasted command such as `gh auth token` does. It is also malformed when it
looks like a path (starts with `/`, `~`, `./` or `../`) or a command (`$`, `|`, `;`, a quote
and other shell characters). URLs, emails, sites and channel ids are not checked. An adapter refuses
a malformed token before any request, with `<NAME> is malformed (<why>)`, and doctor carries
the same line, for example `GITHUB_TRACKER_TOKEN: malformed (contains whitespace)`. Exit 1 means a required credential is missing or malformed; exit 2
means a check could not run. Presence checks do not verify remote token validity. An HTTP
adapter that the provider refuses reports the status and a hint, for example
`github.backlog: could not run: HTTP 401: credential rejected (wrong, expired or revoked token)`.
`HTTP 403` means no access (scopes, SSO authorization or a rate limit). `HTTP 404` means
not found or not visible to the credential. `HTTP 429` is a rate limit and `HTTP 5xx` a
provider error. The provider's response text is never shown.
An `Owner:` line reports `owner.name: set` or `owner.name: not set`; it does not change
the exit code.

| Adapter | Required credential or configuration |
| --- | --- |
| code_host.github | `gh auth status --hostname github.com` must succeed. Authenticate gh separately or supply `GH_TOKEN` or `GITHUB_TOKEN`. WUWEI captures and discards gh's account output. A write-scoped `GH_TOKEN` or `GITHUB_TOKEN` in `.wuwei/env` or the environment is readable by seats, and `wuwei config check` reports it. |
| tracker.linear | `LINEAR_API_KEY` |
| tracker.jira | `JIRA_SITE` (an `https://` origin, kept from seats but not redacted), `JIRA_EMAIL` and `JIRA_API_TOKEN`; `tracker.project` names the project key |
| tracker.github | `GITHUB_TRACKER_TOKEN`, a fine-grained token for issues and projects only, or your gh login with `tracker.auth = "gh"` ([below](#github-tracker-through-your-gh-login)); `tracker.project` names `owner/repo` (else the first repository) and optional `tracker.board` names a Projects board as `owner/number` |
| chat.slack | `SLACK_BOT_TOKEN` or `SLACK_USER_TOKEN`, plus `SLACK_OWNER_DM_CHANNEL`. With `chat.identity = "custom_app"`, `SLACK_BOT_TOKEN` is required. Optional `SLACK_API_BASE` overrides `https://slack.com/api/` (https, or http to a loopback host). |
| inbound.slack | `SLACK_BOT_TOKEN` or `SLACK_USER_TOKEN`, plus `SLACK_OWNER_DM_CHANNEL`. Mentions in work and external channels need your Slack user id in `owner.handles`. Commands from your owner DM need `control_plane.owner`; `plan` and `ask` with a code need `WUWEI_TOTP_SECRET`. Optional `SLACK_API_BASE` as for chat.slack. |
| review_bot.greptile | `GREPTILE_API_KEY` |
| calendar.ics | `WUWEI_CALENDAR_URL`, a private HTTPS feed URL |
| docs.notion | `NOTION_TOKEN`, a Notion integration token with access to `docs.space` |
| docs.confluence | `CONFLUENCE_EMAIL` and `CONFLUENCE_API_TOKEN`, an Atlassian account email and API token |
| docs.markdown | No credential; pages are files under `docs.root` in the item's worktree |
| runtime.codex | `codex.command`, a nonempty command array in config.toml; credentials for the companion are managed by that tool |
| runtime.claude | No WUWEI credential variable; authenticate the Claude CLI separately |
| scanner.ziran | No WUWEI credential variable; install and configure ZIRAN separately |
| vcs.git, host.local, checks.local, tts.say | No WUWEI credential variables |
| Any none adapter | No credentials; measurements remain unmeasured |

The existing `calendar.url` setting remains a runtime fallback for older
workspaces; move private URLs into `WUWEI_CALENDAR_URL` for configuration readiness.

### GitHub tracker through your gh login

A fine-grained token is made only in the GitHub web UI. If you already work with gh signed
in, `bin/wuwei config set tracker.auth '"gh"'` lets `tracker.github` run the same GraphQL
through `gh api graphql --hostname github.com --input -`, the login `code_host.github`
already uses (`gh auth: set` in `config check`). A set `GITHUB_TRACKER_TOKEN`
is used first, whatever `tracker.auth` says; gh runs only when the token is unset. `config check` prints
`tracker.github: gh login (tracker.auth = "gh"; GITHUB_TRACKER_TOKEN not set)` and needs no
token; doctor's tracker row reads the backlog through gh and names `gh auth status` when it
fails. A gh failure reports its exit, the HTTP status when gh printed one and a hint, never
gh's own text. With `tracker.board`, the Status write needs the `project` scope, which a
default gh login lacks: run `gh auth refresh -s project`.

The trade-off: the token is scoped to issues and projects; your gh login is broad (classic
scopes such as `repo` and `workflow`). With the opt-in, the tracker path gives up least
privilege: a defect in the adapter would act with your whole gh login. How seats reach it is
unchanged. Tracker operations run only through `bin/wuwei` (`tracker create`, `tracker log`,
the watch, discovery, doctor) and the outward policy, as with the token. The
opt-in adds nothing to `.wuwei/env` or to a seat's environment. gh keeps its login in its own
store, which any process running as you can already reach, so that store is not a boundary
either way ([threat model](security.md#threat-model-91)). It does not change the seat credential rule:
keep a write-scoped `GH_TOKEN` or `GITHUB_TOKEN` out of `.wuwei/env` and the environment seats
inherit (`config check` reports one); gh then uses its own stored login. Only you can set
`tracker.auth = "gh"`: `config set` from a session needs your answer on a card, and seats cannot write
`config.toml`. Keep the default `tracker.auth = "token"` in a workspace under the `strict`
posture or with shared credentials, and wherever more than you can run commands as your user.
