# Tasks: Publish notices (SECURITY.md, CONTRIBUTING.md, NOTICE credits)

Test first: run each test task, see it fail for the stated reason, then do the change task
that follows it. Run tests with `python -m pytest -q <file>` from the repository root using
the interpreter the task names. Texts, formats and the assertions are in plan.md; licence
facts and URLs are in research.md.

## Security policy (US1, FR-001, FR-002, FR-009)

- [X] T001 In `tests/test_docs.py`, add `test_security_policy_scope_and_channel` (plan.md,
  test 1). Fails today: `FileNotFoundError` for `SECURITY.md`.
- [X] T002 Write `SECURITY.md` per plan.md (supported versions, what counts, what does not
  count in design spec 9.1 wording, how to report through private vulnerability reporting,
  what to expect; links to `docs/site/security.md` and the design spec). T001 passes.

## The signed asset ships SECURITY.md (US4, FR-007)

- [X] T003 In `tests/test_docs.py`, in `test_release_asset_ships_every_linked_doc` (line
  366), add `assert {'LICENSE', 'NOTICE', 'SECURITY.md'} <= listed`. Fails today:
  `SECURITY.md` is not in `MANIFEST.sha256`.
- [X] T004 Add `'SECURITY.md'` to the root file tuple in `scripts/build-release.py` (line 18)
  and to the copied root files in `scripts/headless_e2e.py` (line 148). T003 passes, and
  `tests/test_headless_e2e.py` still passes (its scratch build copies the same files).

## Contributor guide (US3, FR-003, FR-009)

- [X] T005 In `tests/test_docs.py`, add `test_contributing_points_at_the_rules` (plan.md,
  test 2). Fails today: `FileNotFoundError` for `CONTRIBUTING.md`.
- [X] T006 Write `CONTRIBUTING.md` per plan.md, under about 40 lines, pointing at `AGENTS.md`
  and `.specify/memory/constitution.md`. T005 passes.

## Credits and the spec-kit licence (US2, FR-004, FR-005, FR-006, FR-008, FR-009)

- [X] T007 Re-check every row of research.md against its "Checked at" URL (WebFetch). Update
  research.md if a fact changed; mark any row that cannot be confirmed "credit, licence not
  verified".
- [X] T008 In `tests/test_docs.py`, add `test_notice_credits_match_readme_acknowledgements`
  (plan.md, test 3). Fails today: no `## Acknowledgements` section in `README.md` (and no
  `.specify/LICENSE`).
- [X] T009 Add `.specify/LICENSE` with the upstream spec-kit MIT text verbatim.
- [X] T010 Extend `NOTICE` after line 4 with the spec-kit entry, the project entries and the
  concept entries in research.md order, in the plain-text layout of plan.md.
- [X] T011 Append `## Acknowledgements` as the last section of `README.md`, one bullet per
  NOTICE entry with the same Source URL; optionally add the Development-section line naming
  `CONTRIBUTING.md` by its GitHub URL and linking `SECURITY.md`. T008 passes.
- [X] T012 Prove the README check bites: delete one URL from the README section, run T008's
  test, confirm it fails naming that URL, restore it.

## Finish

- [X] T013 Run `python -m pytest -q` from the repository root; everything passes, including
  `tests/test_hygiene.py` (no machine paths) and the existing README tests in
  `tests/test_docs.py`.
- [X] T014 Grep every file you wrote (`SECURITY.md`, `CONTRIBUTING.md`, `NOTICE`,
  `.specify/LICENSE`, `README.md`, `tests/test_docs.py`, the two scripts) for em-dashes and
  emojis and remove any.
- [X] T015 Draft the PR body section "Licences checked": one line per research.md row with
  the "Checked at" URL, the licence found and the date.
