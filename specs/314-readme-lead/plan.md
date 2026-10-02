# Implementation Plan: README lead, WUWEI first in the comparison, short limits

**Branch**: `314-readme-lead` | **Date**: 2026-10-02 | **Spec**: `specs/314-readme-lead/spec.md`

## Summary

Text-only change in `README.md` and one paragraph of `docs/site/index.md`, guarded by
`tests/test_docs.py`. Add a lead under the hero, rebuild the comparison table by question
with WUWEI first, shorten "How they compose" to two sentences, replace "Where WUWEI is worse"
with `## Limits` below Quick start, align the hero alt text and the docs index intro. No
code, no new files outside this feature directory, no SVG regeneration.

## Technical Context

Markdown docs; pytest docs tests (`tests/test_docs.py`), stdlib `re` only, the same
split-by-heading idiom the file already uses. Run `python -m pytest -q tests/test_docs.py`,
then the full suite.

## Constitution Check

- IV Test first: the test edits land first and fail against the current README.
- V Ponytail: edit the existing test in place and add one small test; no helper, no new
  fixture. Reuse the `section = readme.split(heading, 1)[1].split('\n## ', 1)[0]` idiom.
- Writing style: no em-dashes, no emojis; the checklist in `charters/_common-authoring.md`.
- Pass.

## Files and exact changes

### tests/test_docs.py

1. `test_readme_compares_with_other_tools` (line 39), rewrite in place:
   - Keep: heading `## How WUWEI compares`; order What WUWEI is and is not < How WUWEI
     compares < Install; the "As of <Month> <year>" regex; the six tool names and six links;
     `### How they compose`; section under 70 lines; no em dash.
   - Add: `rows = [line for line in section.splitlines() if line.startswith('|')]`;
     `rows[0]` contains `Who plans the day`, `Who reviews the work`,
     `What stops a bad merge`, `What is learned afterwards`, `Where it runs`, and
     `rows[0].count('|') <= 7` (at most six columns); the first cell of `rows[2]`
     contains `WUWEI`.
   - Replace the `### Where WUWEI is worse` asserts with
     `assert 'Where WUWEI is worse' not in readme`.
   - Add the banned-word check:
     `for word in ('professional', 'enterprise', 'best-in-class'): assert word not in readme.lower(), word`.
2. New `test_readme_lead_and_limits` next to it:
   - Lead: the text between `'Apache 2.0</a></p>'` and `'## What WUWEI is and is not'`
     contains `careful engineering team`, `ranked`, `did not write` and `retro`.
   - Alt and index aligned: the hero alt (`re.search(r'alt="([^"]+)"', readme)[1]`) and the
     first paragraph of `docs/site/index.md` after the `# WUWEI documentation` heading both
     contain `ranked` and `retro`.
   - Limits: `readme.index('## Quick start') < readme.index('## Limits') <
     readme.index('## Development installs')`; flatten the section with
     `' '.join(section.split()).lower()` and assert each of `needs claude code`,
     `one owner per workspace`, `40 to 100 ms`, `its author`, `live rehearsal`, and each of
     the links `docs/site/reference.md#hook-latency-budget`, `docs/site/rehearsal.md`,
     `docs/site/security.md`.
3. Leave `test_hero_shows_the_current_day`, `test_readme_first_day_and_shipped_areas` and
   `test_release_asset_ships_every_linked_doc` unchanged; the new text must keep them green.

### README.md

Write each paragraph below as given, then run it through the humanizer (embedded mode) or
the ten-line checklist; small wording changes are fine if the test phrases and facts stay.

1. Lead, inserted after line 15 (nav links), before `## What WUWEI is and is not`, as a plain
   paragraph:

   > WUWEI runs your coding agents the way a careful engineering team works. The day is
   > planned and ranked, and you approve the plan each morning. Every change is reviewed by
   > an agent that did not write it, merges follow your merge policy, and the day ends with
   > a retro that proposes changes to the rules.

2. Hero alt text (line 5), replace the value, keep the words the hero test needs:

   > WUWEI day loop. Calibration and the owner interview come before the first Plan. Each
   > day is planned and ranked, each item is built and checked, then reviewed by one gate or
   > three by tier, with one fix round. A shepherd takes each pull request to merge under the
   > merge policy, and Close runs a retro that carries the lessons into the next day. Guards
   > with a heartbeat check every action, and the owner answers decisions from the phone
   > through the DM.

3. `## How WUWEI compares` (lines 36-79), replace the intro, table, following paragraph and
   both subsections with:

   ```markdown
   ## How WUWEI compares

   As of October 2026. Each other tool is described from its own README or docs, and these
   projects change often, so follow the links. WUWEI puts its process in hooks that refuse
   at the moment of action, because a process written only as prompts is guidance a model
   can skip; it runs alongside the tools below.

   | Tool | Who plans the day | Who reviews the work | What stops a bad merge | What is learned afterwards | Where it runs |
   |---|---|---|---|---|---|
   | **WUWEI**, chartered roles that run a working day | A planner seat ranks the work and you approve it at the morning gate | One or three gates that did not write the change, then one fix round | Shipped hooks refuse at the moment of action; the merge policy and your branch protection decide | A daily retro: seats propose rule changes and you promote them | Claude Code, across your repositories, through `gh` |
   | [Spec Kit](https://github.com/github/spec-kit), a spec-driven development toolkit | You run specify, plan and tasks per feature, after a project constitution | Converge adds checklists and consistency analysis when you want them | Your repository rules | Specs and the constitution in the repository | Many coding agents through integrations |
   | [OpenSpec](https://github.com/Fission-AI/OpenSpec), spec-driven development for AI coding assistants | You propose a change and the agent writes its specs, design and tasks | An optional verify step | Your repository rules | Archiving a change updates the specs | 30+ coding tools |
   | [superpowers](https://github.com/obra/superpowers), composable skills loaded by a session-start hook | Brainstorming, then a plan of small tasks | Each task is reviewed for spec compliance, then code quality | Finishing a branch verifies tests, then you choose merge or PR | Plans and code in the repository | Claude Code, Codex, Cursor, Gemini CLI and others |
   | [BMAD Method](https://github.com/bmad-code-org/BMAD-METHOD), agile AI-driven development with agent personas | Analyst, product manager and architect agents write the brief, PRD and architecture | A code review skill with several independent reviewers | Your repository rules | A retrospective reviews each finished epic, and the loop goes back to planning | Coding tools that support skills; Claude Code and Codex plugins |
   | [Kiro](https://kiro.dev), an agentic IDE, CLI and web app by AWS | Specs with requirements, design and tasks | Your own review | Hooks you write; a PreToolUse hook can block a tool call | Steering files you write | Kiro IDE, CLI and web |
   | [Claude Code](https://code.claude.com/docs/en/overview) plan mode, subagents, hooks, memory | Plan mode proposes a plan before any edit | Subagents you define; automatic review on pull requests | Hooks you write; a PreToolUse hook can deny a tool call | `CLAUDE.md` and auto memory | Terminal, IDE, desktop app and web |

   WUWEI's roles are the planner, lead, builder, shepherd, steward and four sentinels
   ([concepts](docs/site/concepts.md)). It works through `gh` for the code host, with tracker
   and chat as optional adapters. Releases carry a signed manifest and an integrity check,
   and ZIRAN audits the role tool grants ([security](docs/site/security.md)).

   ### How they compose

   An item's spec can be written with Spec Kit or OpenSpec (this repository builds WUWEI with
   Spec Kit, see `specs/`), and a seat can run superpowers' skills inside its worktree.
   Claude Code's hooks, subagents, skills and plugins are what WUWEI is made of.
   ```

4. `## Limits`, inserted after the Quick start section, before `## Development installs`:

   ```markdown
   ## Limits

   - WUWEI needs Claude Code. Codex can run seats as an optional runtime.
   - One owner per workspace.
   - Hooks add about 40 to 100 ms to each tool call, depending on the machine
     ([hook latency budget](docs/site/reference.md#hook-latency-budget)).
   - It is early: so far only its author has used it day to day, and the
     [live rehearsal](docs/site/rehearsal.md) is the check before each release.

   What the guards cover, and what they leave to the code host, is in
   [security](docs/site/security.md).
   ```

### docs/site/index.md

Line 7, replace the second sentence:

> WUWEI 无为 means "effortless action." It is a Claude Code plugin that runs your coding
> agents the way a careful engineering team works: the day is planned and ranked, each
> change is reviewed by an agent that did not write it, merges follow a policy, and a retro
> at the end of the day proposes changes to the rules.

## What must not change

- The hero `<picture>` sources, `<h1>`, tagline and 无为 line; `#00C9A7` and every phrase
  `test_readme_install_and_hero` pins.
- `## What WUWEI is and is not`, `## What ships today` and their order before the comparison.
- `## Install`, `## Quick start`, `## Development installs`, `## Development` text.
- `scripts/build-hero.py`, `docs/assets/hero-*.svg` (their `<desc>` stays; regenerating is
  out of scope).
- `docs/site/security.md` and the design spec: the guard-scope statement stays there.
- The end of `README.md`, where #307 adds Acknowledgements; keep both on rebase.

## PR body (for whoever opens the PR)

Show the old table (`README.md:44-52` on `main`) and the new one, one after the other, and
list the URLs in `research.md` as the external claims re-checked on 2026-10-02.
