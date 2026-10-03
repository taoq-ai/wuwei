# Implementation Plan: Documentation system: a configured docs system with a docs obligation per tier checked at the gate and at close, and pages written from the records

**Branch**: `418-docs-system-spec` | **Date**: 2026-10-03 | **Spec**: [spec.md](spec.md)

## Summary

A spec-only change. The amendment to `docs/specs/2026-09-24-wuwei-design.md` is already in
the working tree, written by the spec author: one new subsection, `### 5.12 Documentation
system (owner, 2026-10-03, #418)`, placed after 5.9 and before section 6, plus one row
widened in the 4.1 hook table and one row added to the section 8 adapter table. The
builder shows the phrase check red on main and green here, reviews the wording against the
sections listed below, and runs the suite. No runtime code, no test changes.

## Technical Context

Markdown only. The verification check below is a throwaway stdlib script run from a
scratch directory, never committed (the issue's acceptance: only the spec changes). The
existing `tests/test_docs.py` reads the design spec only in
`test_guard_boundaries_are_stated_once` (4.5, 9.1, section 10), which this change does not
touch; `tests/test_docs.py` passes on the worktree (58 passed).

## Constitution Check

- I (stdlib), II (three-state exits), III (one behaviour, one function): no runtime code.
  The design keeps them for #419: HTTP adapters on stdlib `urllib` through the shared
  helper, every docs call exit 0, 1 or 2 with the reason, one CLI function per behaviour.
- IV (test first): the phrase check is run red against a `git archive main` export before
  the amendment is accepted, then green on the worktree. Red is never produced by stashing
  or reverting the working tree.
- V (ponytail): one subsection. No new mechanism where one exists: the draft queue and
  outward policy for approval, the recorded gate tier for the obligation, the `DOC` class
  for the sentinel finding, `closing.unresolved` for the close, the interview table for
  the question, the doctor row shape, `profiles.ABSOLUTE` for the path check. One `space`
  key serves both remote systems; updates append instead of merging; markdown reports are
  not published rather than inventing a repository for them.
- VII (security): no refusal is weakened. Remote writes are drafts unless the owner lists
  the kind in `auto`; the lint applies to both; credentials stay named and out of seat
  environments; the Notion and Atlassian MCP write tools join the outward tool patterns so
  the port is not the only door; `docs.written` and `docs.exempt` are CLI-only events. The
  `docs` value itself is a seat declaration, never trusted as an owner action.
- Governance: the design spec is amended only by its owner; the owner's evidence line is
  in the issue, and the owner merges. The constitution is unchanged (the issue asks for no
  constitution paragraph).

## What was changed (spec author, already in the working tree)

All in `docs/specs/2026-09-24-wuwei-design.md`:

1. 4.1 hook table: the PreToolUse outward row reads "chat, tracker or docs (5.12) adapter
   call".
2. New `### 5.12 Documentation system (owner, 2026-10-03, #418)` after 5.9, in the order of
   5.11's structure: configuration (`[docs]` keys and defaults), the docs obligation
   (value forms, who sets it, `light` exemption and `docs.exempt`), checks at two points
   (before the gate verdict, at close), writes (`docs page`, `docs publish`), approval and
   content (`auto` or draft, markdown never a draft, content rules, `docs.written`, MCP
   tool patterns), adapters (port operations, Notion, Confluence, markdown, none,
   credentials, contract test), setup, interview and doctor, owner-facing surfaces.
3. Section 8 adapter table: new row `docs (5.12) | read(ref), write(draft) | Notion
   (recommended), Confluence, repository Markdown`.

Net growth: 116 lines added, 1 removed.

## Design decisions the builder must check against the issue

- `docs.system` keeps the issue's key name and is the port's adapter selector; there is no
  `adapters.docs`. Schema default `none` (existing workspaces unchanged); Notion is the
  recommended answer in setup and the interview, matching "default when configured".
- Tiers are the effective gate tier recorded at the first gate dispatch, lowercase as
  `repos.gates.floor` and `dispatch.TIERS` spell them. The issue's `["STANDARD", "FULL"]`
  is the same set.
- The obligation is a declaration at the gate (no PR exists yet) and a write after the
  merge for remote systems, so the page links the merged PR. Markdown pages are written
  before the gate and travel in the PR.
- Value forms: `<page>` (exists, checked through `read`), `new`, `none, <reason>`.
- Gate: the quality brief carries the obligation; the sentinel files a blocking `DOC`
  finding for a missing or implausible value; `dispatch.receive` refuses a quality `PASS`
  while the value is missing. Close: four refusal cases, each naming its command;
  `strict_close = false` turns them into report lines.
- Approval reuses the outward policy at the port: the `docs` channel sends only kinds in
  `auto`, drafts the rest. Markdown is never a draft (its PR and gates are the review).
- Publishing: report and retro pages from named sections, once per kind per day; under
  markdown `publish` has no effect and doctor warns.

## Consistency review (builder)

Read these against 5.12 and edit only the design spec, only for a real conflict, keeping
the phrases the check pins:

- 3.4 (three-state exits, `none` adapters report unmeasured), 3.5 (ports: no abstract
  base class, a `none` adapter, a contract test), 4.3 and 4.8 (lint and voice apply to
  outward text), 4.9 (approve tier, drafts the owner approves), 5.1 and 5.3 (quality
  verdict rows, verdict shape), 5.2 (records written by the workflow, never by the owner
  by hand), 5.4 (the owner is asked only at the listed points: a docs draft is an owner
  approval like any other outward draft), 5.6 (unmeasured never counts as clean), section
  8 table, 9.1 (no local file is a trust anchor; the `docs` value is a declaration).
- The `DOC` class already exists in the verdict class sweep (`cli/wuwei/verdict.py:15`,
  `CLASSES`) and the builder charter (`charters/builder.md:26`); 5.12 reuses it.
- A grep of the design spec for `docs.exempt`, `docs.written`, `strict_close`,
  `required_tiers` and `NOTION_TOKEN` finds them only inside 5.12.

## What must not change

- Runtime and shipped text: `cli/`, `adapters/`, `hooks/`, `bin/`, `agents/`, `charters/`,
  `skills/`, `templates/`, `scripts/`, `.github/`, `docs/site/`, `README.md`.
- `tests/`: no file changes.
- `.specify/memory/constitution.md`: unchanged.
- Design 4.5, 9.1 and section 10: untouched, so `test_guard_boundaries_are_stated_once`
  keeps passing.
- Existing 5.x sections other than the two table rows: untouched. 5.10 and 5.11 are
  #411's and #416's; this branch does not add or renumber them.

## Verification commands

Run from the repository root. `<scratch>` is any directory outside the repository.

```sh
mkdir -p <scratch>/main && git archive main docs/specs | tar -x -C <scratch>/main
python3 <scratch>/check_418.py <scratch>/main   # must fail: AssertionError: section 5.12
python3 <scratch>/check_418.py .                # must print: OK: documentation system stated once
git diff --stat main -- cli adapters hooks bin agents charters skills templates scripts .github docs/site tests README.md .specify   # must be empty
python -m pytest -q
```

`<scratch>/check_418.py`:

```python
import re, sys
from pathlib import Path
spec = (Path(sys.argv[1]) / 'docs/specs/2026-09-24-wuwei-design.md').read_text()
flat = lambda text: ' '.join(text.split())
part = lambda pattern: flat((re.search(pattern, spec, re.S | re.M) or [''])[0])
docs = part(r'^### 5\.12 .*?(?=^## )')
hooks = part(r'^### 4\.1 .*?(?=^### )')
adapters = part(r'^## 8\. .*?(?=^## )')
assert docs, 'section 5.12'
for phrase in ('`docs.system = "none"` nothing in this section applies',
               '`notion`, `confluence`, `markdown`', 'The schema default is `none`',
               'recommend `notion` unless the repositories\' links point elsewhere',
               'refuses a name with no adapter under `adapters/docs/`',
               '`required_tiers` (default `["standard", "full"]`)', '`repos.gates.floor`',
               '`light` items are exempt by default', '`root` (default `docs`)',
               'for `confluence` it is the `https` link, which also names the site',
               '`publish` (default `["report", "retro"]`)', '`auto` (default `[]`)',
               '(`page`, `report`, `retro`)', 'every other write is a draft (4.9)',
               '`strict_close` (default `true`)',
               'recorded gate tier (written when `dispatch next` tiers it)',
               '`wuwei plan set <item> docs=<value>`', '`new`: a new page under `space`',
               '`none, <reason>`', 'refuses a page that does not exist',
               'The builder sets the value before it stands down',
               'never an owner approval', 'one `docs.exempt` event when it is tiered',
               'Before the gate verdict', 'under the `DOC` class',
               '`wuwei dispatch receive` refuses a quality `PASS` while the value is missing',
               'At close', 'no `docs.written` event for it since its merge',
               'has its docs draft still pending', 'names a path its merged PR did not change',
               '`wuwei drafts approve <id>`', 'With `strict_close = false` these are report lines',
               'keeps its obligation for the day it merges',
               '`wuwei docs page <item>` renders the item\'s page from its records',
               'what changed (the scope and the PR title)', 'how to use it (the PR body\'s',
               'links to the PR and the ticket (5.11)', 'appends a dated section',
               '`<root>/<item>.md`', 'goes out with the item\'s PR',
               '`wuwei docs publish report|retro`', 'once per kind per day',
               'Merged, Parked, Decisions answered, Carry and Docs sections',
               'Applied and Proposed sections', '`wuwei report` and `wuwei retro` publish',
               'Under `markdown`, `publish` has no effect',
               'a kind listed in `auto` is written at once', 'so it is never a draft',
               'no raw record (state, events, verdicts, decision files), no absolute path and no credential',
               'the renderer refuses rather than strips', 'one `docs.written` event',
               'written only by the CLI', 'Notion and Atlassian MCP write tools under channel `docs`',
               '`read(ref)` returns', '`write(draft)` creates a page under `draft.parent`',
               'otherwise appends to `draft.ref`', '`NOTION_TOKEN`',
               '`CONFLUENCE_EMAIL` and `CONFLUENCE_API_TOKEN`', 'next version number',
               'storage format', 'no credentials and no network',
               'docs port contract test with recorded fixtures', 'no test reaches the network',
               '"Where does your documentation live?"', 'README and CONTRIBUTING',
               '`notion.so` or `notion.site`', '`atlassian.net/wiki`', 'none found Notion leads',
               '`doctor` adds a docs row', '`read(space)` could not run or found no page',
               'configuration.md', 'glossary entries', 'daily.md',
               'The board and `wuwei next` show an item\'s unmet obligation',
               'Every docs write, `markdown` included, first goes through the humanizer pass (`[outward] humanize`, default true, #420)',
               'under `markdown`, a fail when `root` is not a directory in a configured repository',
               'Under `markdown`, `plan set` refuses `new`'):
    assert phrase in docs, phrase
assert 'chat, tracker or docs (5.12) adapter call' in hooks
assert '| docs (5.12) | `read(ref)`, `write(draft)` |' in adapters
whole = flat(spec)
for key in ('docs.exempt', 'docs.written', 'strict_close', 'required_tiers', 'NOTION_TOKEN'):
    assert whole.count(key) == docs.count(key) >= 1, key  # stated in 5.12 only
assert '\N{EM DASH}' not in spec
print('OK: documentation system stated once')
```

The spec author ran this check: red on the main export (`AssertionError: section 5.12`),
green on the worktree.

## Build map for #419 (same chain; recorded here so #419 needs no design decision)

Reuse, do not re-implement:

- Port registry: add `'docs': {'read': ('ref',), 'write': ('draft',)}` to
  `cli/wuwei/registry.py` `PARAMETERS`; load with
  `registry.load('docs', {'adapters': {'docs': config['docs']['system']}})`, the same
  substitution `registry.runtime_config` does.
- HTTP: extend `adapters/_http.py` `request` with a `method` keyword (default `'POST'`) so
  Notion `GET`/`PATCH` and Confluence `GET`/`PUT` share the bounded helper; keep
  `operation` and `credential` as they are.
- Outward policy at the port: decorate each adapter's `write` with
  `registry.outward_operation('docs')` and `_http.operation`, as `adapters/tracker/linear.py`
  `create` does. In `cli/wuwei/outward.py` `classify`, before the `kind not in ('chat',
  'slack')` branch (`:312`): for `kind == 'docs'` return `send` when the draft's `kind` is
  in `config['docs']['auto']`, else `draft`. Add `kind` and `parent` to `METADATA_FIELDS`.
- Draft queue: add `'docs': {'write'}` to `cli/wuwei/drafts.py` `OPERATIONS`; after a
  successful docs send in `drafts.approve`, record the item's value and the `docs.written`
  event through the same function `wuwei docs page` uses.
- Config: `"docs"` in `cli/wuwei/workspace.py` `SCHEMA` with `system` (`none`, `notion`,
  `confluence`, `markdown`), `required_tiers` (each in `dispatch.TIERS`), `space`, `root`
  (relative literal path), `publish` (subset of `report`, `retro`), `auto` (subset of
  `page`, `report`, `retro`), `strict_close`; the `[docs]` table in
  `templates/workspace/config.toml`; the Notion and Atlassian MCP write patterns in the
  default `outward.tool_patterns` with channel `docs`.
- Credentials: `NOTION_TOKEN`, `CONFLUENCE_EMAIL`, `CONFLUENCE_API_TOKEN` in
  `cli/wuwei/env.py` `CREDENTIALS`.
- Value: `wuwei plan set <item> docs=<value>` in `cli/wuwei/commands/plan.py`; if `plan
  set` already exists from #412 or #417 when #419 is built, add the `docs` key to it. The
  item key `docs` gets its producer in `cli/wuwei/state.py` `_producer_error` (`wuwei plan
  set or wuwei docs page`).
- Exemption event: written in `cli/wuwei/dispatch.py` `next_step` right after the
  `gate.tiered` write (`:172-178`) when the tier is outside `required_tiers` and the system
  is not `none`.
- Gate: `cli/wuwei/brief.py` `write` adds one `Docs:` header line to quality gate briefs
  (and the obligation to builder briefs); `cli/wuwei/dispatch.py` `receive` refuses a
  quality `PASS` (base role `quality`, first or second opinion) while the value is missing,
  naming `plan set <item> docs=...`. One step in `charters/sentinel-quality.md` and one in
  `charters/builder.md`.
- Close: the four cases in `cli/wuwei/closing.py` `unresolved`, inside the existing
  approved-items loop, using its PR rows for "merged" and `code_host.files(ref)` for the
  markdown path; `strict_close = false` moves them to a `## Docs` section that
  `cli/wuwei/report.py` `build` adds (the `none` reasons always appear there).
- Content check: `cli/wuwei/profiles.py` `ABSOLUTE` for absolute paths; credential values
  through `cli/wuwei/redact.py`.
- New code, one module each: `cli/wuwei/docs.py` (render, value, write, publish),
  `cli/wuwei/commands/docs.py` (`docs page`, `docs publish`), `adapters/docs/notion.py`,
  `adapters/docs/confluence.py`, `adapters/docs/markdown.py`, `adapters/docs/none.py`;
  contract test and recorded fixtures under `tests/`.
- Setup, interview, doctor: a `docs` row in `cli/wuwei/interview.py` `QUESTIONS` (choices
  Notion, Confluence, Markdown, None; free text a page link); link detection in
  `cli/wuwei/commands/setup.py` `discover`; a docs row in `cli/wuwei/commands/doctor.py`.
- Owner docs: `docs/site/configuration.md`, the glossary, `docs/site/daily.md`,
  `docs/site/reference.md` (the doc tests require every config key and command to be
  documented).
