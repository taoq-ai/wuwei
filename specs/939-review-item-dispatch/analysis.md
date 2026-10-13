# Cross Artifact Analysis: Review Item Dispatch

**Date**: 2026-10-13

| Severity | Finding | Resolution |
| --- | --- | --- |
| HIGH | A gate brief normally requires a built item. | Permit the review kind directly at the gate boundary and verify the PR head. |
| HIGH | An ordinary gate would raise a PR after PASS. | Finish a review on the existing gate decision path for PASS or FIX; retain ESCALATE and PARK handling. |
| HIGH | A resumed sentinel transcript can name two briefs. | Give the review a fresh sentinel and keep the first brief binding. |
| HIGH | A PR listing lacked branch and fork metadata. | Read both in the existing GitHub listing and refuse a fork or unknown head repository. |
| HIGH | A pushed PR can invalidate a verdict after briefing. | Use a head-specific brief name and recheck the live PR on receipt. |
| HIGH | A PR branch may already be checked out in an earlier worktree. | Reuse the existing branch worktree through worktree adoption. |
| HIGH | Adoption may return a different worktree path than the default. | Dispatch checkout first, then brief the recorded path on the next step. |
| HIGH | Checkout and brief steps could reserve a sentinel seat prematurely. | Return a command-only run action for checkout; count only a sentinel launch. |
| HIGH | A cached PR may omit an older review target or retain a stale head. | Read the named PR directly if absent; check its live head at brief and receipt. |
| HIGH | ESCALATE or PARK could be silently marked done on receipt. | Decide the one-role review verdict after receipt through the existing gate path. |
| HIGH | Finished review items could hold close or appear open in report. | Skip status done items in both readers. |
| HIGH | Completed review items could trigger ordinary PR duties. | Exclude review items from PR ping and shepherd duties. |
| HIGH | A fast-forward offer repeats for an ahead or diverged worktree. | Offer it only after merge-base confirms local HEAD is an ancestor of the PR head; otherwise refuse with next steps. |
| HIGH | A completed review verdict vanishes from the day report. | List its current verdict and workspace-relative verdict file in Done, and include the path in the done action. |
| MEDIUM | An untyped candidate still needs its old route. | Keep build as the default and test it. |
| LOW | A null PR on an ordinary build candidate rejects the proposal. | Treat null as an absent PR at admission. |
| LOW | An unfinished review with a pushed worktree branch gets an unclaimed PR finding. | Skip that build-only finding for review items. |

No unresolved CRITICAL or HIGH findings.
