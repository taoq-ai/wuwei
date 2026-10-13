# Cross Artifact Analysis: PR Auto Claim

**Date**: 2026-10-13

| Severity | Finding | Resolution |
| --- | --- | --- |
| HIGH | Removing the item pretool refusal bypasses the pre-PR gate path. | Restore the main guard and route an ungated hook result to unclaimed. |
| HIGH | A planned item can move directly to raised through `record_pr`. | Do not auto link planned items; verify local gate evidence before any link. |
| HIGH | An unclaimable row can repeat ahead of seat recovery. | Restrict to configured repos, refresh open status, include goal choice, rank recovery first, and dismiss after one attempted command. |
| MEDIUM | Several commands or URL lines can link the wrong PR. | Require one create segment, one URL and no other output-producing command; skip dry-run and web modes. |
| MEDIUM | A refused matched claim can disappear. | Record both its error and the unclaimed URL with a redacted reason. |
| MEDIUM | A worktree match omits the branch. | Read the local VCS branch and pass it to the shared claim writer. |
| LOW | Case and approval ordering can miss a matching item. | Canonicalize configured repo casing and prefer approved branch matches. |
| LOW | A timeout is classified as a generic claim error. | Let TimeoutError reach the existing `traces.slow` path. |
| MEDIUM | A refused item match can adopt a duplicate PR item. | Offer `pr claim` with `--item` and instruct gates before claiming the existing PR. |
| MEDIUM | Pending unclaimed events force a host refresh on every `next`. | Refresh when the cache predates the event or the poll interval elapsed; skip cleared rows. |

No unresolved CRITICAL or HIGH findings.
