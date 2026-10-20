# Spec: DORA and the error budget count conventional reverts and read past the first page (1177)

## In my words

On 2026-10-19 `wuwei report --dora` gave ai-stacks a change failure rate of 0.0 although
#3388 (`revert(infra/TIN-817): ...`) reverted a change. Two bugs caused it:

1. `evidence.budget` and `report.dora` count a revert only when the title starts with `Revert`,
   case-sensitive. A conventional `revert:` or `revert(scope):` title is missed.
2. `gh.merged_prs`, `gh.deployments` and `gh.releases` read one page of 100. A busy repository
   shows `deploys: 100` and `merged: 99`, a page cap, not a count.

After this change one shared rule (`evidence.reverts`) counts a PR as a revert when its title starts
with the word revert in any case. Both the error budget and the DORA table use it. The three reads
page until a page ends before the window (`gh.pages` with a stop), so the counts cover the whole
window. The board keeps reading one page of merged PRs, so a warm board makes no more host calls
than after #1161.

Out of scope: counting failed deployments as change failures, measuring time to restore, and
report.py's tracing of reverts to their originals.

## Acceptance scenarios

1. Merged PRs titled `revert(infra/TIN-817): drop the issuer`, `revert: x` and `Revert "y"` each
   count as a revert in `report --dora` and `evidence.budget`; `fix: a revert-proof parser` does not.
2. 150 deployments in the window over two pages give `deploys: 150`; the same holds for releases.
3. 250 PRs merged in the window give `merged: 250` for budget and dora, and the reads stop at the
   first page whose last PR was updated before the window.
4. A warm board's merged-PR read is still one host call.
5. With no deployment status read, `time_to_restore` stays `unmeasured`.
