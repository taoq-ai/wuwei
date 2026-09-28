# Verdict and retro contracts

`bin/wuwei verdict lint FILE [--role ROLE]` prints `OK: VALUE` and exits 0, prints
ordered findings ending `REJECT: send back to the seat` and exits 1, or prints
an I/O/decoding error and exits 2. Role suffixes after the last plugin prefix and
filename tokens enable quality rows and the arch/quality/security class sweep,
using the same rule as hooks. Every verdict needs exactly one Head row
containing 7 to 40 hex characters and a Probe:, Probes: or Mutation: row.
PASS cannot carry a blocking finding. Each finding needs its own evidence.
The Codex runtime adapter (#26) calls this CLI after a seat writes its verdict.

`GUARDS` registers PostToolUse with matcher
`Write|Edit|MultiEdit|NotebookEdit|Bash` and SubagentStop with no matcher.
File tools resolve paths from cwd and check saved decisions/gate-*.md files
case-insensitively, including symlink aliases. When cwd is outside a workspace,
fall back to finding the workspace from the gate target's parent. NotebookEdit
accepts notebook_path. Inside a workspace, Bash commands containing gate-
case-insensitively lint every gate-*.md in the day's decisions directory,
matching filenames case-insensitively without extracting shell paths.
Relevant literal interpreter one-liners are also refused as opaque.

SubagentStop for any sentinel-* role after the last plugin prefix performs the
same day scan, independent of tool history. Rejections are recorded even when
stop_hook_active is true, but that retry returns 0 to avoid a stop loop.

Every file lint rejection in a workspace appends verdict.rejected with file
and reasons. Event persistence failures return 2. Unrelated calls produce no
events. The hook dispatcher translates guard refusals to hook exit 2.

Retro capture requires cwd inside a workspace or WUWEI_WORKSPACE naming its root.
SubagentStop captures only roles whose suffix after the last colon is a charter
stem under plugin charters/*.md. Other agents pass before note parsing. Relevant
payloads need cwd, agent_id, agent_type and last_assistant_message. Invalid field
types return 2. Missing notes return 1 after recording retro.gap, except when
stop_hook_active is true: the gap is recorded and the guard returns 0.

Retro parsing accepts plain or bold Blocked:, Gap: and Change: lines, each once
with a nonempty value (none is valid). Fenced or quoted examples and HTML
comments do not count. Available fields are retained on incomplete notes.

Capture writes retro/<digest>.json with agent_id, agent_type, fields, missing
and invalid lists, then appends retro.captured or retro.gap with that record
plus its workspace-relative evidence path. The digest covers agent identity
and parsed fields. Event timestamps come from the shared writer. Artifact
retries are idempotent; events record each stop attempt.

Change text remains in retro for the steward, who writes real proposals under
the #81 contract. Capture never writes proposals, charters, existing notes,
ledger or changelog.
