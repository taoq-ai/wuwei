# Tasks: The docs site uses the same MkDocs Material layout and design as ZIRAN (#392)

Test first: run each test task, see it fail for the stated reason, then do the task that
follows it. Run tests with `python -m pytest -q <file>` from the repository root using the
interpreter the task names. Exact test code, config, strings and placement are in plan.md.
No em-dashes, no emojis, no absolute local paths. Do not commit; use plain `mv`, not
`git mv`.

## Setup

- [X] T001 Run `python -m pytest -q tests/test_docs.py tests/test_headless_e2e.py tests/test_owner_records_lint.py`: 116 passed on main at b4b3b28. Note the count.

## US2: pages are plain Markdown (front matter, breadcrumb, `.md` links)

- [X] T002 [US2] In `tests/test_docs.py`, delete `test_site_pages_and_links` and add `test_site_pages_are_plain_markdown` (plan.md section 1); switch lines 445, 645-646 and 835 to `.md` and drop the front-matter clause on line 828. Run them: the new test fails on the first page's `---` front matter; the `.md` assertions fail on `(remote.md)`, `(rehearsal.md)`, `(agent.md)`.
- [X] T003 [US2] Rewrite the 12 pages in `docs/site/*.md` with the three substitutions of plan.md section 3, from a script outside the repository. Run T002: passes.

## US4 and US1: the integrity page moves into the site

- [X] T004 [US4] In `tests/test_docs.py`, change lines 243 and 642 to `SITE / 'integrity.md'`. Run `tests/test_docs.py -k "entry_guides or security_integrity"`: fails with `FileNotFoundError` for `docs/site/integrity.md`.
- [X] T005 [US4] `mv docs/integrity.md docs/site/integrity.md`; in `docs/site/security.md:81` link `integrity.md`; in `README.md:92` link `docs/site/integrity.md`. Run T004: passes. Run `tests/test_headless_e2e.py -k scratch_build`: fails with `FileNotFoundError` for `docs/integrity.md` (the existing test is the red step for T006).
- [X] T006 [US4] In `scripts/headless_e2e.py:148-150`, copy `docs/site/integrity.md` and create the parent with `parents=True` (plan.md section 4). Run `tests/test_headless_e2e.py`: passes.

## US1 and US4: the hero moves into the site and shows per palette

- [X] T007 [US1] In `tests/test_docs.py`, switch the hero paths on lines 96-97, 102, 154, 281, 543 and 664 to `docs/site/assets` / `SITE / 'assets'`, and add the index `#only-light` / `#only-dark` assertions to `test_readme_install_and_hero` (plan.md section 1 table). Run `tests/test_docs.py -k "hero or release_asset"`: fails, `docs/site/assets/hero-light.svg` is missing and the README names the old path.
- [X] T008 [US1] `mv docs/assets/hero-light.svg docs/assets/hero-dark.svg docs/site/assets/` and remove the empty `docs/assets/`; update `README.md:3-5` and `scripts/build-hero.py:1,339` to `docs/site/assets/`; insert the two `<img>` lines with the README alt text into `docs/site/index.md` after the first paragraph (plan.md sections 3 and 4). Run `python3 scripts/build-hero.py` and confirm the SVGs are unchanged. Run T007: passes.

## US1: `mkdocs.yml` with every page in the nav

- [X] T009 [US1] In `tests/test_docs.py`, add `test_mkdocs_nav_covers_every_page` (plan.md section 1). Run it: fails with `FileNotFoundError` for `mkdocs.yml`.
- [X] T010 [US1] Add `mkdocs.yml` at the repository root exactly as plan.md section 2, and add the `- [Integrity](integrity.md): ...` item to `docs/site/index.md` (plan.md section 3). Run T009: passes. Run `tests/test_docs.py -k glossary`: passes.

## US3: the workflow deploys with gh-deploy; Jekyll is gone

- [X] T011 [US3] In `tests/test_docs.py`, add `test_docs_workflow_deploys_mkdocs` (plan.md section 1). Run it: fails on the first missing phrase, `mkdocs.yml` (today's Jekyll workflow already lists `docs/site/**`).
- [X] T012 [US3] Replace `.github/workflows/docs.yml` with plan.md section 5, delete `docs/site/_config.yml`, add `/site/` (anchored, see plan.md section 6) to `.gitignore`. Run T011: passes.

## US3: contributor preview and the one-time Pages setting

- [X] T013 [US3] In `tests/test_docs.py` `test_contributing_points_at_the_rules`, add the phrases `uvx --with mkdocs-material mkdocs serve` and `gh-pages`. Run it: fails on the first.
- [X] T014 [US3] Add the `## Docs site` section of plan.md section 7 to `CONTRIBUTING.md`. Run T013: passes (including `calibrate.instruction_like`).

## Finish

- [X] T015 Run the strict build from the repository root through a script file (`bash <file>` containing `uvx --with mkdocs-material mkdocs build --strict`): exit 0, no `WARNING` line. Remove the generated `site/`.
- [X] T016 Run the full suite with `python -m pytest -q`: everything passes and no assertion was removed or loosened beyond the Jekyll ones listed in plan.md section 1.
- [X] T017 Check every changed file for em-dashes (U+2014), emojis and absolute local paths; remove any. Confirm `git status` lists only `mkdocs.yml`, `.github/workflows/docs.yml`, `.gitignore`, `CONTRIBUTING.md`, `README.md`, `scripts/build-hero.py`, `scripts/headless_e2e.py`, `tests/test_docs.py`, the pages under `docs/site/` (including the new `integrity.md` and `assets/`), the deleted `docs/site/_config.yml`, `docs/integrity.md` and `docs/assets/`, and `specs/392-mkdocs-site/`.
