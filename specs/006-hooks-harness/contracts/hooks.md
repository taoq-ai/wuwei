# Hook and guard contracts

`bin/wuwei hook <Event>` reads one JSON object from stdin. It requires nonempty common
strings `session_id`, `transcript_path`, `cwd`, `hook_event_name`, matching the CLI event.
Tool events require `tool_name`, object `tool_input`, and `tool_use_id`; PostToolUse also
requires `tool_response` (its shape is tool-defined). Bash requires string `command`;
Write requires `file_path` and string `content`; Edit requires `file_path`, `old_string`,
`new_string`; Agent requires `prompt`, `description`, `subagent_type`.
Stop/SubagentStop require boolean `stop_hook_active` and string `last_assistant_message`.
SubagentStop also requires `agent_id`, string `agent_type` (possibly empty), and
`agent_transcript_path`. SessionStart requires a known `source`. PreCompact requires
`trigger` and string-or-null `custom_instructions`. Additional fields are preserved.

Guard modules import `Guard` from `wuwei.guards` and expose a plain `GUARDS` list.
`Guard(event, matcher, check)` uses None for all tools or a full-match regular expression.
An optional `profile_relaxable=False` boolean preserves blocking by default. Only the
outward-text lint registration sets it true; approval tiers have a separate blocking
registration. Invalid metadata fails discovery. Checks return raw results without
applying profiles. For a relaxable finding (exit 1), the dispatcher resolves the scoped
workspace profile: strict (default) refuses, standard prints `warning: <reason>` to stderr
and allows unless another guard refuses. Exit 2 and invalid results always refuse.
Warnings append `hook.warning` with redacted reason and tool, and do not create refusal
events. Direct outward ports reuse the same library profile translation only after their
approval-tier check passes.
`check(payload)` returns `(0|1|2, message: str)`. `discover()` returns a plain list.
Private modules are ignored. A broken module fails closed. An individual throwing or
invalid-result guard contributes an error and does not prevent subsequent guards running.

Clean hooks exit 0 without output, except SessionStart messages combined in
`hookSpecificOutput` with `hookEventName: SessionStart` and `additionalContext`,
and advisory Stop context printed to stderr. SessionStart findings retain the
payload and exit 0; errors and malformed input also exit 0 with unmeasured
diagnostics in additionalContext. SessionStart never refuses.
PreToolUse refuses with exit 2 and `hookSpecificOutput` containing `hookEventName`,
`permissionDecision: deny`, `permissionDecisionReason`. Stop/SubagentStop refuse with
exit 2 and `decision: block`, `reason`. Refusal reasons are newline-joined and also sent
to stderr. PostToolUse errors use stderr and exit 2; PreCompact guard
failures use stderr and exit 1. Malformed input exits 2 except for SessionStart.
See spec assumptions for the newer PreCompact blocking behavior in the supplied reference.

`wuwei.shell.normalize(command)` returns `list[Command]` where each record has `argv`
(a list of strings), `subshell` (bool), and `env` (explicit environment assignments).
Every raw `\b(?:git|gh)\b` mention must be accounted for by an exposed git/gh command
whose argument words are literal. Unaccounted mentions or unsupported syntax raise
`ParseError` with instructions to run git or gh as a plain command; guards return exit 2.
No variables are expanded. Literal cat here-doc substitutions remain supported as git
arguments. Other here-doc bodies, redirections, comments, environment values, and unknown
commands cannot hide mentions. `echo "git push"` is an intentional false positive.

Shell analysis rejects outer-shell expansion in nested `-c` script operands, including
mixed quotes. Guarded argument variables, brace expansion, and globs fail closed.
Interpreter checks include attached, combined, repeated, and Node long eval options.
`is_opaque` also flags interpreters reading stdin or lacking a snippet and an evident
script path. Environment assignments are preserved on Command.env, never evaluated.
