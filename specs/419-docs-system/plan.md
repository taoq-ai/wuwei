# Implementation Plan: Documentation system

**Branch**: `419-docs-system` | **Spec**: [spec.md](spec.md) | **Issue**: #419 | **Design**: 5.12

## Summary

One new core module, `cli/wuwei/docs.py`, holds every docs decision (obligation, value, render,
write, publish, close lines, report lines, brief line, link detection). One new command module,
`cli/wuwei/commands/docs.py` (`docs page`, `docs publish`). One new port kind, `docs`, with four
adapters under `adapters/docs/`. Everything else is one call or one row at an existing shared
spot: the derived `config['adapters']['docs']` makes the registry, the draft queue and the config
check work unchanged; `outward.classify` gains one `docs` branch so `registry.outward_operation`
drafts or sends docs writes like every other port; `drafts.approve` records `docs.written` after a
sent docs draft. With `docs.system = "none"` (the schema default) every new call returns early.

## Technical Context

- Python 3.11+ stdlib only (`urllib`, `base64`, `html`, `json`, `re`). pytest for tests, run
  `python -m pytest -q` from the repository root.
- No network in tests: adapters replay recorded responses through a patched
  `urllib.request.urlopen` (reuse `replay` and `Reply` from `tests/test_reference_adapters.py`,
  adding the request method to each recorded call).
- Hook latency (#346): `commands/next.py` runs at SessionStart. `docs.py` imports only `json`,
  `re`, `pathlib`, `wuwei.state` and `wuwei.workspace` at module level; `registry`, `brief`,
  `goals`, `outward`, `drafts`, `watch` and `redact` are imported inside the functions that use
  them. `next.step` imports `docs` inside the loop branch that needs it.

## Constitution Check

- I stdlib only: yes; adapters use the shared `adapters/_http.py`.
- II three-state exits: every adapter call returns `Result(0|1|2)`; `docs page`, `docs publish`
  and `plan set` exit 1 on a refusal (`state.StateError`) and 2 on could-not-run; close reports
  `docs unmeasured: <reason>` as exit 2.
- III one behaviour, one function: each behaviour below lives in one function of `docs.py`;
  callers are one line.
- IV test first: tasks.md orders every test before its implementation.
- V ponytail: no new policy engine, no docs-only lint, no new code-host operation, no new state
  writer; reuses `outward_operation`, `drafts`, `state._write_state`, `watch.records`,
  `brief.read`, `redact.redact`, `workspace.atomic_write`, `registry.record_none`.
- VII security: credentials only in `.wuwei/env` and `env.CREDENTIALS` (kept out of seats); pages
  refuse absolute paths, `.wuwei/` paths and loaded credentials; `docs.written`, `docs.exempt`
  and `docs.set` and the item `docs` field have CLI producers only.

## Data

- Config `[docs]` (FR-001), in `SCHEMA` after `"tracker"`:

  ```python
  "docs": {"system": (str, "none"),
           "required_tiers": [(str, None, ("light", "standard", "full")), ["standard", "full"]],
           "space": (str, ""), "root": (str, "docs"),
           "publish": [(str, None, ("report", "retro")), ["report", "retro"]],
           "auto": [(str, None, ("page", "report", "retro")), []],
           "strict_close": (bool, True)},
  ```

- Item field: `items.<item>.docs = {"value": "<page id, link or markdown path>" | "new" | "none",
  "reason": "<one line>"}`, written only by `docs.assign` and `docs.record` through
  `state._write_state(..., reserved=False)`.
- Events (all CLI-only, reserved in `commands/event.py` `EVENT_PRODUCERS`):
  - `docs.set` `{item, value, reason}`: `plan set` or `docs page` recording a value;
  - `docs.written` `{item, kind, adapter, page, draft}` (`draft` is the draft id or `None`;
    `item` is `None` for report and retro): every write, as the `_write_state` event that also
    records the value when one changes;
  - `docs.exempt` `{item, tier}`: once, when `dispatch next` tiers an item outside
    `required_tiers`.
- Draft rows: channel `docs`, operation `write`, `inputs = {"draft": {kind, item, title, body,
  parent, ref}}`; `row['item']` comes from `draft.item` as for tracker drafts.

## Port contract

See [contracts/docs-port.md](contracts/docs-port.md) for `read(ref)`, `write(draft)` and the HTTP
calls each adapter makes (what the recorded fixtures hold).

## Changes

### Config and registry

- `cli/wuwei/workspace.py`
  - `SCHEMA["docs"]` as above.
  - `SCHEMA["outward"]["tool_patterns"]` default: two rows, channel `docs`:
    `r"mcp__.*notion.*__.*(create|update|append|patch|post|move|duplicate).*"` and
    `r"mcp__.*atlassian.*__(create|update)Confluence.*"` (Confluence only, so a Jira tool is not
    claimed).
  - `load_config`: right after `_validate`, `config['adapters']['docs'] = config['docs']['system']`
    so the existing adapter loop validates it. In that loop, for `kind == 'docs'` look the line up
    at `('docs', 'system')` and name `docs.system` (not `adapters.docs`) in the `ConfigError`.
  - `CONFIG_CACHE_VERSION = 2` (the schema and the derived key change).
- `cli/wuwei/registry.py`: `PARAMETERS['docs'] = {'read': ('ref',), 'write': ('draft',)}`.
- `cli/wuwei/env.py`: add `NOTION_TOKEN`, `CONFLUENCE_EMAIL`, `CONFLUENCE_API_TOKEN` to
  `CREDENTIALS`.
- `cli/wuwei/commands/config.py` `requirements`: `('docs', 'notion'): [('NOTION_TOKEN',)]`,
  `('docs', 'confluence'): [('CONFLUENCE_EMAIL',), ('CONFLUENCE_API_TOKEN',)]`. The existing loop
  then prints and counts them because `config['adapters']['docs']` exists.

### Adapters

- `adapters/_http.py` `request(url, token, payload=None, *, authorization='Bearer',
  extra_headers=None, method='POST')`: `data` is `None` when `payload is None`; the event-stream
  branch reads `(payload or {}).get('id')`. Existing callers are unchanged.
- `adapters/docs/none.py`: `read` -> `registry.record_none('docs', 'read', root)`; `write`
  decorated `@outward_operation('docs')` -> `record_none('docs', 'write', root,
  measurement=False)` (the tracker `none.create` shape).
- `adapters/docs/notion.py`, `adapters/docs/confluence.py`: `read` with `@operation(...)`;
  `write` with `@outward_operation('docs')` over `@operation(...)` (the `linear.create` shape).
  Markdown-to-blocks (Notion) and Markdown-to-storage (Confluence) are private helpers in each
  file: `#`, `##`, `###` headings, `- ` list items, other non-empty lines paragraphs, text
  escaped. `# ponytail:` comment on each: no inline formatting, tables or links as rich text;
  Notion refuses more than 100 blocks or a line over 2000 characters (`Failure`).
- `adapters/docs/markdown.py`: no network, no credential, not decorated (a file in the item's PR,
  never an outward write). `read(ref)`: `ref` is an absolute file path; a symlink or missing file
  is `Result(1, None, 'markdown.read: no page at that path')`; else `{id, title (first '# '
  line or the stem), link, updated (mtime ISO)}` with `id == link == ref`. `write(draft)`: target
  is `draft['ref']` or `<parent>/<item>.md`; refuses a symlink target or a target outside
  `parent`'s directory; with `ref` appends `"\n" + body`, else writes `"# <title>\n\n" + body`;
  `parent.mkdir(parents=True, exist_ok=True)`; `workspace.atomic_write`; returns `{id, link}`
  (the absolute path; `docs.py` records only the relative one).
- `adapters/code_host/github.py` `pr`: add `'title': value.get('title') or ''` and
  `'body': value.get('body') or ''`; update `tests/fixtures/code_host/recordings.json` data and
  any test that compares a whole `pr()` dict.

### Outward policy and the draft queue

- `cli/wuwei/outward.py`
  - `METADATA_FIELDS` += `'kind'`, `'parent'` (the docs draft's non-text keys).
  - `classify`: immediately before `discussion = ''`, add
    `if kind == 'docs': return (CLEAN, 'send') if context.get('kind') in config['docs']['auto'] else (FINDINGS, 'draft')`.
    The sensitive, commitment, disagreement, audience and recipient checks above it still apply,
    so a sensitive page drafts even when its kind is in `auto`.
- `cli/wuwei/drafts.py`
  - `OPERATIONS['docs'] = {'write'}`.
  - `create`: destination falls back to `nested.get('ref') or nested.get('parent')` before
    `teamId`, so the approval prompt names the page or parent.
  - `approve`: after `finish`, `if row['channel'] == 'docs' and result.exit == 0:
    docs.record(root, inputs['draft'], row['adapter'], result.data['link'], draft_id=draft_id)`
    (lazy import). Its exceptions fall into the existing exit-2 handler.

### `cli/wuwei/docs.py` (new; every docs behaviour)

Signatures and rules:

- `required(config, row) -> bool`: `system != 'none'` and `(row.get('gates') or {}).get('tier')
  in required_tiers`.
- `unmet(config, row) -> bool`: `required(...)` and not `row.get('docs')`.
- `shown(config, row) -> str`: `'n/a'` when not required, `'missing'` when unmet, else the value
  (board column).
- `COMMAND = 'bin/wuwei plan set {item} docs=<page>|new|none --reason "<why>"'`; markdown form
  `'bin/wuwei docs page {item}, or bin/wuwei plan set {item} docs=<path>|none --reason "<why>"'`.
- `brief_line(config, row, item, role) -> str | None`: `None` under `none` or for roles other
  than `builder` and `sentinel-quality`. Builder: `Docs: <system>; items tiered <tiers> need a docs
  value before you stand down: <command>.` Quality: `Docs: not required (tier <tier>).`, or
  `Docs: required (tier <tier>); value missing: a blocking DOC: FINDING naming <command>.`, or
  `Docs: required (tier <tier>); value <value> (<reason>); check it against the diff under DOC.`
- `exempt(root, config, item, tier)`: under a system other than `none` and `tier not in
  required_tiers`, `state.append_event('docs.exempt', {'item', 'tier'}, root)`.
- `assign(item, value, reason, root=None) -> str` (`plan set`): `StateError` under `none`, for an
  unknown item, for `none` without a reason, and for `new` under markdown (naming `docs page`).
  A page value is read through the port first: markdown requires the item's worktree and a
  relative path under `docs.root` (no `..`, not absolute), read as `<worktree>/<path>`; remote
  reads `value`. Read exit 1 -> `StateError(reason)`, exit 2 -> `OSError(reason)`. Writes with
  `_write_state(kind='docs.set')`. Returns `'<item>: docs <value>'`.
- `render(root, config, data, item) -> (title, body)`: the candidate is today's `proposal.json`
  row with `id == item`, else `data['discovery_candidates'][item]`; no scope is a `StateError`.
  Goal outcome from `goals.parse(<root>/.wuwei/memory/goals.md)` when the goal is listed. When
  the item has a PR: `brief.read(code_host.pr, pr, root=root)` for `title`, `body`, `url`.
  Ticket: `(data.get('tickets') or {}).get(item, {}).get('id')`. Title `<item>: <first scope
  line>`. Body sections `### What changed` (scope, then `Pull request: <PR title>`),
  `### Why` (`Goal: <outcome>`, evidence), `### How to use it` (the PR body's `How to use`
  section, matched as a heading of any level up to the next heading; omitted when absent),
  `### Links` (`- Pull request: <url>`, `- Ticket: <id>`; omitted when neither exists).
- `check(text)`: raises `state.StateError` naming the first of: a `.wuwei/` path, `state.json`,
  `events.jsonl`, an absolute path (`(?:^|[\s(\[\x60"'=])(?:/|~/|[A-Za-z]:\\)[\w.-]`, so URLs
  pass), or a line that `redact.redact` changes ("credential"). Refuses, never strips.
- `page(root, item) -> (code, message)`: item must be in today's items; value `none` is a
  `StateError`; `render`, then `check(title + body)`. Under `none`: call the none adapter's
  `write` (exit 2, recorded). Under markdown: the target path is the value or
  `<docs.root>/<item>.md`, checked under `docs.root`; requires the worktree; run
  `outward.humanize_lint({'draft': draft}, root, config, {'docs'})` (exit 1 refuses); call
  `adapter.write(draft, root=root)` with absolute `parent`/`ref`; `record` with the relative path.
  A dated `## <YYYY-MM-DD>` heading is prepended to `body` whenever `ref` is set (append). Under
  notion and confluence: value unset becomes `new` first (`docs.set`); `ref` is `''` for `new`,
  else the value; `parent` is `docs.space` (empty is a `StateError` naming
  `bin/wuwei config set docs.space`); the decorated `write` drafts or sends; the shared
  `_outcome` maps the result.
- `_outcome(root, result, draft, adapter) -> (code, message)`: exit 0 -> `record`, `(0, 'docs:
  wrote <kind> page <link>')`; exit 1 whose reason contains `stored draft` -> `(0, reason)`;
  other exit 1 -> `(1, reason)`; exit 2 -> `(2, reason)`.
- `record(root, draft, adapter, page, draft_id=None)`: one
  `state._write_state(update, root, reserved=False, kind='docs.written', payload={item, kind,
  adapter, page, draft})`; `update` sets `items[item]['docs'] = {'value': page, 'reason': ''}`
  when `kind == 'page'` and the current value is unset or `new`.
- `publish(root, kind) -> (code, message)`: markdown -> `(0, 'docs: publish has no effect under
  markdown')`; `none` -> the none adapter (exit 2). Once per kind per day: a `docs.written`
  event of that kind today or any docs draft row today whose `inputs.draft.kind` is that kind
  -> `(0, 'docs: <kind> page for <date> already <draft id or page>')`. Source: today's
  `report.md` (`Merged`, `Parked`, `Decisions answered`, `Carry`, `Docs`) or
  `retro/<date>.md` (`Applied`, `Proposed`); a missing file is a `StateError` naming
  `wuwei report` or `wuwei retro`. Title `Report <date>` or `Retro <date>`; `check`; draft
  `{kind, item: '', title, body, parent: space, ref: ''}`; decorated `write`; `_outcome`.
- `findings(root, config, data) -> list[str]`: for each item in today's state with phase
  `merged` and `required`, in name order, the first that applies:
  no value -> `<item>: no docs value (tier <tier>); <COMMAND>`; value `none` -> nothing;
  a pending docs page draft for the item -> `<item>: docs draft <id> pending; bin/wuwei drafts
  approve <id>`; markdown and the value not among `brief.read(code_host.files, pr)` paths ->
  `<item>: docs page <path> is not in <pr>; <markdown COMMAND>`; remote and no `docs.written`
  page event for the item after the first event today whose `phase_changes` moves it to `merged`
  -> `<item>: docs page <value> not written since the merge; bin/wuwei docs page <item>`.
- `close(root) -> (code, text)`: `(0, '')` under `none` or `strict_close = false`; else
  `(int(bool(lines)), '\n'.join(lines))`; `watch.ERRORS` -> `(2, 'docs unmeasured: <exc>')`.
- `report_lines(root, config, data) -> list[str]`: `[]` under `none`; one line per required
  item: `- <item>: <value>` plus ` (<reason>)`, or `- <item>: missing`; under
  `strict_close = false` the `findings` lines follow as `- <line>`; `['none']` when empty.
- `detect(paths) -> str | None`: for each repository path in order, `README.md`, `README`,
  `CONTRIBUTING.md`, `CONTRIBUTING`; the earliest
  `https://[\w.-]*notion\.(?:so|site)/[^\s)>\]"']+` or
  `https://[\w-]+\.atlassian\.net/wiki/[^\s)>\]"']+` match.

### Callers (one call each)

- `cli/wuwei/commands/plan.py`: verb `set` (`item`, `assignment`, `--reason`); `assignment` must
  be `docs=<value>` with a nonempty value, else `ValueError('plan set: expected
  docs=<page>|new|none')` (exit 2); calls `docs.assign`. If #412 or #417 lands first, extend its
  `set` dispatch with the `docs` key instead of adding a second parser.
- `cli/wuwei/commands/docs.py` (new): `docs page <item>`, `docs publish {report,retro}`;
  `workspace.guard_scope` (None -> exit 0); `StateError` -> 1; `OSError`, `ValueError`,
  `KeyError`, `TypeError` -> 2; prints the message.
- `cli/wuwei/commands/__init__.py` `WRITES` += `docs page`, `docs publish`, `plan set`;
  `cli/wuwei/__main__.py` `GROUPS` Daily += `docs`.
- `cli/wuwei/dispatch.py`
  - `next_step`: after the `gate.tiered` `_write_state`, `docs.exempt(root, config, item,
    record['tier'])` (hold the `load_config` result in a local).
  - `receive`: after `result` is read, with `config = workspace.load_config(root)`:
    `if base(role) == 'quality' and docs.unmet(config, data['items'][item]) and (result == 'PASS'
    or not re.search(r'\bDOC: *FINDING', text)): raise Refused('docs obligation unmet: the quality
    verdict must be FIX with a DOC: FINDING naming ' + COMMAND)`.
- `cli/wuwei/brief.py` `write`: after the `Assumptions:` header line (outside the `if gate`
  block so the builder gets it), `line = docs.brief_line(config, current, item, role)`; append
  when not `None`.
- `cli/wuwei/closing.py` `check`: `results.append(docs.close(root))` after the obligations entry.
- `cli/wuwei/report.py` `build`: after `## Carry`, `lines += ['', '## Docs', *report_lines]` when
  `report_lines` is not empty (so `none` changes nothing).
- `cli/wuwei/commands/report.py` and `commands/retro.py`: after writing, when the kind is in
  `docs.publish` and `docs.system` is `notion` or `confluence`, print `docs.publish(root, kind)`'s
  message and return its code.
- `cli/wuwei/commands/next.py` `step`: in the item loop, for `phase in ('gate', 'delta')`,
  before the `verdicts` row: `if docs.unmet(config, items[name])` return
  `_row('docs', '<item> (tier <tier>) has no docs value; record it before the quality gate.',
  'wuwei plan set <item> docs=<page>|new|none --reason "<why>"')`.
- `cli/wuwei/commands/board.py` `read`: a `Docs` column in the Work table from `docs.shown`.
- `cli/wuwei/commands/doctor.py`: `_docs(root, config)` in the `gates` section (called from
  `diagnose` next to `_gates`), rows named `docs`: `none` -> ok `not used`; notion/confluence ->
  fail `docs.space is empty` (fix `bin/wuwei config set docs.space '"<page link>"'`), fail
  `<VAR> missing` (fix `add <VAR> to .wuwei/env`), fail when `read(space)` exit is not 0 (its
  reason; fix `check docs.space and the credential`), else ok `<system>: <title>`; markdown ->
  fail when `docs.root` is not a directory in any configured repository (fix
  `create <root>/ in the repository or bin/wuwei config set docs.root '"<dir>"'`), warn when
  `publish` is not empty (fix `bin/wuwei config set docs.publish '[]'`), else ok. `docs=` points
  at `docs/site/configuration.md#docs`.
- `cli/wuwei/interview.py`: a `docs` row after `review_bot`: header `Docs`, question `Where does
  your documentation live?`, choices Notion, Confluence, Markdown, None mapping `docs.system`
  (descriptions avoid glossary words such as page, gate and tier before any `(`), free
  `(_docs_link, 'a Notion or Confluence link, for example https://<site>.atlassian.net/wiki/...')`;
  `_docs_link` fullmatches the two `detect` patterns and returns `{'docs.system': ..., 'docs.space':
  link}`. `ask(ids, repos, defaults=None)`: a row with a default prints `  Enter: <default>` and an
  empty reply takes it.
- `cli/wuwei/commands/setup.py` `_setup`: `link = docs.detect([<each staged repo path>])`; pass
  `defaults={'docs': link}` to `interview.ask` when found.
- `cli/wuwei/state.py` `_producer_error` item map: `'docs': 'wuwei plan set or wuwei docs page'`.
- `cli/wuwei/commands/event.py` `EVENT_PRODUCERS`: `docs.set`, `docs.written`
  (`'wuwei docs or wuwei drafts approve'`), `docs.exempt` (`'wuwei dispatch next'`).

### Charters, generated agents, template and site

- `charters/sentinel-quality.md` step 7: when the brief's `Docs:` line says required, check the
  value against the diff under `DOC`; a missing value, or `none` for a change to documented
  behaviour (a command, a config key, an interface, user-visible output), is a blocking
  `DOC: FINDING` naming the command the line gives. `charters/builder.md`: one rule under the
  class list: when the brief has a `Docs:` line, record the value with the command it names
  before you stand down; under markdown, write the page with `bin/wuwei docs page <item>` and
  commit it. Regenerate `agents/` with `bin/wuwei agents build`.
- `templates/workspace/config.toml`: a commented `[docs]` table after `[tracker]` with every key.
- `docs/site/configuration.md`: `[docs]` in the Sections list and a section naming each key as
  `` `docs.<key>` ``; `concepts.md`: glossary entries `Docs system` and `Docs obligation`
  (appended, two lines each) and `GLOSSARY` in `tests/test_docs.py`; `daily.md`: one paragraph;
  `reference.md`: rows for `bin/wuwei docs page <item>`, `bin/wuwei docs publish report|retro`
  and `bin/wuwei plan set <item> docs=`; `adapters.md`: credential rows for `docs.notion` and
  `docs.confluence`.

### Changed while building

- `cli/wuwei/commands/docs.py` finds the workspace like `plan` does (outside one it exits 2 with
  the reason) instead of `workspace.guard_scope`: an explicit `docs page` names an item, so there
  is nothing to skip silently. Its `listed(kind)` is what `wuwei report` and `wuwei retro` call.
- `cli/wuwei/signal.py`: `docs.set`, `docs.written` and `docs.exempt` are silent events.
- `adapters/docs/_lines.py`: the one Markdown line reader notion and confluence share.
- `docs.publish` names a retro's `.wuwei/charters/...` targets workspace-relative (see spec
  Assumptions); `docs.page` under markdown refuses a recorded path missing from the worktree.

## What must not change

- `outward.check_call`, `check_tier`, `check_lint`, `registry.outward_operation` signatures and
  every non-`docs` classify path; the draft queue for chat, code host and tracker.
- `dispatch.tier`, the gate sets, `gate.tiered` payloads; `closing.unresolved`; the report's
  existing sections.
- Under `docs.system = "none"`: no brief line, no receive refusal, no close line, no report
  section, no event, no board difference other than the `n/a` column, no `next` row.
- `registry.validate`/`load` semantics for other kinds; `adapters.docs` is not a schema key.
- Hook-path imports: `next.step` and `outward` gain no module-level import.

## Merge notes (same wave)

- #412 makes `('plan', 'set')` owner-only in `guards/protect_state.py`. 5.12 needs seats to set
  `docs=`; whoever merges second narrows that entry to `spec=` assignments. Task T048 pins this.
- #417 adds `plan set <item> ticket=<id>` and the `tickets` record. `docs.render` reads
  `tickets.<item>.id` only; one `set` verb dispatches all keys after merge.

## Verification

- `python -m pytest -q tests/test_docs_port.py tests/test_docs_system.py` then the full suite.
- A search for U+2014 and emoji code points over the files this feature touches finds nothing
  new.
