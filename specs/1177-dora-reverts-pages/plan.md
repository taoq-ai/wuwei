# Plan: DORA and the error budget count conventional reverts and read past the first page (1177)

- `cli/wuwei/gh.py`: `pages` takes a `stop` predicate and ends after the page whose last item
  stops. `merged_prs(repo, since, limit=30)` pages the closed list sorted by update, stopping at a
  PR updated before `since`. `deployments(repo, since)` and `releases(repo, since)` page and stop at
  an item created before `since` (both lists come newest first).
- `cli/wuwei/evidence.py`: `reverts(prs)` counts titles matching `revert\b`, case-insensitive;
  `budget` uses it.
- `cli/wuwei/report.py`: `dora` uses `evidence.reverts` and passes `since` to the deploy reads.
- `cli/wuwei/board.py`: `merged_prs(..., limit=1)`, one page as before.
- Copies under `.claude/wuwei/cli/wuwei/`.
- Tests: `tests/conftest.py` FakeGh slices `page`/`per_page` and answers deployments and releases;
  tests in `tests/test_report.py`, `tests/test_evidence.py`, `tests/test_status_perf.py`; the replay
  case key gains `&page=1`.
