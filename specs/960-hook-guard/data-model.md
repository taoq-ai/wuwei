# Data model

No new entities. Input remains the existing PreToolUse payload with cwd, session_id,
transcript_path, tool_name and tool_input.command. Output remains the guard's
(code, reason), translated by the hook into deny and existing hook.refusal records.
Forged PostToolUse input is test data only and is never executed.
