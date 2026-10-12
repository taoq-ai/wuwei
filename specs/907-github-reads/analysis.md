# Specification Analysis Report: 907-github-reads (with 900-listing-unmeasured)

| ID | Severity | Summary | Resolution |
|----|----------|---------|------------|
| A1 | HIGH | `_rebase` no longer reads the PR again before its local rebase and push; a teammate's push in between could be overwritten. | Resolved: the push leases the read head (`vcs.push(..., pr['head'])`), so a moved branch refuses the push; the read is from the same action seconds earlier, as the old second read was. Merge and `--push` keep their own fresh reads. |
| A2 | HIGH | A failed repository must not make the healthy ones stale or unusable. | Resolved: per-repository `at` and `failed` in `prs.json`; `refresh` replaces only the read repository's rows; tested with three repositories. |
| A3 | MEDIUM | A `prs.json` written before this change has no `repos` map. | Resolved: without the map every repository takes the file's `fetched_at`, as before; existing fixtures pass unchanged. A repository added after a new-format write has no entry and is due; one removed from config leaves the listing. |
| A4 | MEDIUM | A failed repository's `at` is its failure time; quoting its rows with that time would pass stale state off as fresh. | Resolved: offers short-circuit its raised PRs to `unmeasured` before the G1 time check; a brief's counterpart line treats it as unlisted. |
| A5 | MEDIUM | A PR with no row in a failed repository: marking it unmeasured would hold the day forever (code host fakes, an adapter without listing). | Resolved: it keeps its `pr act` step, which reads that PR fresh; no stale state decides. |
| A6 | MEDIUM | WUWEI's own raise, claim, push or merge event makes every repository due, a failed one included, before its retry time. | Accepted: one call per repository per own PR action, which is when fresh state matters. |
| A7 | LOW | `dispatch next <item>` run by hand on a raised item still reads the listing head for a moved check, even for a failed repository. | Accepted: next never offers it for an unmeasured PR; pre-existing behavior on a manual command. |
| A8 | LOW | A claimed PR with a worktree whose `pr act` launch resolves to a plain run is read once per `wuwei next` until the planner acts. | Accepted, out of scope; in the spec's Assumptions as a follow-up. |

Coverage: 907 FR-001 to FR-005 and 900 FR-001 to FR-003 each have tasks (T001 to T011), 100 percent. CRITICAL 0 open, HIGH 0 open.
