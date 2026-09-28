# Outward lint and send classification contract

`wuwei.outward.lint(text, channel, config) -> (code, message)` takes loaded workspace
configuration. It returns 0 clean, 1 finding or 2 unable to check, without profile
relaxation. No body or matched token is included in diagnostics. Consumers #85 and #95
can reuse it. Owner name words and slash/comma/space-separated pronouns are forbidden
case-insensitively at word boundaries. Optional owner.handles contains bare chat IDs and
code-host handles. Matching applies NFKD, removes Mn, Me and Cf, then casefolds.
Conventional pronoun families include possessives. Identity and internal-pattern matching
also checks a view with formatting underscores replaced by spaces.

`outward.patterns` is a list of case-insensitive regular expressions. Defaults cover
pending drafts, queues, agents, sentinel, seats, WUWEI, queued, the owner, Claude, Codex,
subagents, steward and gate verdicts. `outward.banned_characters` contains literal strings
plus the special token `emoji`; defaults are emoji, U+2014, U+2015, U+2E3A and U+2E3B.
Emoji detection includes any base character followed by U+FE0F. Bare arrows, copyright
and registered symbols remain allowed. Empty lists explicitly disable these checks.
`outward.max_length` maps channel names to positive limits.

`wuwei.outward.classify(text, root, config) -> (code, disposition)` is the shared
send-versus-draft decision for adapters and future outbound tiers (#95). It returns:

- `(0, 'send')`: the complete message is `fixed in <7-40 hex digits>` with optional period
  and surrounding whitespace, and vcs.resolve resolves the hash in a configured repository.
- `(1, 'draft')`: any other prose, an unknown hash, or no configured repositories.
- `(2, 'draft')`: invalid text or an unavailable resolution when no repository resolves it.

Classification does not replace lint. `check_call(inputs, root, config, channels)` runs
lint on extracted text, then classification. Non-mechanical messages return 1 with
"deliver as a draft for the owner to send". Standard profile prints redacted lint warnings
but still enforces the draft requirement and fails closed on errors.

The approve tier never sends. Processes with the owner's uid can forge local files and
hook payloads, so no local approval record is trusted or created. There is no approval
recorder, digest question or approval-id input. Draft delivery belongs to the chat and
code_host adapters (Slack draft, GitHub pending review comment), outside this feature.
The generic state writer retains its reserved-namespace mechanism with no reserved keys
here. Each feature adds keys it owns; #8 will reserve fast_checks. gate_verdicts remains
writable through the generic state writer.

`outward.tool_patterns` is an array of `{pattern, channel}` records. Patterns full-match
tool names case-insensitively. Defaults cover Slack send/post/reply/schedule/update,
Linear save/create/update issue/comment and GitHub add/create/update comment MCP tools.
Custom records replace defaults. Overlapping matches for different channels are errors.
An unmatched `mcp__` tool passes only when the first underscore-separated word of its
last segment is a read verb: get, list, search, read, find, fetch, query, describe, view
or lookup (case-insensitive). A service word contained in the MCP server segment may
precede that verb, as in `mcp__claude_ai_Slack__slack_read_thread`.
All other unmatched MCP tools return 2 with an outward.tool_patterns configuration hint.

The guard registers PreToolUse only. Outside a workspace it returns 0 before parsing the
tool input or policy only if WUWEI_WORKSPACE is unset. A set but invalid override returns 2,
including an empty override. Native tools skip policy parsing inside a valid workspace.
chat.post, chat.dm, tracker.create and code_host.comment invoke the same policy at the
adapter port. Missing workspaces at ports return 2 without calling the operation. Their
names are not MCP tool patterns. tracker.claim and tracker.transition carry no text.
Bash-level sends (`gh pr comment`, curl to Slack) are covered by Bash guards and the
code_host port allowlist, not this tool-name guard.

Supported text keys: `text`, `message`, `body`, `title`, `description`. All supplied text
fields are checked together in sorted field order, separated by newlines. A `draft`
object may contain the same text and metadata keys, one level deep. Metadata keys:
`ref`, `channel`, `channel_id`, `thread`, `thread_ts`, `item`, `issue`, `issue_id`, `issueId`,
`id`, `team`, `team_id`, `project`, `project_id`, `state`, `assignee`, `labels`, `owner`, `repo`.
These metadata values are strings, null, or lists of strings; channel and channel_id must
be nonblank strings. `issue_number` and `pull_number` accept strings or integers, never
booleans. Other keys and structured content return 2. At least one nonempty text field is
required. Limits apply to both the policy channel and any input channel/channel_id.
