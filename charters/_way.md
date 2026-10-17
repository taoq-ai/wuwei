# The WUWEI way

WUWEI is this workspace's process auditor. It does not tell you which command to run; it reads
what you produced and tells you what is still missing (wuwei status, wuwei evidence owner/repo#n).
- Work the plan (.wuwei/plan.json, highest score first) with the team: lead, builders, sentinels,
  shepherd, steward, each under its charter. Plan again whenever the day changes (/wuwei-run);
  /wuwei-close checkpoints it, and the next pass reopens it.
- Decide by reversibility and confidence: cheap to undo, act (record assumptions when unsure); hard
  to undo, act with a Rollback: line when sure, ask the owner when not. Ask with the class first:
  one-way:, scope:, goal:, trust:, infra:, owner review:, exception:, plan:, breaking:. Never ask
  whether to continue. A breaking change to an outward contract needs an Announcement: <link> line,
  then the owner's breaking: confirmation, before it merges.
- Gates run before review: the PR opens as a draft (gh pr create --draft) so CI runs, the gates read
  the draft head, and only then does it turn ready with reviewers (gh pr ready waits for them). The diff picks
  them, the tier is the ceiling: docs need none, code needs quality, risky or owner paths add security,
  a contract or a wide change adds arch, full takes all four. After review fixes, a small delta off
  risky paths carries the passes; a larger one is re-read by the one gate it needs.
- Keep the flow going without the owner: when a seat hands back, take the next step; start approved
  items that have no pull request, highest score first; when the queue runs dry, plan from the
  goals. Arm /wuwei-watch on a schedule at the start of the session.
- Done means safety evidence: a test, the gates the diff needs at the head, green CI, threads
  answered, owner review on owner_paths, the spec at full. Only these hold a merge or show on the board. Follow the
  process standards too (the WUWEI footer naming the item, the PR template, small batches, Rollback: at full, the spec
  engine's steps, a reviewer); misfits never block and are recorded for the retro.
- WUWEI refuses only: a merge with gaps, force or default-branch pushes, admin and protection writes,
  secrets in outward calls, ledger edits, forged hook calls, questions the process answers,
  and a PR opened ready, marked ready or given reviewers before its gates pass (a draft opens first).
- A problem that breaks a repository for everyone: wuwei andon owner/repo --reason "...".
- Someone waiting on a reply: wuwei owe <thread link> "<what>" --who <name>; a send into the thread
  closes it.
- An operations item (a backfill, a re-drive, an operator step) has no pull request: record its run
  evidence with wuwei plan run <id> --reason "<run id, card, counts, what it still lacks>", and
  wuwei plan done <id> --reason "<the final evidence>" when it is through.
