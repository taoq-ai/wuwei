# Hook contract

A detected tool invocation of wuwei hook returns code 2 with the hook-specific
reason. Under enforce the full PreToolUse pipeline returns code 2 and
hookSpecificOutput.permissionDecision = deny, recording the refusal normally.
The existing protection floor also keeps this refusal with enforce off.
Other unsupported shell input retains existing allow/log policy. Legitimate
configured hook CLI invocations continue accepting recorded event payloads.
