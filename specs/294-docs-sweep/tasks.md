# Tasks: Docs sweep (#294)

Test first: run each test task, see it fail for the stated reason, then do the page task that
follows it. Run tests with `python -m pytest -q tests/test_docs.py` from the repository root
using the interpreter the task names. Details (exact phrases, links, anchors, hero anchors)
are in plan.md.

## Setup

- [X] T001 In `tests/test_docs.py`, add `import os`, `import subprocess`, `import sys` and hoist the table header regex of `test_every_template_config_key_is_documented` to a module constant `TABLE`, used by that test. Run `tests/test_docs.py`: 25 passed, unchanged.

## Command coverage (US1, FR-001, FR-002)

- [X] T002 In `tests/test_docs.py`, add `test_reference_lists_every_cli_command(tmp_path)` as in plan.md test 1. Run it: fails today with `IndexError` or a split error because `reference.md` has no `## Commands` section.
- [X] T003 In `docs/site/reference.md`, add the `## Commands` section and table (one row per `--help` command, help spelling, a "More" link where a section exists). Run T002: passes. Delete one row locally, see it fail naming the command, restore it.
- [X] T004 In `tests/test_docs.py`, extend `test_shipped_things_are_not_called_planned` (create it here, plan.md test 8) with the `reference.md` phrase `will set \`remote\``. Fails today.
- [X] T005 In `docs/site/reference.md` line 128, replace the #65 sentence as in plan.md. Run T004 for that row: passes.

## Section coverage (US1, FR-003, FR-004)

- [X] T006 In `tests/test_docs.py`, add `test_configuration_names_every_config_section` as in plan.md test 2. Run it: fails today listing 35 sections (32 template ones plus `listen`, `responder`, `chat`).
- [X] T007 In `docs/site/configuration.md`, add `## Sections` after the opening paragraph with every section as `` `[name]` `` (`` `[[repos]]` ``), grouped and linked by heading, plus the `[decisions.cruise]` row saying designed, not built, refused by `config check` today. Run T006: passes. Remove one name locally, see it fail naming it, restore it.
- [X] T008 In `tests/test_docs.py` `test_shipped_things_are_not_called_planned`, add the `configuration.md` phrases `MCP scanning (#35)` and `Planned planner rotation`. Fails today.
- [X] T009 In `docs/site/configuration.md`, delete the #35/#36 "remain deferred" sentence (lines 170 to 171) and change "Planned planner rotation" to "Scheduled planner rotation" (line 93). Run T008: passes.

## Site map and cross-links (US3, FR-005, FR-009)

- [X] T010 In `tests/test_docs.py`, change `test_site_pages_and_links` to derive pages from `SITE.glob('*.md')`. Passes today (every page is linked); it pins the map from now on.
- [X] T011 In `tests/test_docs.py`, add `test_security_integrity_and_cross_links` (plan.md test 7). Fails today: `plugin.json` is not in `security.md`.
- [X] T012 In `docs/site/security.md` (ZIRAN paragraph) and `docs/integrity.md`, add the board server and registry gate sentence; in `docs/site/recovery.md` and `docs/site/rehearsal.md`, add the cross-link line. Run T011: passes.
- [X] T013 In `tests/test_docs.py` `test_shipped_things_are_not_called_planned`, add the `charter-overrides.md` phrase `**Planned:**`. Fails today.
- [X] T014 In `docs/site/charter-overrides.md` line 15, replace the `**Planned:**` line with the shipped steward cycle sentence. Run T013: passes.

## Concepts and daily path (US3, FR-009)

- [X] T015 In `tests/test_docs.py`, add `test_concepts_and_daily_cover_shipped_mechanisms` (plan.md test 6). Fails today: no `## Review tiers` in `concepts.md`.
- [X] T016 In `docs/site/concepts.md`, add the six sections (Review tiers, Decision classes and cruise levels with "not built", Sessions, Listener, Heartbeat, Cockpit and board), each linking its detail page. In `docs/site/daily.md`, add the `tier` sentence to step 4.3 and the `phone answers` sentence to section 5. Run T015: passes.
- [X] T017 In `tests/test_docs.py`, add `test_cruise_mode_is_designed_not_built` (plan.md test 5). Fails because `cruise` is not in the README yet.

## README and index (US2, FR-006, FR-007, FR-008)

- [X] T018 In `tests/test_docs.py`, add `test_readme_first_day_and_shipped_areas` (plan.md test 4) and add the `README.md` phrase `interactive day planner` to `test_shipped_things_are_not_called_planned`. Both fail today: no `## What ships today`, no calibrate in the quick start.
- [X] T019 In `README.md`, drop the stale line 21 sentence, add `## What ships today` with the seven area links and the cruise mode sentence ("designed, not built", linking `docs/specs/2026-09-24-wuwei-design.md`), refine the hooks bullet with the M-series figure, and add calibrate, `config promote`, `promote` and `calibrate --interview` to the quick start before `/wuwei plan`. In `docs/site/index.md`, add the same first-day steps to "Start here" and refresh the page descriptions. Run T017 and T018: pass. Run `test_readme_compares_with_other_tools`, `test_entry_guides_install_signed_release_and_explain_development_checkout` and `test_release_asset_ships_every_linked_doc`: still pass.

## Hero (US4, FR-010)

- [X] T020 In `tests/test_docs.py`, add `test_hero_shows_the_current_day` (plan.md test 9). Fails today: no `Calibrate` in the SVGs.
- [X] T021 In `scripts/build-hero.py`, add the calibrate pill with its `interview` owner link and pulse, the `tier: one gate or three` caption, the `Phone` pill with its `DM` link and pulse, and the `beat` ring flash with its `heartbeat` label and reduced-motion entry; extend `<desc>`. Do not move existing geometry or timings. Run `python3 scripts/build-hero.py`, open both SVGs in a browser, and adjust only the new elements until nothing overlaps.
- [X] T022 In `README.md`, extend the hero `alt` text with calibrate, the tier, the phone and the heartbeat. Run T020, `test_hero_files_match_their_generator`, `test_hero_variants_share_geometry_and_motion` and `test_readme_install_and_hero`: all pass. Run `python3 scripts/build-hero.py` again: `git status` shows no further change.

## Finish

- [X] T023 Run the full suite with `python -m pytest -q`: everything passes.
- [X] T024 Check every file changed for em-dashes (U+2014), emojis and absolute local paths (home, temp or scratch directories, the interpreter path) and remove any. Confirm `git status` lists only `README.md`, `docs/site/*.md`, `docs/integrity.md`, `docs/assets/hero-*.svg`, `scripts/build-hero.py`, `tests/test_docs.py` and `specs/294-docs-sweep/`.
- [X] T025 Review fixes: `reference.md` says `remote` is set today (the control plane sets it); the README comparison paragraph says one or three review gates by tier. `test_shipped_things_are_not_called_planned` now also rejects `nothing sets \`remote\`` and `with three parallel review gates`.
