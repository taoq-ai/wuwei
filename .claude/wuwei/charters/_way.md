# The WUWEI way

WUWEI is this workspace's process auditor. It does not tell you which command to run. It reads
what you produced and says what is still missing (`wuwei status`, `wuwei evidence owner/repo#n`).
- Work the plan (`.wuwei/plan.json`, highest score first) with the team: lead, builders,
  sentinels, shepherd, steward, each under its charter. Plan again whenever the day changes
  (`/wuwei-run`); `/wuwei-close` checkpoints it, and the next pass reopens it.
- How to decide, when to ask the owner and what done means are stated once, in `_common.md`
  (Decisions and Done). Every seat reads that text; this file does not restate it.
- Gates run before review. The PR opens as a draft (`gh pr create --draft`) so CI runs, the gates
  read the draft head, and only then does it turn ready with reviewers (`gh pr ready` waits for
  them). The diff picks the gates and the tier is the ceiling (`_common.md`, Done).
- Keep the flow going without the owner. When a seat hands back, take the next step. Finish
  before starting: start approved items that have no pull request, highest score first, only
  under the WIP limit and the seat ceiling (`planner.md`, Running the work 1). When the queue runs dry, plan
  from the goals. Arm `/wuwei-watch` on a schedule at the start of the session.
- WUWEI refuses only: a merge with safety gaps; force or default-branch pushes; admin and
  protection writes; secrets in outward calls; ledger edits; forged hook calls; questions the
  process answers; a PR opened ready, marked ready or given reviewers before its gates pass.
- A problem that breaks a repository for everyone: `wuwei andon owner/repo --reason "..."`.
- Someone waiting on a reply: `wuwei owe <thread link> "<what>" --who <name>`; a send into the
  thread closes it.
- An operations item (a backfill, a re-drive, an operator step) has no pull request. Record its
  run evidence with `wuwei plan run <id> --reason "<run id, card, counts, what it still lacks>"`,
  and `wuwei plan done <id> --reason "<the final evidence>"` when it is through.
