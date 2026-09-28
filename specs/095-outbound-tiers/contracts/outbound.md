# Outbound tier contract

`bin/wuwei outbound tier` reads one JSON object from stdin and reports
`{"tier": "send", "exit": 0}` or `{"tier": "draft", "exit": 1}`. Invalid input,
configuration or unavailable evidence reports draft with exit 2. Nonzero results
print a redacted reason to stderr. This command never sends, creates drafts, or
records message text. Duplicate JSON fields fail closed.

Example, after configuring Cwork as an internal work channel:

```sh
printf '%s\n' '{"text":"Thanks","channel":"Cwork"}' | bin/wuwei outbound tier
```

## Shared policy

`outward.classify(text, root, config, context=None, *, kind="chat")` returns
`(0|1|2, "send"|"draft")`. Missing context drafts. CLI and `check_call` use this
function; MCP PreToolUse and decorated adapter ports use `check_call`. Tier runs
before lint, which remains mandatory for send candidates. The CLI reports the tier
alone; it is not an authorization to bypass the send-time lint checks.

`kind` is `chat`, `slack`, `tracker` or `code_host`. The CLI defaults to `chat`;
hooks take it from outward.tool_patterns and ports take it from their port kind.
Unsupported kinds draft. Custom tool patterns must select one of these kinds.

Text comes from `text`, `message`, `body`, `title` and `description`, joined with
newlines. Tracker `draft` objects are parsed one level deep: that field name does
not mean the operation saves an unsent draft. Unknown fields and structured text
fail closed. Additional metadata supported by #11 remains accepted.

Audience and destination fields:

- `channel` or `channel_id`: configured internal destination. Conflicting aliases draft.
- `recipient`: known person ID/login or company email; `recipients`: array of these.
- `recipient_org`: explicit organization evidence; external evidence always drafts.
- `channel_type`: only `channel` is eligible; DM, group and unknown types draft.
- Boolean `is_dm`, `is_external`, `is_shared`, `is_connected`, `is_client`: any true drafts.
- `ref`: `owner/repo#number` or GitHub PR URL for code-host calls. Alternatively,
  `owner`, `repo` and `pull_number`/`issue_number`. Conflicting references draft.
- `thread`: optional discussion/thread/comment ID. Technical replies use the targeted
  discussion subject; missing target evidence drafts. Adapter reply IDs may be integers.
  Chat `thread` and `thread_ts` replies draft because the chat port cannot measure
  all participants. Only top-level chat posts qualify. Tracker writes always draft.

`@handle`, Slack `<@ID>` mentions and email addresses in text count as audience.
Unknown people draft. A work channel is an internal broadcast only when no explicit
external evidence contradicts configuration. Caller-provided approval/tier/in_scope
flags are unsupported. Nested fields cannot suppress external evidence.

## Configuration

`[outbound]` defines work_channels, external_channels, company_domains,
code_host_orgs and people. Empty defaults disable auto-send. Domain and organization
matches are exact and case-insensitive. People keys are namespaced by transport:
`slack:<id>`, `github:<login>`, `email:<address>`. Unqualified keys confer no trust.
A known person's nonempty email and org must both be internal when both are present.
GitHub authors and participants require an org matching the PR's org; an email-only
entry cannot vouch for a code-host login.

```toml
[outbound]
work_channels = ["Cwork"]
external_channels = ["Cclient"]
company_domains = ["example.test"]
code_host_orgs = ["example"]
[outbound.people."github:developer"]
email = "developer@example.test"
org = "example"
[outbound.people."slack:U123"]
email = "developer@example.test"
```

The owner edits `.wuwei/config.toml` outside agent tools. The protect-state guard
protects this policy file alongside state files, including normalized shell targets.

A team PR must match a configured repos.name and allowed organization, with a known
internal author and known internal discussion participants. The existing `code_host`
pr/reviews/threads ports provide this evidence. A failed read is never treated as clean.
All PR participants are checked even when replying to one thread.

`sensitive_keywords` uses whole-word matching; `sensitive_patterns`,
`commitment_patterns` and `disagreement_patterns` are case-insensitive regular
expressions searched across normalized text. Arrays replace defaults. Defaults
cover the issue's sensitive topics, first-person commitments, deadlines and explicit
disagreement. Invalid patterns produce exit 2. No message text appears in reasons.

## Conservative language coverage

Complete acknowledgement forms: ack, acknowledged, thanks, thank you, got it, done.
Complete status forms: test/tests/build/CI followed by passed, failed, running or
is running. These accept optional terminal punctuation and known mentions.

Mechanical fixes require the complete form `fixed in <7-40 hex digits>` and a
matching resolved full commit SHA through the VCS port. Technical forms are limited
to an identifier subject followed by `is thread safe`, `uses a lock`,
`returns None/True/False`, or `raises ValueError/TypeError`. The subject must occur in
the verified PR discussion. Unknown prose, multi-part replies and uncertain scope
draft. This is a conservative lexical policy, not a semantic classifier.

Every draft-tier send is refused with `deliver as a draft for the owner to send`.
The caller can prepare a Slack draft or GitHub pending review comment for the owner.
Local approval records never authorize sending. Creating those drafts is out of scope.

## Guard scope and dependencies

The guard handles outbound MCP writes only within a discoverable workspace,
configured repository or worktree carrying the existing wuwei-workspace Git anchor.
WUWEI_WORKSPACE locates config but does not bring unrelated cwd/targets into scope.
Local repo/path/file_path targets can bring a call into scope; unsupported payload
fields still fail closed there. Native tools are irrelevant and are not shell-parsed.

#85 voice checks are absent on this base. Their shared lint integration is preserved;
voice learning and enforcement remain deferred to that issue.
