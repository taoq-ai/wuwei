# Adapters and ports

The CLI core asks named ports for plain data. Modules under `adapters/` implement those ports, and external tools run there, not in core. Configure them in `.wuwei/config.toml` under `[adapters]`. An adapter result uses 0 clean, 1 findings, 2 could not run. A `none` adapter reports unmeasured when a measurement is required.

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
| calendar | none, ics | none |
| transcripts | none | none |
| tts | none, say | say on macOS, else none |

The `vcs` port calls git, and `code_host.github` calls `gh`. Tracker and chat integrations need their external access and credentials. The Codex runtime uses the configured companion command and timeout. The ZIRAN scanner needs **ZIRAN 0.39.0 or newer** and checks `ziran --version` before each measurement. Older or missing versions report unmeasured (exit 2). It supports S4 audit and S2 live traces through the [JSON CLI contract](configuration.md).

The read-only VCS operation `pushed_branches(repo)` returns unique branch names from all local remote-tracking refs, excluding remote HEAD aliases. Close compares these with the item's current branch. It does not fetch or write repository state. Missing tools, malformed output and timeouts return exit 2.

## Credentials

Store credentials in `.wuwei/env`, created empty by `wuwei init` and `wuwei init --upgrade`. Keep its permissions at `0600`. WUWEI adds `/env` to `.wuwei/.gitignore`. Never put credentials in tracked configuration. Credentials come only from you, never through a session: the state guard refuses agent writes to it.

Use one `KEY=value` assignment per line. Blank lines and whole-line `#` comments are allowed. Matching single or double quotes around a value are removed. Values have surrounding whitespace trimmed and are otherwise literal: no shell execution, variable expansion or inline comments. Existing process environment values take precedence, including empty values. Malformed files, symlinks, nonregular files and unsafe permissions stop execution with exit 2. The diagnostic never prints values.

CLI commands and hooks load this file before adapters run. Loaded values are redacted from output, events, traces and refusal messages. `SLACK_OWNER_DM_CHANNEL` and `JIRA_SITE` are identifiers, so stored events keep them.

`wuwei config check` prints a credentials section for the effective adapters, defaults included. It names each requirement and reports `set`, `missing` or `malformed (<why>)`, never values. A token is malformed when it contains whitespace, as a pasted command such as `gh auth token` does. It is also malformed when it looks like a path (starts with `/`, `~`, `./` or `../`) or a command (`$`, `|`, `;`, a quote and other shell characters). URLs, emails, sites and channel ids are not checked. An adapter refuses a malformed token before any request, with `<NAME> is malformed (<why>)`. Doctor carries the same line, for example `GITHUB_TRACKER_TOKEN: malformed (contains whitespace)`.

Exit 1 means a required credential is missing or malformed. Exit 2 means a check could not run. Presence checks do not verify remote token validity. An HTTP adapter the provider refuses reports the status and a hint, for example `github.backlog: could not run: HTTP 401: credential rejected (wrong, expired or revoked token)`. `HTTP 403` means no access (scopes, SSO authorization or a rate limit). `HTTP 404` means not found or not visible to the credential. `HTTP 429` is a rate limit and `HTTP 5xx` a provider error. The provider's response text is never shown. An `Owner:` line reports `owner.name: set` or `owner.name: not set` and does not change the exit code.

| Adapter | Required credential or configuration |
| --- | --- |
| code_host.github | `gh auth status --hostname github.com` must succeed. Authenticate gh separately or supply `GH_TOKEN` or `GITHUB_TOKEN`. WUWEI discards gh's account output. Seats can read a write-scoped `GH_TOKEN` or `GITHUB_TOKEN` from `.wuwei/env` or the environment, and `wuwei config check` reports it. When gh fails, WUWEI reads `gh api user` once. A GitHub rate limit shows in doctor as `gh` waiting, rate limited until a time, never as missing auth. |
| tracker.linear | `LINEAR_API_KEY` |
| tracker.jira | `JIRA_SITE` (an `https://` origin), `JIRA_EMAIL` and `JIRA_API_TOKEN`; `tracker.project` names the project key |
| tracker.github | `GITHUB_TRACKER_TOKEN`, a fine-grained token for issues and projects only, or your gh login with `tracker.auth = "gh"` ([below](#github-tracker-through-your-gh-login)). `tracker.project` names `owner/repo` (else the first repository). Optional `tracker.board` names a Projects board as `owner/number`. |
| chat.slack | `SLACK_BOT_TOKEN` or `SLACK_USER_TOKEN`, plus `SLACK_OWNER_DM_CHANNEL`. With `chat.identity = "custom_app"`, `SLACK_BOT_TOKEN` is required. Optional `SLACK_API_BASE` overrides `https://slack.com/api/` (https, or http to a loopback host). |
| review_bot.greptile | `GREPTILE_API_KEY` |
| calendar.ics | `WUWEI_CALENDAR_URL`, a private HTTPS feed URL |
| runtime.codex | `codex.command`, a nonempty command array in config.toml; that tool manages its own credentials |
| runtime.claude | No WUWEI credential variable; authenticate the Claude CLI separately |
| scanner.ziran | No WUWEI credential variable; install and configure ZIRAN separately |
| vcs.git, host.local, checks.local, tts.say | No WUWEI credential variables |
| Any none adapter | No credentials; measurements remain unmeasured |

### GitHub tracker through your gh login

A fine-grained token is made only in the GitHub web UI. If you already work with gh signed in, `bin/wuwei config set tracker.auth '"gh"'` lets `tracker.github` use that login. It runs the same GraphQL through `gh api graphql --hostname github.com --input -`, as `code_host.github` does. A set `GITHUB_TRACKER_TOKEN` is used first, whatever `tracker.auth` says. `config check` then prints `tracker.github: gh login (tracker.auth = "gh"; GITHUB_TRACKER_TOKEN not set)` and needs no token. Doctor's tracker row reads the backlog through gh and names `gh auth status` when it fails. A gh failure reports its exit, the HTTP status when gh printed one and a hint, never gh's own text.

On either path a GraphQL error reads `GitHub error response for <owner>/<repo>#<n>: <message>`. It names the ticket when the lookup has one, and GitHub's first error message, redacted and cut at 160 characters. With `tracker.board`, the Status write needs the `project` scope, which a default gh login lacks: run `gh auth refresh -s project`.

Without a board, in review is the label named by `tracker.states.in_review`. `bin/wuwei init --upgrade` creates it, and doctor's `tracker labels` row warns while it is missing. When `pr raise` or `tracker move` finds it missing on your own tracker, it names `bin/wuwei init --upgrade` and then `bin/wuwei tracker move <item> in_review`. On a tracker WUWEI does not own, the duty stays skipped in the day report until that tracker's owner adds the label.

The trade-off: the token is scoped to issues and projects, and your gh login is broad (classic scopes such as `repo` and `workflow`). With the opt-in, the tracker path gives up least privilege. A defect in the adapter would act with your whole gh login. Tracker operations still run only through `bin/wuwei` and the outward policy. The opt-in adds nothing to `.wuwei/env` or to a seat's environment. gh keeps its login in its own store, which any process running as you can already reach ([threat model](security.md#threat-model-91)). Keep a write-scoped `GH_TOKEN` or `GITHUB_TOKEN` out of `.wuwei/env` and the environment seats inherit. Only you can set `tracker.auth = "gh"`: `config set` asks your Owner step card, and seats cannot write `config.toml`. Keep the default `tracker.auth = "token"` where shared credentials live or where more than you can run commands as your user.
