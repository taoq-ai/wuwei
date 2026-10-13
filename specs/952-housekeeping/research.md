# Research
Reuse watch and the host port. Only PR waits and sleep timers run in the recorded
wrapper process; one-shot commands keep their existing direct paths. PR wait reads
current workspace PRs each tick. Live waits share one purpose within a session and day,
since completion notifications wake the session that started the wait.

## Owner-authorized design reconsideration
Review demonstrated that a broad wrapper bypassed argv guards and could interrupt
state writers after their item became terminal. The owner requested narrowing the
wrapper, removing native exec and all fabricated prior-day clocks. The runtime allowlists only waits/timers; round 2 removes the partial Bash guard
unwrap and keeps a forged-hook refusal test through the real CLI.

Fast checks use ps with a C locale and skip cwd probes. Explicit checks add orphan
cwd probes, with failures attached to individual PIDs. Kill verification uses ps -p.
Unreapable identities are recorded once and listed without holding the day loop.
Prior-day seats and external cleanup are plain listings: no meaningless Yes and no
owner approval is consumed. Active worktrees and process ancestors are excluded.
