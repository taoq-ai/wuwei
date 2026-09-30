# Requirements checklist

- [X] User scenarios and acceptance come from the issue's Acceptance section.
- [X] Root cause cites file and line on main, reproduced in this worktree with a scratch
  workspace and in-process module probes.
- [X] Requirements are testable and scoped to issue #240.
- [X] Assumptions record the deviations (directory listing kept, context variable instead
  of arguments, no new reuse cache) and why.
- [X] No authorisation caching, no daemon, no new runtime dependency or file.
