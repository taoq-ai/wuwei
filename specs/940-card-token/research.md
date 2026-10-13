# Research

Decision: canonicalize only the leading generated card identity in the existing hook. Every answer consumer reads that hook's hashes, so no separate matcher is needed per command.
Rationale: exact command and token remain required, appended context becomes harmless, and historical exact hashes stay compatible.
Alternatives: a token-only match weakens command binding; a new answer store duplicates the existing event log.

Decision: extract a pure mismatch diagnostic for direct-card paths.
Rationale: next derives cards without consuming answers; calling needs_owner there could spend a Yes during a read.
