# Analysis: 950-start-adopts

| ID | Severity | Finding | Resolution |
| --- | --- | --- | --- |
| A1 | CRITICAL | Comparing worktree HEAD with main checkout HEAD mistakes a normal start from a newer remote base for outside work. | Compare with the item's `worktree.created` start or a readable remote default branch ref; skip after own builder brief or build record. |
| A2 | HIGH | Exact full branch matching misses normal user prefixes and fixed workspace paths miss `.claude/worktrees`. | Match the final branch segment and scan Git's worktree registry, preserving whole-name boundaries. |
| A3 | HIGH | Holding on a failed PR listing prevents valid starts. | Skip only the PR check and mark the start reason unmeasured. |
| A4 | HIGH | Evidence rows without a command leave the day waiting without a route to close. | Put exact `build reconcile` or `plan park` commands in rows and the first owner decision. |
| A5 | MEDIUM | Any prompt line mentioning an item claims unrelated work. | Link seats by name, description or `Item:` line; reject a casual first-line mention. |
| A6 | MEDIUM | Refreshing planned items periodically adds host calls when no start is due; trusting an old cached open PR can suppress the imminent start before refresh. | Refresh only the repository of an imminent start, respecting the cache interval, and trust its cached PR rows only while fresh. |
| A7 | LOW | Re-reading events for each item adds repeated file parsing. | Share one event read across an offers call. |
| A8 | LOW | Repository resolution or a malformed proposal can hide a linked seat. | Check seats independently and catch `AttributeError` as dependency lookup does. |
| A9 | LOW | A held planned item can inherit the generic builder CAP message. | Prefer the held evidence message. |
| A10 | LOW | An item ID followed by punctuation fails the old boundary check. | Accept punctuation while preserving whole item IDs. |

No open CRITICAL or HIGH findings. Every requirement maps to a task and an acceptance scenario.

## Round 2

| ID | Severity | Finding | Resolution |
| --- | --- | --- | --- |
| R1 | HIGH | A No on a hold left a permanent wait, while a PR or worktree hold had no Owner card. | Use one Owner step card for every hold; No rejects that evidence and follows the normal path. Remove the evidence-only wait branch. |
| R2 | MEDIUM | Unrelated ad-hoc roles and case-insensitive item matching produced false holds. | Hold only builder and spec seats; match item IDs case-sensitively and accept an explicit uppercase `Item X.` line. |
| R3 | MEDIUM | Carried worktrees without today's creation event were compared to a moving origin ref. | Read the first `logs/HEAD` creation commit before origin fallback. |
| R4 | MEDIUM | Direct dispatch skipped the stale PR refresh. | Refresh in `dispatch.launch_set`, the common start path. |
| R5 | LOW | Both evidence sources could not share a command, reasons repeated the item, `~` paths were missed and refusal wording lost prompt-only item names. | Build one reconcile command with both flags, use one decision prefix, expand repo paths and preserve prompt lookup for refusals. |

No open CRITICAL or HIGH findings after the round 2 implementation.

## Round 3

| ID | Severity | Finding | Resolution |
| --- | --- | --- | --- |
| F1 | MEDIUM | A seat hold hid a committed worktree, including after the seat card's No. | Offer combined PR and worktree, worktree, then seat candidates, skipping only commands the owner rejected. |
| F2 | MEDIUM | Explore and general-purpose seats linked plan items and put them in flight. | Link only WUWEI roles or recorded builder and spec seats. |
| F3 | LOW | A worktree checked out on an existing branch reads the branch tip as its baseline. | Accepted ceiling, marked with `ponytail:` and an expected-failure regression. Open PR detection still applies. |
| F4 | LOW | Worktree paths with spaces split in card commands. | Shell-quote the worktree argument. |
| F5 | LOW | A No covered later seat cards and the spec omitted same-day worktree rejection. | Name the seat in the park command and document that new commits do not reopen a rejected worktree card that day. |
| F6 | LOW | Unbriefed WUWEI seats with guards off lost prompt-only item names. | Reuse prompt prose lookup for both guard modes. |

No open CRITICAL or HIGH findings after the round 3 implementation.
