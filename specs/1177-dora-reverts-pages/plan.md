# Plan: DORA and the error budget count conventional reverts and failed deploys, and read past the first page (1177)

- `cli/wuwei/gh.py`: `pages` takes a `stop` predicate and ends after the page whose last item
  stops. `merged_prs(repo, since, limit=30)` pages the closed list sorted by update, stopping at a
  PR updated before `since`. `deployments(repo, since)` pages, stops at a deployment created before
  `since` and keeps those inside the window. `releases(repo, since)` pages the same way.
- `cli/wuwei/evidence.py`: `failures(repo, merged, deploys)` returns the count of change failures
  (reverts by title, plus runs of failed production deploys per environment) and the restores as
  (first failed, green) time pairs. It reads each production deployment's statuses, one host call
  each. `budget` reads deployments and divides the count by merges.
- `cli/wuwei/report.py`: `dora` calls `evidence.failures` inside its read, uses the count for the
  rate and the median restore hours for `time_to_restore`.
- `cli/wuwei/board.py`: `merged_prs(..., limit=1)`, one page as before.
- Copies under `.claude/wuwei/cli/wuwei/`.
- Docs: design.md section 6 (error budget definition), docs/site/concepts/metrics.md (DORA),
  learning.md and many-repositories.md.
- Tests: `tests/conftest.py` FakeGh slices `page`/`per_page` and answers deployments, releases and
  deployment statuses; tests in `tests/test_report.py`, `tests/test_evidence.py`,
  `tests/test_status_perf.py`; the replay case answers the paged merged read and the deployments read.
