# Fixture payloads

Hook payloads that tests/test_hook.py replays through `hook.handle`. None is captured hook stdin.
Their `~/.claude/projects` paths point at tests/fixtures/transcripts, which the replay lays out under
the test's projects folder: rows of a real session transcript with the question, answer, brief and
local paths replaced (specs/hook-transcript/fixtures.py builds them).
A green replay shows the hook handles these files; it proves nothing about a real harness shape
that differs from them. Replace a file with a captured payload when one exists, and change its
provenance line.

Each file has one provenance line, `- <file>: transcript | reconstructed: <source>`:

- transcript: `tool_input` and `tool_response` come from a real launch in a Claude Code session
  transcript (the assistant `tool_use` input and the `toolUseResult` row), with the prompt, output
  path and session id replaced. The hook envelope (`session_id`, `transcript_path`, `cwd`,
  `permission_mode`, `hook_event_name`, `tool_use_id`) follows the documented hook fields.
- reconstructed: written by hand from the source named; no real payload of this shape was recorded.

## Provenance

- claude-agent-pre-accepted.json: transcript: the Agent `tool_use` input of a sentinel-security launch on 2026-10-16
- claude-agent-post-accepted.json: transcript: that launch's `toolUseResult` (status async_launched, agentId)
- claude-agent-post-model-effort.json: transcript: the Agent `tool_use` input of a sentinel-goal launch on 2026-10-18 that passed `model` and `effort`, and its `toolUseResult` with `resolvedModel`
- claude-agent-pre-rejected.json: reconstructed: the accepted PreToolUse with an unknown subagent_type
- claude-agent-post-rejected.json: reconstructed: a string error response, the form tests/test_hook.py already uses; Claude Code may send a failed launch to PostToolUseFailure instead
- codex-spawn-agent-post.json: reconstructed: the shape tests/test_codex.py uses, which is the shape hook.codex parses; not checked against a real Codex payload
- claude-subagent-pre-tool.json: reconstructed: the documented PreToolUse fields plus agent_id and agent_type, as traces with an agent field show the hook receives them; the command is a 2026-10-16 trace target
- claude-subagent-stop.json: reconstructed: the documented SubagentStop fields and the agent id of a seat.stopped ledger row; no transcript fixture holds its launch, so it replays as a forged stop
- claude-ask-post.json: transcript: the AskUserQuestion `tool_use` input and `toolUseResult` of a plan question in a Claude Code session on 2026-10-19 (tests/fixtures/transcripts/ask-flow.jsonl), with the question and answer replaced by an owner review
- claude-seat-stop.json: reconstructed: the documented SubagentStop fields with the agent id, type and transcript layout of a builder launch on 2026-10-19 (tests/fixtures/transcripts/agent-launch.jsonl and its meta file); the message is written by hand
