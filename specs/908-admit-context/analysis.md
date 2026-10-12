# Specification Analysis Report: 908-admit-context

| ID | Severity | Summary | Resolution |
|----|----------|---------|------------|
| A1 | HIGH | `_owner_prs` silently dropped PRs: ids from the short repository name collided across owners and the `taken` check skipped the rest. | Resolved: `adopted_id` names the whole repository; the three-repository gate test shows three rows. |
| A2 | HIGH | Requiring a repository for every source could break automatic admissions that passed none. | Resolved: the two automatic callers (`claim_pr`, `_admit`) now pass the repository they hold; findings inherit it or ask once (FR-007). |
| A3 | HIGH | A seat CLI call carries no item identity, so the finding cannot learn its origin by itself. | Resolved: `seat note --item`, named in the builder charter; an unknown item is refused. |
| A4 | MEDIUM | Inheriting the goal of an item under `unplanned` or an old goal would fail admission later with a generic message. | Resolved: the finding records a goal only when it is one of today's; otherwise the admission asks with the exact command. |
| A5 | MEDIUM | A recorded worktree is an absolute path; the start command must quote it. | Resolved: `shlex.quote(tree)`; `brief.write` already accepts an absolute worktree. |
| A6 | MEDIUM | The id shape for several repositories changes (`PR-widget-12` to `PR-acme_widget-12`). | Accepted: ids are per day and the gate card prints them; docs name the shape. |
| A7 | LOW | The gate still claims adopted rows under the first goal. | Accepted: the plan text shows it and the owner approves it on the gate card; not silent. |
| A8 | LOW | `wuwei next` proposes a finding's `plan add` even when it will ask for a goal or repository. | Accepted: the refusal names the exact command, which is the one explicit selection. |

Coverage: FR-001 to FR-008 each have tasks (T001 to T011), 100 percent. CRITICAL 0 open, HIGH 0 open.
