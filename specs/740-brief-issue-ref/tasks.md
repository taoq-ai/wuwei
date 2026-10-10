# Tasks: an owner/repo#N reference in a brief never fails registration with Not Found

**Input**: `specs/740-brief-issue-ref/spec.md`, `specs/740-brief-issue-ref/plan.md`

**Tests**: required (constitution IV). Each behaviour's test task comes before its
implementation task; run the test and see it fail for the expected reason before the code.
Run tests with `python -m pytest -q` from the repository root.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Shared helper (User Story 3)

- [X] T001 [US3] In `tests/test_brief.py`, add `test_not_found_reads_the_404_reason`:
  `references.not_found` is true for
  `'github.pr: could not run: gh exited 1 (acme/widget): gh: Not Found (HTTP 404)'` and for a
  `ValueError` carrying that text, false for a `gh: Bad credentials (HTTP 401)` reason and
  for `''`. Run it; it fails (`AttributeError`, no `not_found`).
- [X] T002 [US3] In `cli/wuwei/references.py`, add `not_found(reason)` (plan, Design 1).
  Run T001; it passes.
- [X] T003 [US3] In `cli/wuwei/outward.py`, `_pr_context` (lines 304 to 308), replace the
  inline `re.search(r'\(HTTP 404\)', ...)` with `references.not_found(result.reason)` and
  update the `#606` comment to name the helper (plan, Design 2). Refactor under an existing
  test: run `tests/test_outbound.py -k issue_reference_reads_without_pr_context` before and
  after; every row passes unchanged (FR-005).

## Phase 2: Tests for User Stories 1 and 2 (P1, P2)

- [X] T004 [US1] In `tests/test_brief.py`, add a small helper or fixture variant that writes
  `[[repos]]\nname = "acme/widget"\npath = "tree"\ndefault_branch = "main"\n` to the `day`
  fixture's `.wuwei/config.toml` (as `test_repo_default_branch` does). Add
  `test_issue_reference_registers_with_a_warning`: set `day[3].results['pr']` to
  `registry.Result(2, None, 'github.pr: could not run: gh exited 1 (acme/widget): gh: Not Found (HTTP 404)')`
  and the state's `tickets` to `{'X': {'id': 'acme/widget#24'}}` (`state._write_state`,
  `reserved=False`); run `brief(monkeypatch, 'Ticket: acme/widget#24', 'builder', 'X', 'tk')`.
  Assert exit 0; `briefs/tk.md` contains
  `Warning: acme/widget#24 is no pull request the host could read (` and the body line
  `Ticket: acme/widget#24`; a `brief written` event exists; `main(['why', 'X', '--json'])`
  prints JSON whose `ticket` is `acme/widget#24` (spec US1 scenarios 1 and 2). Run it; it
  fails with exit 2 (the reproduced root cause).
- [X] T005 [US1] In `tests/test_brief.py`, add `test_counterpart_pr_line_is_unchanged`: the
  same config, `day[3].results['pr'] = registry.Result(0, {'head': 'a' * 40})`, body
  `see acme/widget#7`; assert exit 0, the brief has
  `Counterpart acme/widget#7 head (no-cache): {"head": "aaaa...` and no `Warning:` line
  (US1 scenario 3, FR-004). Run it; it passes today (a guard against the change, not a red
  test; note it as such).
- [X] T006 [US2] In `tests/test_brief.py`, add
  `test_unreadable_counterpart_follows_the_posture`, parametrized on
  (posture, reason, expected exit): (`guarded` default, 401 reason, 0),
  (`strict`, 401 reason, 2), (`strict`, 404 reason, 0). The 401 reason is
  `'github.pr: could not run: gh exited 1 (acme/widget): gh: Bad credentials (HTTP 401)'`.
  Write `[security]\nposture = "strict"` into the config for the strict rows, keeping the
  `[[repos]]` row. Assert: exit 0 rows have the `Warning: acme/widget#24` line with the
  reason text; the exit 2 row has the 401 reason on stderr, no `briefs/<name>.md` and no
  `brief written` event (FR-002, US2 scenarios 1 to 3). Run it; the two exit 0 rows fail
  (exit 2 today), the strict-401 row passes today and pins that the refusal stays.

## Phase 3: Implementation (User Stories 1 and 2)

- [X] T007 [US1] [US2] In `cli/wuwei/brief.py`, `write` (lines 528 to 532), read the posture
  once before the loop and wrap the counterpart read in `try`/`except ValueError`: a 404
  reason or a non-strict posture appends the warning line, anything else re-raises (plan,
  Design 3); add `references` to the top-level `from wuwei import ...` line. Run T004, T005
  and T006; all pass.

## Phase 4: Polish

- [X] T008 Run the changed test files (`tests/test_brief.py`, `tests/test_outbound.py`); the full suite runs in CI (owner, 2026-10-10).
- [X] T009 Check the changed files (`cli/wuwei/references.py`, `cli/wuwei/outward.py`,
  `cli/wuwei/brief.py`, `tests/test_brief.py`, the spec files) for em-dashes, emojis and
  absolute local paths; remove any.

## Dependencies

- T001 before T002; T002 before T003 and T007.
- T004, T005 and T006 before T007.
- T008 and T009 last.
