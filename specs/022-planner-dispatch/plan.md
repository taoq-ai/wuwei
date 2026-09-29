# Implementation plan: Planner dispatch and receive

Use stdlib Python 3.11 and existing state, verdict, brief, workspace and port helpers. Add a small planner core and CLI command. The core reads state and returns actions; receive lints a verdict file, checks its HEAD and records it in the reserved `gate_verdicts` state field. Existing brief and launch guards enforce worktree cleanliness, CAP and live builder exclusion at launch. The pre-PR guard and merge policy read the recorded initial verdicts and required deltas. Tests exercise decision branches in process and one CLI path. No runtime dependency or agent launch in tests.

Constitution: test first, atomic state writes, exit 0/1/2, no subprocess in core, no hard-coded workspace or repo names.
