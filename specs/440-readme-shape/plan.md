# Implementation Plan: The README borrows the shape of superpowers' README

**Branch**: `440-readme-shape` | **Date**: 2026-10-03 | **Spec**: `specs/440-readme-shape/spec.md`

## Summary

Reorder and extend `README.md` (six new sections before the comparison, installation split
by harness), credit superpowers in `NOTICE` and the Acknowledgements, reorder the page list
in `docs/site/index.md`, and pin the new shape in `tests/test_docs.py`. No runtime code
changes.

## Technical Context

Docs plus one test file. Python 3.11 stdlib and pytest for the test. Test command:
`python -m pytest -q` from the repository root.

## Constitution Check

- I (stdlib): no runtime change. III (one behaviour, one test): one new test owns the new
  shape; existing tests change only their order pins. IV (test first): every test task
  precedes its text task. V (ponytail): no helper module, no generator; the test reads the
  sources of truth that already exist. Constraints: no em-dashes, no emojis.

## Files to change

| File | Change |
|---|---|
| `tests/test_docs.py` | Update two order pins, extend the NOTICE test, add two tests (below). |
| `README.md` | New sections, `## Install` becomes `## Installation` with subsections and moves before the comparison together with `## Quick start`; superpowers bullet in Acknowledgements. |
| `NOTICE` | New superpowers entry. |
| `docs/site/index.md` | Reorder the page list only. |

Nothing else changes: not the hero block or `scripts/build-hero.py` (#431 owns the hero),
not the lead, not `## How WUWEI compares`, not `## What ships today`, not `## Limits`,
not `## Development installs` or `## Development`, not `mkdocs.yml` (the nav order is not
pinned against the index and the issue asks only for the index links).

## What to reuse (do not re-implement)

- `wuwei.registry.INTERFACES` and `wuwei.registry.known(port)`: the shipped adapter names
  per port, read from `adapters/<port>/*.py`.
- `wuwei.__main__.GROUPS`: the command names `bin/wuwei --help --all` prints, in process
  (no subprocess; `test_reference_lists_every_cli_command` already checks GROUPS against the
  parser).
- `_plain(name)` in `tests/test_docs.py`: asserts no em-dash and no emoji and returns the
  text. Use `_plain('README.md')` in the new test.
- The section-split idiom the file already uses:
  `text.split(f'\n{heading}\n', 1)[1].split('\n## ', 1)[0]`, as a local lambda in the new
  test (as `test_guard_boundaries_are_stated_once` does). No shared helper.
- `hooks/hooks.json` keys for the hook events; `skills/*/SKILL.md` and `charters/*.md`
  globs for skills and seats.

## Test changes (`tests/test_docs.py`)

1. `test_readme_compares_with_other_tools` (line 119): replace the order assertion with
   `readme.index('## What WUWEI is and is not') < readme.index('\n## Installation\n') <
   readme.index('## How WUWEI compares')`. Everything else in it stays.
2. `test_notice_credits_match_readme_acknowledgements` (line 780): add `'superpowers'` to
   the names tuple, and assert the NOTICE superpowers block (text from `\nsuperpowers\n`
   to the next blank line) contains `README` and `MIT`. The URL parity loop then forces
   the Acknowledgements bullet.
3. New `test_readme_tells_the_day_in_superpowers_shape()`:
   - `readme = _plain('README.md')`; `len(readme.splitlines()) <= 300`.
   - Heading order: the list in FR-001 from `## What ships today` to `## How WUWEI
     compares`, each found as `\n<heading>\n`, indices strictly increasing.
   - `section(h)` lambda as above.
   - How it works: paragraphs = non-empty blocks of `section` split on blank lines; exactly
     4; each `re.search(r'\byou\b', p, re.I)` and `len(p.splitlines()) <= 5`; the section
     contains `/wuwei:wuwei-plan`, `retro`, `status line`, `DM`, `safe path`.
   - The basic workflow: `steps = re.findall(r'^(\d)\. \*\*', s, re.M)` equals
     `['1', ..., '7']`; the lowercased section contains, in increasing index order,
     `calibrat`, `morning gate`, `build`, `tier`, `shepherd`, `retro`, `memory`; contains
     `posture` and `not built`; `len(s.splitlines()) <= 20`.
   - When something goes wrong: `re.findall(r'^- ', s, re.M)` has length 5; contains
     `why last refusal`, `doctor --fix`, `wuwei next`, `shadow report`, `.wuwei/days/`.
   - What is inside: for each `skills/*/SKILL.md`, `(skills/<name>/SKILL.md)` in section;
     for each `charters/*.md` not starting with `_`, `(charters/<name>.md)` in section;
     each key of `json.loads(hooks/hooks.json)['hooks']` in section; `(docs/site/index.md)`
     and `(docs/site/adapters.md)` in section. Adapters: rows
     `re.findall(r'^\| `?([a-z_]+)`? \| ([^|]+) \|', s, re.M)` into a dict
     `{port: set of names split on ', ' with backticks stripped}`; assert
     `rows == {port: set(registry.known(port)) for port in registry.INTERFACES}`. Planned:
     the line starting `Planned:`; every capitalised word on it lowercased is not in any
     `registry.known(port)`.
   - Philosophy: exactly 5 lines matching `^- `; flattened lowercase section contains
     `safe path`, `records`, `cooperative mistake prevention`, `code host`, `warn`,
     `posture`, `unmeasured`, `stdlib`.
   - Installation: `### Claude Code`, `### Codex`, `### Other harnesses (planned)` at
     increasing indices inside the section. Claude Code part contains `wuwei.tar.gz` before
     `/plugin marketplace add ../wuwei-plugin`, and `/plugin marketplace add taoq-ai/wuwei`
     and `(#development-installs)`. Codex part contains `adapters.runtime` and
     `codex.command` and `(docs/specs/2026-09-30-codex-plugin-spike.md)`; if
     `not (ROOT / '.codex-plugin/plugin.json').exists()`, it contains `planned`. Planned
     part contains `https://github.com/taoq-ai/wuwei/issues/441`, `planned`, `measured`,
     and no ```` ``` ````.
   - Names exist: over the six new sections joined, every `/wuwei:([a-z-]+)` is a
     directory under `skills/`; every code span `` `(?:\.\./wuwei-plugin/|bin/)?wuwei
     ([a-z][a-z-]*)` `` (regex `` `[^`]*?\bwuwei ([a-z][a-z-]*) ``) names a word in
     `' '.join(words for _, words in GROUPS).split()`.
4. New `test_docs_index_mirrors_the_readme_sections()`:
   - For (heading, page) in How it works/`daily.md`, The basic workflow/`concepts.md`,
     When something goes wrong/`recovery.md`, What is inside/`adapters.md`,
     Philosophy/`security.md`, Installation/`integrity.md`: `(docs/site/<page>` in the
     README section.
   - In `docs/site/index.md`, the page list is the lines starting `- [` before
     `## Start here`; the indices of `(<page>)` for the six pages in that order are strictly
     increasing.

Mutation checks by hand (task T012): drop a skill link, add a fake adapter name to the
table, reorder two headings, add a fifth bullet to When something goes wrong, add an
install code block to the planned subsection; each fails the new test.

## README content outline (the builder writes the prose)

All second person where the owner is meant. Each glossary word at its first prose use
links `docs/site/concepts.md#<term>`; expect at least seat, sentinel, shepherd, steward,
nudge, page, carry, unmeasured, park, host terminal to move their first link into the new
sections (`test_glossary_words_link_at_first_use` names the first miss). Link files only.

- `## How it works` (4 paragraphs, at most 5 lines each, link `docs/site/daily.md`):
  1. Morning: you run `/wuwei:wuwei-plan`; the planner ranks candidate work against your
     goals and puts one Ask card in front of you, "Approve today's plan as proposed?"
  2. Day: builders work in their own worktrees, reviewers that did not write the change
     check it, a shepherd follows each pull request; the status line shows where the day
     stands.
  3. When a seat needs you, the question arrives as a decision, in the session or as a
     DM on your phone; you answer and the day continues.
  4. Evening: close and the retro (`/wuwei:wuwei-report`) propose rule changes you promote.
     The hooks make the safe path the default, so nothing special has to be remembered.
- `## The basic workflow` (7 entries plus the rule line, link `docs/site/concepts.md`):
  1. **Setup and calibration**: `wuwei setup` in a host terminal; leaves `.wuwei/` and
     the config. 2. **Plan and the morning gate**: `/wuwei:wuwei-plan`; leaves the
     approved plan. 3. **Build**: an approved item; leaves a branch, tests first, green
     fast checks; specification mode (spec-kit steps enforced by hooks) is designed, not
     built (design 5.10). 4. **Review by tier**: a change done; one gate or three, one
     fix round; leaves verdicts. 5. **Shepherd to merge**: a raised PR; the merge policy
     and branch protection decide. 6. **Close and retro**: end of day,
     `/wuwei:wuwei-report` or `/wuwei:wuwei-retro`; leaves the report and proposals.
     7. **Memory into tomorrow**: promoted proposals and `/wuwei:wuwei-consolidate`;
     carried items open the next plan. Then one line: the hooks hold each step at the
     moment of action, warn or block by the posture you configured.
- `## When something goes wrong` (5 bullets, link `docs/site/recovery.md`):
  `bin/wuwei why last refusal`, `bin/wuwei doctor --fix`, `bin/wuwei next`,
  `bin/wuwei shadow report`, the records under `.wuwei/days/<date>/` (state, events,
  decisions).
- `## What is inside` (short grouped list plus one table, links
  `docs/site/index.md` and `docs/site/adapters.md`): Skills (4, linked); Seats (planner,
  lead, builder, shepherd, steward, four sentinels, each linked to its charter); Guards
  by hook event (PreToolUse, PostToolUse, SubagentStop, SessionStart, PreCompact, Stop,
  one clause each from design 4.1, shipped behaviour only); Adapters table `| Port |
  Shipped |` with one row per port in `registry.INTERFACES` (16 today; the issue notes said 14), then
  `Planned: Signal and WhatsApp as owner channels (design 15).`; Docs site link.
- `## Philosophy` (5 bullets, link `docs/site/security.md`).
- `## Installation` (link `docs/site/integrity.md`):
  `### Claude Code`: the current Install body unchanged, then one line on
  `/plugin marketplace add taoq-ai/wuwei` as the development source, see
  [development installs](#development-installs).
  `### Codex`: Codex runs seats as an optional runtime today: `adapters.runtime =
  "codex"` and `codex.command`, or one gate per item through `gates.second_opinion`. The
  Codex plugin (guards in Codex sessions) is planned; the
  [Codex spike](docs/specs/2026-09-30-codex-plugin-spike.md) has the gap table.
  `### Other harnesses (planned)`: tracked in issue #441; a harness is listed as supported
  only after a measured fixture day runs on it; candidates on one line (Cursor, Gemini
  CLI, GitHub Copilot CLI, OpenCode, Kimi Code, Kiro, Antigravity and others from #441).
- `## Quick start`: moved unchanged after Installation.
- `## Acknowledgements`: add after the Spec Kit bullet:
  `- [superpowers](https://github.com/obra/superpowers): the shape of this README's
  sections (MIT, structure only).`

`NOTICE` entry, after ZIRAN in "Projects whose ideas or tools WUWEI uses (no code
copied)":

```
superpowers
  Source: https://github.com/obra/superpowers
  Licence: MIT, Copyright (c) 2025 Jesse Vincent
  Used: the section structure of README.md (how it works, the basic workflow, when
  something goes wrong, what is inside, philosophy, installation per harness); no text
  copied.
```

`docs/site/index.md` page list order: Daily path, What the session knows, Concepts,
Recovery, Adapters and ports, Charter overrides, Security integration, Integrity,
Configuration, Operator reference, Remote operation, Release rehearsal. Bullet text
unchanged.

## Risks

- The glossary-link test will fail on the first unlinked term; fix one term at a time.
- `## Install` is a prefix of `## Installation`; the updated pin uses
  `'\n## Installation\n'`.
- Line budget: 215 today; the plan estimated about 290, but the first build was 337 (16
  adapter rows, not 14). Fixed by one line per list item, the section links folded into
  the items and the Codex and planned-harness paragraphs on one line each: 300 lines.
