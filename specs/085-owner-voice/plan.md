# Implementation Plan: Owner voice

Use the existing CLI registry, chat/code-host adapter ports, promotion path, protect-state guard and outward lint. Add a read-only sent-message chat operation, a thin `voice learn` command and one small profile parser. Keep raw adapter responses in memory; write only redacted owner messages after all reads succeed. Validate profile rules at lint time. Runtime remains Python 3.11 standard library only. Tests run before implementation and cover failures, security boundaries and promotion.

Ship an empty workspace voice template so the owner can edit the profile without repository exemplars.
