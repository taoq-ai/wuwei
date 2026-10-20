# Spec: DORA and the error budget count conventional reverts and failed deploys, and read past the first page (1177)

## In my words

On 2026-10-19 `wuwei report --dora` gave ai-stacks a change failure rate of 0.0 for a window that
held two failed production deploys and #3388 (`revert(infra/TIN-817): ...`). Three things were wrong:

1. `evidence.budget` and `report.dora` counted a revert only when the title started with `Revert`,
   case-sensitive. A conventional `revert:` or `revert(scope):` title was missed.
2. Failed deployments never counted, and time to restore was always `unmeasured`.
3. `gh.merged_prs`, `gh.deployments` and `gh.releases` read one page of 100. A busy repository
   showed `deploys: 100` and `merged: 99`, a page cap, not a count.

After this change one shared function, `evidence.failures`, counts the change failures that both the
error budget and the DORA table use:

- each merged PR whose title starts with the word revert, in any case;
- each run of failed production deployments (state `failure` or `error`) in one environment, up to
  the next successful deployment of that environment. A rerun that fails again is the same failure.
  A run still failing at the window's end counts with no restore time.

A deployment is production when GitHub marks its environment production or the environment name
contains "prod". Its state is its newest status that is not `inactive`. Time to restore is the median
time from the first failed deployment of a run to the green one. It stays `unmeasured` when nothing
was restored. The rate is change failures over merges.

The three reads page until a page ends before the window (`gh.pages` with a stop). The board keeps
one page of merged PRs, so a warm board makes no more host calls than after #1161.

Out of scope: report.py's tracing of reverts to their originals.

Owner ruling, 2026-10-20: count failed deployments and measure time to restore "In this PR".

## Acceptance scenarios

1. Merged PRs titled `revert(infra/TIN-817): drop the issuer`, `revert: x` and `Revert "y"` each
   count as a revert in `report --dora` and `evidence.budget`; `fix: a revert-proof parser` does not.
2. 150 deployments in the window over two pages give `deploys: 150`; the same holds for releases.
3. 250 PRs merged in the window give `merged: 250` for budget and dora, and the reads stop at the
   first page whose last PR was updated before the window.
4. A warm board's merged-PR read is still one host call.
5. The ai-stacks shape: 5 merges with one revert, a production deploy failing at 08:00, its rerun
   failing at 09:00, green at 12:06, a failed staging deploy, and another production environment
   still failing. dora and budget give a rate of 0.6 (the revert, one restored run and one open run,
   over 5 merges), time to restore is 4.1 hours, and the tier is raised.
6. With no failed production deployment restored, `time_to_restore` stays `unmeasured`.
