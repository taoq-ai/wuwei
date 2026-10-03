# Tasks: Documentation system

Test first: write each test task, run it with `python -m pytest -q <file>` from the repository
root, see it fail for the stated reason, then do the implementation task that follows it.
Signatures, texts and shapes are in plan.md and contracts/docs-port.md. No test reaches the
network: adapters replay `tests/fixtures/docs/recordings.json` through a patched
`urllib.request.urlopen` (reuse `replay`/`Reply` from `tests/test_reference_adapters.py`, adding
`request.get_method()` to each recorded call). Neutral names only in fixtures.

## Phase 1: Config and the port (US5, US6, FR-001, FR-002)

- [X] T001 In `tests/test_workspace.py`, add a failing test: a default config has
  `config['docs'] == {'system': 'none', 'required_tiers': ['standard', 'full'], 'space': '',
  'root': 'docs', 'publish': ['report', 'retro'], 'auto': [], 'strict_close': True}` and
  `config['adapters']['docs'] == 'none'`; `[docs] system = "wiki"` raises `ConfigError` whose
  text names `docs.system` and `notion`; `required_tiers = ["huge"]` and `auto = ["dm"]` raise;
  `templates/workspace/config.toml` still loads. Fails today: `KeyError: 'docs'`.
- [X] T002 In `cli/wuwei/workspace.py`, add `SCHEMA["docs"]`, the derived
  `config['adapters']['docs']`, the `docs.system` naming in the adapter loop, and
  `CONFIG_CACHE_VERSION = 2`.
- [X] T003 In `tests/test_adapters.py`, add `('docs', 'read', ('ref',), True)` and
  `('docs', 'write', ('draft',), False)` to `CALLS`. Fails today: `test_module_contracts`
  (`registry.INTERFACES` has no `docs`), `test_none_call[docs-*]` (no `adapters.docs.none`) and
  `test_registry_loads_config_selection` (`'none' not in known('docs')`).
- [X] T004 In `cli/wuwei/registry.py`, add `PARAMETERS['docs']`; create `adapters/docs/none.py`
  (`read`, decorated `write`) per the contract.
- [X] T005 In `tests/test_docs_port.py` (new), add the failing port contract test,
  parametrized over `notion`, `confluence` and `markdown`: `read(ref)` returns exactly the keys
  `id`, `title`, `link`, `updated`; `write` with `ref=''` creates and with a `ref` appends, each
  returning `id` and `link`; for notion and confluence assert each recorded call's method, URL
  and JSON body (GET read, POST create, PATCH or PUT append with `version.number` + 1) and that
  the credential is in the `Authorization` header; call the remote `write` as
  `write.__wrapped__` (below the outward port, as `drafts.approve` does).
  Add: an error body (`{"object": "error"}` / a 500 status) is exit 2 with no provider text in
  the reason; a missing credential is exit 2 and `urlopen` is never called; markdown refuses a
  symlink target (exit 2) and returns exit 1 for a missing file; `registry.known('docs') ==
  ['confluence', 'markdown', 'none', 'notion']`. Fails today: `ModuleNotFoundError`.
- [X] T006 In `adapters/_http.py`, add `method` and an optional `payload` to `request`. Create
  `tests/fixtures/docs/recordings.json`, `adapters/docs/notion.py`,
  `adapters/docs/confluence.py` and `adapters/docs/markdown.py` per contracts/docs-port.md.
- [X] T007 In `tests/test_outward.py` `test_every_free_text_adapter_write_goes_through_the_port`,
  allow a per-adapter exemption `('docs', 'write', 'markdown')` with the reason "a file in the
  item's pull request; docs.page runs outward.humanize_lint". Without it the test fails on
  `('docs', 'markdown', 'write')`; with it notion, confluence and none are checked.

## Phase 2: Outward policy and the draft queue (US2, FR-007)

- [X] T008 In `tests/test_outward.py`, add failing tests for `outward.classify(..., kind='docs')`
  on a configured workspace: `{'draft': {'kind': 'page', 'item': 'X', 'title': 'T', 'body':
  'Adds a flag.', 'parent': 'p', 'ref': ''}}` returns `(1, 'draft')` by default and `(0, 'send')`
  with `docs.auto = ["page"]`; a body with a sensitive keyword (`salary`) drafts even under
  `auto`. Fails today: `_text` raises on `kind` (exit 2) and the docs kind always drafts.
- [X] T009 In `cli/wuwei/outward.py`, add `kind` and `parent` to `METADATA_FIELDS` and the `docs`
  branch in `classify`.
- [X] T010 In `tests/test_drafts.py`, add a failing test: calling the notion `write` port
  (unwrapped HTTP replaced by a sink) on a docs draft stores one pending row with channel `docs`,
  operation `write`, `item` from the draft and destination the draft's `parent`; `drafts.read`
  accepts it. Fails today: `drafts: unsupported operation`.
- [X] T011 In `cli/wuwei/drafts.py`, add `OPERATIONS['docs']` and the `ref`/`parent` destination
  fallback.
- [X] T012 In `tests/test_workspace.py` (or `tests/test_outward.py` next to the MCP guard tests),
  add a failing test: the default `outward.tool_patterns` map a `mcp__notion__notion-create-pages`
  and a `mcp__atlassian__createConfluencePage` tool to channel `docs`, and not
  `mcp__atlassian__createJiraIssue`. Fails today: no docs rows.
- [X] T013 In `cli/wuwei/workspace.py`, add the two `tool_patterns` rows.

## Phase 3: The obligation, the gate and the value (US1, FR-003 to FR-005, FR-009)

- [X] T014 In `tests/test_docs_system.py` (new), add failing tests for `docs.required`,
  `docs.unmet` and `docs.shown` over rows with tiers `light`, `standard`, `full`, none recorded,
  with and without a value, under `none` and `notion`. Fails today: `ModuleNotFoundError:
  wuwei.docs`.
- [X] T015 Create `cli/wuwei/docs.py` with `required`, `unmet`, `shown` and `COMMAND`.
- [X] T016 In `tests/test_docs_system.py`, add failing tests for `bin/wuwei plan set` through
  `python3 -P -m wuwei` once and `docs.assign` in process otherwise, on a gate-approved day
  under notion (a fake docs adapter via `monkeypatch` of `registry.load` for `docs`):
  `docs=none --reason "internal refactor"` records `items.X.docs == {'value': 'none', 'reason':
  'internal refactor'}` and one `docs.set` event, exit 0; `docs=none` without a reason is exit 1;
  an unknown item is exit 1; `docs=<page>` whose read returns exit 1 is exit 1 and exit 2 is
  exit 2, recording nothing; `docs=new` records `new`; `ticket=1` is exit 2; under `none` exit 1.
  Under markdown: `docs=new` is exit 1 naming `bin/wuwei docs page X`; `docs=../x.md` and
  `docs=other/x.md` are exit 1; `docs=docs/x.md` with the file in the item's worktree records it.
  Fails today: `invalid choice: 'set'`.
- [X] T017 Implement `docs.assign`, the `set` verb in `cli/wuwei/commands/plan.py`, `plan set` in
  `cli/wuwei/commands/__init__.py` `WRITES`, and the `docs` entry in `state._producer_error`.
- [X] T018 In `tests/test_dispatch.py`, using its `root` fixture, add failing tests: with
  `docs.system = "notion"`, the first gate `dispatch next` of a LIGHT item (no flags, a small
  diff, floor `light`) records exactly one `docs.exempt` event `{'item', 'tier': 'light'}` and a
  second `dispatch next` records none; a STANDARD item records none; under `none` no event.
  Fails today: no event.
- [X] T019 Implement `docs.exempt` and call it in `dispatch.next_step` after `gate.tiered`.
- [X] T020 In `tests/test_brief.py`, add failing tests: under notion a `sentinel-quality` brief
  for a standard item with no value has the `Docs: required (tier standard); value missing`
  header line naming `bin/wuwei plan set X docs=`; with `none` recorded it shows the value and
  reason; a light item shows `Docs: not required (tier light).`; a builder brief has the
  builder line; an arch brief and every brief under `none` have no `Docs:` line. Fails today: no
  line.
- [X] T021 Implement `docs.brief_line` and the one call in `cli/wuwei/brief.py` `write`.
- [X] T022 In `tests/test_dispatch.py`, add failing tests (issue acceptance 1): under notion a
  standard item with no value: a quality `PASS` verdict is refused naming `plan set X docs=`; a
  quality `FIX` verdict whose class line has `DOC: PASS` is refused; a quality `FIX` with
  `DOC: FINDING` and a blocking finding is recorded; after `docs.assign(X, 'none', 'internal
  refactor')` the `PASS` is recorded; a LIGHT item's `PASS` is recorded with no value; an arch
  `PASS` is never checked; under `none` nothing changes. Fails today: the PASS is recorded.
- [X] T023 Add the check in `dispatch.receive`.
- [X] T024 In `tests/test_state.py` (next to the reserved-field tests), add a
  failing test: `wuwei event docs.written {}`, `docs.exempt` and `docs.set` exit 1 naming their
  producer, and a generic `state set items.X.docs` is refused naming `wuwei plan set or wuwei
  docs page`. Fails today: both reasons say `its dedicated command`.
- [X] T025 Add the three kinds to `EVENT_PRODUCERS` in `cli/wuwei/commands/event.py`.

## Phase 4: Writing pages (US2, US3, FR-007)

- [X] T026 In `tests/test_docs_system.py`, add failing tests for `docs.render` and `docs.check`:
  a day with `proposal.json` (scope `Add a dry-run flag\nSecond line`, evidence), `goals.md`
  with the item's goal, `items.X.pr`, a fake code host whose `pr` returns `title`, `body` with a
  `## How to use` section and `url`, and `tickets.X.id = 'ABC-1'`: title is `X: Add a dry-run
  flag`; the body has `### What changed`, the PR title, `Goal: <outcome>`, the evidence, the How
  to use text, `- Pull request: <url>` and `- Ticket: ABC-1`; without a PR or ticket the Links
  section is omitted; without a scope it raises `StateError`. `check` raises on
  `/opt/x/y`, `~/x`, `C:\x`, `.wuwei/days`, `state.json`, `events.jsonl` and a loaded
  credential value (`redact.VALUES`), and accepts `https://example.com/a/b` and `docs/x.md`.
  Fails today: no functions.
- [X] T027 Implement `docs.render` and `docs.check`; in `adapters/code_host/github.py` `pr`, add
  `title` and `body`, and update `tests/fixtures/code_host/recordings.json` and any test that
  compares a whole `pr()` dict.
- [X] T028 In `tests/test_docs_system.py`, add failing tests (issue acceptance 2) for
  `wuwei docs page X` under notion with the recorded fixture: one pending docs draft whose body
  holds the summary, PR and ticket links and no absolute path (assert the worktree path and the
  workspace root are absent), the item value becomes `new`, no `urlopen` call, exit 0 with the
  message naming `wuwei drafts approve <id>`; with `auto = ["page"]` one POST is replayed, one
  `docs.written` event `{'item': 'X', 'kind': 'page', 'adapter': 'notion', 'page': <url>,
  'draft': None}` is recorded and the value becomes the page URL; with a value set to a page the
  draft is an append whose body starts with `## <date>`; a page with an absolute path in its
  evidence is exit 1 and stores nothing; value `none` is exit 1; under `none` exit 2 with an
  `adapter: none` event. Fails today: `invalid choice: 'docs'`.
- [X] T029 Implement `docs.page`, `docs._outcome`, `docs.record` and
  `cli/wuwei/commands/docs.py`; add `docs page` and `docs publish` to `WRITES` and `docs` to the
  Daily group in `cli/wuwei/__main__.py`.
- [X] T030 In `tests/test_drafts.py`, add a failing test: approving a pending docs draft (host
  confirmation and the notion HTTP replay patched as the existing approve tests patch them)
  sends once, records one `docs.written` event carrying the draft id, and sets a `new` value to
  the page link. Fails today: no event.
- [X] T031 Call `docs.record` from `drafts.approve` after a sent docs draft.
- [X] T032 In `tests/test_docs_system.py`, add failing tests (issue acceptance 4) under
  markdown: an item with a git-free worktree directory under `tmp_path`: `docs page X` writes
  `<worktree>/docs/X.md` starting with `# X: ...`, records the value `docs/X.md` and one
  `docs.written` event whose `page` is relative, creates no draft; a second run appends a
  `## <date>` section and keeps the first text; an item without a worktree is exit 1; with
  `outward.humanize_strict = true` a body with a tell is exit 1 and writes nothing. Fails today:
  no markdown path in `docs.page`.
- [X] T033 Implement the markdown branch of `docs.page`.

## Phase 5: Close and report (US1, US2, US3, FR-006)

- [X] T034 In `tests/test_docs_system.py`, add failing tests for `docs.findings`/`docs.close` on
  a day whose state has merged items (written through `state._write_state` so a `phase_changes`
  merged event exists): under notion a standard item with no value gives one line naming
  `bin/wuwei plan set X docs=` and `close` returns `(1, ...)`; value `none` gives none; value `new`
  with a pending docs draft names `bin/wuwei drafts approve <id>`; value `new` with no
  `docs.written` after the merge (one before it) names `bin/wuwei docs page X`; with one after the
  merge, none; a light item and an unmerged item give none; under markdown a value not in the
  fake code host's `files(pr)` names the path and one in it gives none; a code-host failure is
  `(2, 'docs unmeasured: ...')`; `strict_close = false` returns `(0, '')`; under `none`
  `(0, '')`. Fails today: no functions.
- [X] T035 Implement `docs.findings` and `docs.close`.
- [X] T036 In `tests/test_close_branches.py` (or `tests/test_report_retro.py` where close runs
  end to end), add a failing test that `closing.check` includes the docs line and exits 1 for
  an unmet standard item, and exits 0 for it after `docs.assign(..., 'none', reason)`. Fails
  today: close passes.
- [X] T037 Append `docs.close(root)` to the results in `closing.check`.
- [X] T038 In `tests/test_report_retro.py`, add failing tests: under notion, `report.build` has
  `## Docs` with `- X: none (internal refactor)` (issue acceptance 1) and `- Y: missing`; with
  `strict_close = false` the finding lines follow; under `none` there is no `## Docs` section and
  the existing report tests are unchanged. Fails today: no section.
- [X] T039 Implement `docs.report_lines` and the `## Docs` section in `report.build`.

## Phase 6: Publishing (US4, FR-008)

- [X] T040 In `tests/test_docs_system.py`, add failing tests (issue acceptance 3): under notion
  with `publish = ["report"]`, `wuwei report` prints the report and one line naming a stored
  draft whose title is `Report <date>` and whose body holds exactly the Merged, Parked,
  Decisions answered, Carry and Docs sections; a second `wuwei report` names the first draft and
  stores no second; `publish = []` stores none; `wuwei docs publish retro` after `wuwei retro`
  stores a `Retro <date>` draft with Applied and Proposed; under markdown `docs publish report`
  is exit 0 with `no effect under markdown` and stores nothing; without `report.md` it is exit 1.
  Fails today: no publish.
- [X] T041 Implement `docs.publish` and the calls in `cli/wuwei/commands/report.py` and
  `cli/wuwei/commands/retro.py`.

## Phase 7: Board, next, setup, interview, doctor, config check (US6, US7, FR-010)

- [X] T042 In `tests/test_next.py`, add a failing test: under notion a standard item at `gate`
  with no value gives the `docs` row whose command starts `wuwei plan set X docs=`; with a value
  the `verdicts` row returns; under `none` the `verdicts` row. In `tests/test_board_mcp.py`, the
  Work table has a `Docs` column showing `missing`. Fails today: no row, no column.
- [X] T043 Add the `docs` row to `cli/wuwei/commands/next.py` (lazy import) and the column to
  `cli/wuwei/commands/board.py`.
- [X] T044 In `tests/test_interview.py`, add failing tests: the `docs` question exists with
  choices Notion, Confluence, Markdown, None mapping `docs.system`; the answer
  `https://example.atlassian.net/wiki/spaces/DOCS/pages/1/Home` maps to
  `{'docs.system': 'confluence', 'docs.space': <link>}` and a `notion.so` link to notion; other
  text is refused; `ask(['docs'], [], defaults={'docs': <link>})` with an empty reply records the
  link. In `tests/test_docs_system.py`, `docs.detect` finds a Confluence link in a repository
  README before a Notion link in a later CONTRIBUTING, and returns `None` with none. In
  `tests/test_setup.py`, setup passes the detected link as the docs default. Fails today: unknown
  question `docs`.
- [X] T045 Implement the interview row, `_docs_link`, `ask(..., defaults=None)`, `docs.detect`
  and the setup call.
- [X] T046 In `tests/test_doctor.py`, add failing tests for the `docs` row: `none` ok `not used`;
  notion with empty space fail naming `docs.space`; notion with space and no `NOTION_TOKEN`
  fail naming it; notion with a fake read returning exit 2 fail; notion read ok gives ok;
  markdown with `root` missing in every repository fail; markdown with the directory and
  default `publish` warn naming `docs.publish`; markdown with `publish = []` ok. In
  `tests/test_env_credentials.py` (where the config check credential tests live), `config check`
  under notion without `NOTION_TOKEN` prints `docs.notion: NOTION_TOKEN: missing` and exits 1,
  and the three new variables are kept out of `env.child_environment()`. Fails today: no row, no requirement, variables passed to seats.
- [X] T047 Implement `doctor._docs`, the `requirements` entries and `env.CREDENTIALS`.
- [X] T048 In `tests/test_hooks.py` (or `tests/test_owner_actions.py`), add a test that a seat's
  Bash payload `bin/wuwei plan set X docs=none --reason "no docs change"` inside the workspace is
  not refused by the PreToolUse guards (exit 0). It passes on this branch and fails if a merge
  makes every `plan set` owner-only (see plan.md merge notes); run it to confirm it passes.

## Phase 8: Charters, template and site (FR-010)

- [X] T049 In `tests/test_charters.py`, add a failing test that `charters/sentinel-quality.md`
  has a step naming `Docs:`, `DOC: FINDING` and documented behaviour, and `charters/builder.md`
  a rule naming `Docs:` and `bin/wuwei docs page`. In `tests/test_docs.py`, append
  `('Docs system', r'docs systems?')` and `('Docs obligation', r'docs obligations?')` to
  `GLOSSARY` and add a test that `configuration.md` names `[docs]` and each `docs.<key>`,
  `reference.md` has rows for `bin/wuwei docs page`, `bin/wuwei docs publish` and
  `bin/wuwei plan set <item> docs=`, `daily.md` mentions the docs obligation, and `adapters.md`
  lists `NOTION_TOKEN`, `CONFLUENCE_EMAIL` and `CONFLUENCE_API_TOKEN`. Fails today: none present.
- [X] T050 Edit the two charters, run `bin/wuwei agents build` to regenerate `agents/`, add the
  commented `[docs]` table to `templates/workspace/config.toml`, and edit
  `docs/site/configuration.md`, `concepts.md`, `daily.md`, `reference.md` and `adapters.md`.

## Phase 9: Whole suite

- [X] T051 Run `python -m pytest -q`; fix what the new list entries break (adapter `CALLS`,
  interview ids, default `tool_patterns`, template keys, `pr()` dicts, glossary links). Check
  every file written for em dashes, emojis, absolute local paths and engagement names.

## Build notes

- T016, T026 to T041: the close, report and publish tests live in `tests/test_docs_system.py` next
  to the shared day fixture instead of `tests/test_close_branches.py` and `tests/test_report_retro.py`.
- T033: the markdown branch landed with T029; its tests (T032) were written after and passed on
  first run.
- T049: `tests/test_charters.py::test_pre_review_class_sweep` counted every mention of a class
  code; it now counts the `Independently check` line, since the quality charter names
  `DOC: FINDING` for the docs obligation while arch still owns the DOC class check.
- T051: `tests/test_signal_status.py` pins every emitted event kind; `docs.set`, `docs.written`
  and `docs.exempt` are silent in `signal.SILENT`.
