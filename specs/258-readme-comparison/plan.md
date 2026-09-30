# Implementation Plan: README comparison with other ways to run coding agents

**Branch**: `258-readme-comparison` | **Spec**: `specs/258-readme-comparison/spec.md`

## Summary

One new README section between "What WUWEI is and is not" and "Install", and one docs test
in `tests/test_docs.py` that pins it. No runtime code, no docs site change.

## Technical Context

Markdown plus one pytest function using only what `tests/test_docs.py` already imports
(`re`, `ROOT`). Nothing under `cli/`, `adapters/`, `hooks/`, `docs/site/` or `.github/`
changes.

## Constitution Check

- III One behaviour, one test: one test function covers the section.
- IV Test first: the test is written and seen failing (no heading) before the README edit.
- V Ponytail: no new docs page, no helper, no fixture; the section reuses existing pages by
  link instead of restating them.
- Constraints: no em-dashes, no emojis.

## Changes

### 1. Docs test (`tests/test_docs.py`)

New `test_readme_compares_with_other_tools`, placed directly after
`test_readme_install_and_hero` (not at the end of the file, where parallel branches keep
colliding). It:

- reads `README.md`; takes `section = readme.split('## How WUWEI compares', 1)[1].split('\n## ', 1)[0]`
  after asserting the heading is present;
- asserts `readme.index('## What WUWEI is and is not') < readme.index('## How WUWEI compares') < readme.index('## Install')`;
- asserts `re.search(r'As of [A-Z][a-z]+ \d{4}', section)` (date form, not a fixed month);
- asserts each of `'Spec Kit'`, `'OpenSpec'`, `'superpowers'`, `'BMAD Method'`, `'Kiro'`,
  `'Claude Code'` is in the section, and each link target
  `github.com/github/spec-kit`, `github.com/Fission-AI/OpenSpec`, `github.com/obra/superpowers`,
  `github.com/bmad-code-org/BMAD-METHOD`, `kiro.dev`, `code.claude.com/docs` is in it;
- asserts `'### How they compose'` and `'### Where WUWEI is worse'` are in the section, and
  that the "worse" part (`section.split('### Where WUWEI is worse', 1)[1]`, whitespace
  joined) contains `'only in Claude Code'`, `'one owner per workspace'`, `'40 to 100 ms'`,
  `'not an isolation boundary'`, `'proven only by'`, `'live rehearsal'`;
- asserts `len(section.splitlines()) < 70` and that U+2014 (em-dash, written as a `\N{EM DASH}` escape in the test source) is not in the section.

### 2. README section (`README.md`, inserted after line 21, before `## Install`)

Shape, under 70 lines:

- `## How WUWEI compares`
- One sentence: "As of September 2026. Each line describes the tool from its own README or
  docs; they move fast, so check the links." Then one sentence of WUWEI's stance: process
  written as prompts or skills is guidance a model can skip, so WUWEI anchors its process in
  hooks that refuse at the moment of action, and it keeps using the tools below.
- Table, six columns: `Tool | What it does | Layer | Unit of work | Enforcement | State`.
  Rows in this order, cells taken from `research.md` (re-check each URL first):
  1. `[Spec Kit](https://github.com/github/spec-kit)`: constitution once, then specify,
     plan, tasks, implement per feature; many agents through integrations | method and
     prompts | one feature | the agent follows the commands and templates | Markdown in the
     repository.
  2. `[OpenSpec](https://github.com/Fission-AI/OpenSpec)`: change folders (proposal, specs
     with added requirements, design, tasks); propose, apply, archive; 30+ tools | method
     and prompts | one change | the agent follows the commands | `openspec/` in the
     repository.
  3. `[superpowers](https://github.com/obra/superpowers)`: composable skills
     (brainstorming, plans, TDD, debugging, subagent-driven development), loaded by a
     session-start hook; Claude Code, Codex, Cursor and others | method and prompts | one
     task or branch | the agent checks for a relevant skill before each task | plans and
     code in the repository.
  4. `[BMAD Method](https://github.com/bmad-code-org/BMAD-METHOD)`: agent personas
     (analyst, product manager, architect, developer, UX designer) and documents (brief,
     PRD, architecture, epics and stories) | method and prompts | one change or project,
     sized to scope | the agent follows the skills | documents in the repository.
  5. `[Kiro](https://kiro.dev)`: AWS agentic IDE, CLI and web; specs as requirements,
     design and tasks; hooks on file, tool and agent events | its own agent runtime | one
     spec | hooks, including PreToolUse hooks that can block a tool call | spec files in
     the project.
  6. `[Claude Code](https://code.claude.com/docs/en/overview)` plan mode, subagents, hooks,
     memory: plan before edits, subagents in their own context, hooks that can deny a tool
     call, `CLAUDE.md` and auto memory | runtime | one session | the hooks you write |
     `CLAUDE.md` and auto memory.
  7. WUWEI: chartered roles run a working day | runtime (Claude Code hooks and a CLI) | a
     day across repositories: plan, seats, gates, PR, decisions, retro | hooks refuse at
     the moment of action and give the reason | producer-only state and events under
     `.wuwei/`, written only by the CLI.
  No pipes inside cells; nothing in a cell rates the tool.
- Paragraph (the remaining axes, WUWEI only, no claims about the others): roles and gates
  (planner, lead, builder, shepherd, steward, four sentinels; three parallel review gates
  and one fix round), integration (`gh` for the code host; tracker and chat through
  optional adapters), security (signed release manifest and integrity check, ZIRAN audit
  of role tool grants), and the retro-to-charter loop (seats propose, `wuwei promote`
  lands the change, a ledger traces it). Links: `docs/site/concepts.md`,
  `docs/site/security.md`.
- `### How they compose`: FR-004 content. WUWEI is the loop and the enforcement, not a
  spec format; an item's spec can be written with Spec Kit or OpenSpec (this repository
  builds WUWEI with Spec Kit, see `specs/`); a seat can run superpowers' skills inside its
  worktree; Claude Code's hooks, subagents, skills and plugins are what WUWEI is made of.
- `### Where WUWEI is worse`: FR-005 content, using the pinned phrases verbatim:
  heavier to set up (signed asset, `init`, config, owner actions in a host terminal); runs
  only in Claude Code (Codex is an optional seat runtime); one owner per workspace; hooks
  add 40 to 100 ms per tool call depending on hardware (link
  `docs/site/reference.md#hook-latency-budget`); guards are cooperative mistake
  prevention, not an isolation boundary (link `docs/site/security.md`); proven only by its
  author's own use so far, and the live rehearsal is the release criterion (link
  `docs/site/rehearsal.md`).

Relative links only to files already in the release manifest (`docs/site/*.md`); `specs/`
is not shipped, so name it in backticks, do not link it. Do not put "planned" on a line
that mentions a manifest (existing test). Avoid "state the model cannot forge": design 9.1
says a process running as the owner can forge any local file.

## Must not change

`docs/site/`, the design spec, the constitution, `test_readme_install_and_hero`,
`test_release_asset_ships_every_linked_doc`, and every other test and code file.
