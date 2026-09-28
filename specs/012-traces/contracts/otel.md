# PostToolUse trace contract

The guard is Guard('PostToolUse', None, check). Every recorder result is (0, '').
It catches its own validation/storage failures, reports a safe diagnostic on stderr and
appends hook.post_tool_use_error to events.jsonl. If event storage fails too, stderr
reports that failure. Other PostToolUse guards and dispatcher failures retain exit 2.

Workspace scope is resolved before trace validation; all tools are relevant. No workspace
is a quiet return 0. Sessions in external repos or worktrees must set WUWEI_WORKSPACE to
the root containing .wuwei until a shared helper resolves configured repos and worktrees.
An invalid explicit override reports a configuration failure.

The hook requires common metadata from feature #6. The recorder additionally requires
nonempty tool_name, object tool_input, and validates optional duration_ms as a finite
nonnegative number that cannot start before the Unix epoch and optional agent_type as
a nonblank string. agent_role, parent_span_id and tool_response are ignored.

Each line is an object with resourceSpans, containing one resource and one scopeSpans
entry with one span. resource.attributes has service.name. scope.name is wuwei.
The span fields are:

| Field | Value |
| --- | --- |
| traceId | First 32 hex digits of SHA-256 of the session identifier |
| spanId | Fresh nonzero 16-hex identifier |
| parentSpanId | Empty string |
| name | Original tool name |
| startTimeUnixNano | Completion minus duration, decimal nanoseconds string |
| endTimeUnixNano | Shared clock at hook completion, decimal nanoseconds string |
| attributes | Array of key and value.stringValue objects |

Attributes: session.id, gen_ai.tool.name, gen_ai.tool.arguments (JSON object encoded
as a string), gen_ai.agent.name. Role is agent_type, then unknown.
All textual metadata is redacted too. The trace ID is derived from the original session
identifier so redaction cannot merge sessions. There is no transcript read or tool output.

Redaction recursively covers lists and dictionaries. Case-insensitive field matching
checks both raw keys and lowercase alphanumerics to cover separators and camel casing.
Credential fields include password/passwd, secret, token, api/access/private key, authorization,
cookie, credentials, pass, pwd, auth and names ending in _key or -key. Personal fields
include phone/mobile, message, body and text.
These names may appear inside compound keys. String patterns cover credential
assignments (including query parameters and serialized JSON), credential/message flags,
HTTP data/json flags, Bearer/Basic authorization, URL userinfo,
GitHub/OpenAI/Anthropic/Slack tokens, Stripe live/test keys, GitLab, Google, npm and
Hugging Face tokens, Slack webhook URLs, AWS access IDs, JWTs, private-key headers,
international phones and national phones with separators and at least nine digits.
A match replaces the whole string with [REDACTED].
Dictionary keys are also sanitized. Paths matching .env*, *.pem, *.key, *credentials*
or *secret* redact content, old_string and new_string whole. Command bodies after
git commit -m, gh pr comment -b/--body and here-doc declarations become
[BODY n chars sha256:<hex>]. The body markers replace the matched command/declaration
as well, favoring privacy over exact shell reconstruction.

Before regex matching, strings longer than 2048 characters become their redacted first
512 characters followed by [TRUNCATED n chars sha256:<hex>]. The count and digest refer
to the full original string. Regex quantifiers are bounded. Sensitive fields/files are
redacted whole regardless of size. For truncated commands, BODY describes the retained
body prefix and TRUNCATED describes the full original command. Pattern redaction remains
best effort; the durable path is the M5 redactor port. No decoding of arbitrary
base64/encrypted content is attempted; configurable redaction belongs to M5.

Sequential calls retain file append order. Concurrent calls serialize on state.lock;
lock acquisition defines append order. Start times reflect durations, so overlapping
calls may be sorted differently by consumers that sort by start time.

Short writes are reported and rolled back to the prior file size while holding the
writer lock, so a later append cannot complete a corrupt partial line. An existing
unterminated line receives a newline before the next record under that same lock.
Recorder imports are deferred until PostToolUse to keep discovery cheap for other hooks.
