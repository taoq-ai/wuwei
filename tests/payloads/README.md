# Hook payload provenance

Authoritative reference supplied with issue #6: `hooks-doc.md`.
Upstream reference: https://code.claude.com/docs/en/hooks . These fixtures follow the
supplied local snapshot, including its newer PreCompact schema.

- `SessionStart/recorded.json`: live recording, reformatted with neutral session and path placeholders.
- `PreToolUse/bash.json`: reference Common input fields example.
- `PreToolUse/write.json`: common envelope plus Write field-table examples.
- `PreToolUse/edit.json`: common envelope plus Edit field-table examples.
- `PreToolUse/agent.json`: common envelope plus Agent field-table examples.
- `PostToolUse/example.json`: reference PostToolUse input example.
- `SubagentStop/example.json`: reference SubagentStop input example.
- `Stop/example.json`: reference Stop input example, including stop_hook_active=true.
- `PreCompact/example.json`: reference PreCompact input example.

Only SessionStart was recorded live. All other fixtures are doc-derived examples,
not live recordings. Replace them with recordings when live capture is possible.
Tests derive malformed variants and install fake guards in temporary plugin copies;
no test guard ships in the production registry.
