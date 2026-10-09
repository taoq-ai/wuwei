# Tasks: An issue reference no longer fails the outward lint

- [X] T001 Test: in `tests/test_outbound.py`, a `pr` 404 on `acme/app#7` (ref or
  owner/repo/issue_number) yields the no-PR-context tier; a 404 on the `/pull/7` URL or
  with `pull_number`, and a non-404 error, still yield exit 2.
- [X] T002 Implement: in `cli/wuwei/outward.py` `_pr_context`, return `(FINDINGS, '')` for a
  404 on a bare reference.
- [X] T003 Test: in `tests/test_code_host.py`, the GitHub adapter's `pr` reports a 404 as
  exit 2 with `(HTTP 404)` in the reason (pins the text `_pr_context` matches).
- [X] T004 Implement: none; the T003 test passed on main, the adapter already reports it.
