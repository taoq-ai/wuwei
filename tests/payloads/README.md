# Hook payload provenance

Authoritative reference supplied with issue #6: `hooks-doc.md`.
Upstream reference: https://code.claude.com/docs/en/hooks . These fixtures follow the
supplied local snapshot.

- `SessionStart/recorded.json`: live recording, reformatted with neutral session and path placeholders.
- `PreToolUse/bash.json`: reference Common input fields example.
- `PreToolUse/write.json`: common envelope plus Write field-table examples.
- `PreToolUse/edit.json`: common envelope plus Edit field-table examples.
- `PreToolUse/agent.json`: common envelope plus Agent field-table examples.
- `PostToolUse/example.json`: reference PostToolUse input example.
- `SubagentStop/example.json`: reference SubagentStop input example.
- `SubagentStop/handback.json`: `example.json` without `last_assistant_message`, as a background seat's stop arrives (#473).
- `SubagentStop/handback-transcript.jsonl`: shape recorded from a background subagent transcript, neutralised: the SubagentHandback tool use and its tool result (#473).

Only SessionStart was recorded live. All other fixtures are doc-derived examples,
not live recordings. Replace them with recordings when live capture is possible.
Tests derive malformed variants and install fake guards in temporary plugin copies;
no test guard ships in the production registry.
- `SubagentStop/plain-final.json`: compatibility fixture for #937 using documented
  stop fields including agent_transcript_path and last_assistant_message. Field review inferred
  these fields from recorded behavior; tests delay the final text row. This
  is not an exact captured Claude Code desktop 2.1.295 payload.
