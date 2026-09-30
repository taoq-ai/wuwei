# Tasks: README comparison with other ways to run coding agents

**Feature**: `specs/258-readme-comparison/` | **Plan**: `plan.md` | **Spec**: `spec.md`

Test first: T001 and T002 before T003 to T005.

## Phase 1: Test (red)

- [X] T001 [US1] Add `test_readme_compares_with_other_tools` to `tests/test_docs.py`,
  directly after `test_readme_install_and_hero`, asserting everything in plan.md section 1:
  heading present and ordered between "What WUWEI is and is not" and "## Install"; "As of
  <Month> <year>"; the six tool names and six link targets; `### How they compose`;
  `### Where WUWEI is worse` with `only in Claude Code`, `one owner per workspace`,
  `40 to 100 ms`, `not an isolation boundary`, `proven only by`, `live rehearsal`; under 70
  lines; no em-dash.
- [X] T002 Run `python -m pytest -q tests/test_docs.py -k compares` and confirm it fails on
  the missing `## How WUWEI compares` heading.

## Phase 2: README (green)

- [X] T003 [US1] Re-check each URL in `specs/258-readme-comparison/research.md` against the
  tool's current README or docs; drop or correct any claim that no longer holds. Record the
  checked URLs for the PR body (no file needed).
- [X] T004 [US1] Insert `## How WUWEI compares` into `README.md` after "What WUWEI is and is
  not" and before "## Install": date line and stance, the six-column table (seven rows),
  the remaining-axes paragraph, `### How they compose`, `### Where WUWEI is worse`, as in
  plan.md section 2.
- [X] T005 Run `python -m pytest -q tests/test_docs.py` and confirm the new test and
  `test_release_asset_ships_every_linked_doc` pass (every relative link resolves to a
  shipped file).

## Phase 3: Polish

- [X] T006 Check `README.md` and `tests/test_docs.py` for em-dashes, emojis, marketing
  adjectives and absolute local paths; check the table renders on GitHub (no pipes in
  cells) by previewing the Markdown.
- [X] T007 Run the full suite `python -m pytest -q` from the repository root; everything
  passes.
