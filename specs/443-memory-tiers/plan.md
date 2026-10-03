# Implementation Plan: Memory tiers over time

**Branch**: `443-memory-tiers` | **Date**: 2026-10-03 | **Spec**: `spec.md` | **Design**: section
5.14 of `docs/specs/2026-09-24-wuwei-design.md` (written in this item, spec first)

## Summary

Three tiers with one producer each. The one archiver (`consolidation.archive_days`) packs old
days into tarballs; one reader (`consolidation.day_records`) reads a day from wherever it is;
one builder (`digest.build`) turns day records into a week or month digest; the payload
loads digests, then rules, then today, under `memory.budget_tokens`. Forgetting reuses the
existing findings and the existing promote landing, behind one owner action. The export is
one function writing a marked block. No new dependency: `tarfile` is stdlib.

## Technical Context

Python 3.11+, stdlib only. Tests: pytest, in process, `tmp_path` workspaces, fake VCS via
`registry.load` monkeypatch (as `tests/test_consolidation.py` does), `WUWEI_NOW` for the
clock, an injected `confirm` for the host y/N. No network, no subprocess beyond the existing
CLI smoke tests.

## Constitution Check

- I stdlib only: `tarfile`, `json`, `re`, `datetime`. Pass.
- II exits: every new command 0, 1, 2 with the reason; unreadable tarball or records fail
  closed with exit 2. Pass.
- III one behaviour one function: archive in `archive_days`, read in `day_records`, digest in
  `digest.build`, landing in `promotion.land`, export in `memory.export`. Pass.
- IV test first: tasks.md orders every test before its code. Pass.
- V ponytail: no new config for the 60 days or the archive window (existing key reused);
  forgetting reuses `note_findings` checks and `promotion._apply`; no gate-recording path for
  `F-n`. Pass.
- VII security: new records are producer-only; `memory forget` is an owner action; digests
  carry no seat free text that fails the outward lint, no path, no loaded secret; tar members
  are validated before reading. Pass.
- Hook latency (#346): SessionStart reads only `memory/digests/*.md`, spine, index; it never
  opens a tarball and never imports `tarfile` or `digest`. Pass.

## Changes

### `cli/wuwei/workspace.py`

`SCHEMA['memory']` gains `"digest": (str, "week", ("week", "off"))`,
`"budget_tokens": (int, 6000, 1)`, `"export_to": (str, "CLAUDE.md")`. Bump
`CONFIG_CACHE_VERSION` (the defaults change).

### `templates/workspace/config.toml`

Under `[memory]`: `digest = "week"`, `budget_tokens = 6000`, `export_to = "CLAUDE.md"`, each
with a short comment.

### `cli/wuwei/consolidation.py` (archiver, reader, forgetting)

- `expired(root)`: the existing selection loop of `archive_days` (lines 75 to 89) extracted;
  returns the `days/<date>/` directories older than `consolidation.archive_after_days` plus
  every legacy `archive/<date>/` directory, with the existing symlink and date checks.
  `doctor` reuses it.
- `archive_days(root)`: for each expired source, refuse a symlink anywhere under it, write
  `archive/<year>/<date>.tar.gz` with `tarfile.open(target, 'x:gz')` and
  `add(source, arcname=<date>)`, reopen it and compare member file names with the source
  files, then `shutil.rmtree(source)`. Keep the index preflight and refresh and the commit;
  it then writes the week and month digests of the packed days (`digest.write`), and the
  commit paths become the tarballs, those digests and `memory/index.md` (FR-001). Return the moved dates as
  today. On any failure before `rmtree`, unlink the partial tarball and raise.
- `day_records(root, day)`: `{relative name: text}` for one date, or `None` when the date has
  no records. Order: `days/<date>/`, legacy `archive/<date>/`, then
  `archive/<year>/<date>.tar.gz`. Directories: `rglob` regular files, refuse symlinks. Tarball:
  `tarfile.open(path, 'r:gz')`; every member must be a regular file or directory named
  `<date>` or `<date>/...` with no `..` and not absolute, else `ValueError`; read files with
  `extractfile`, decode UTF-8 (a `UnicodeError` is a `ValueError`). Never extracts to disk.
- `_contradicts(rule, other)`: the do or never comparison now inline in `note_findings`
  (lines 44 to 52) extracted unchanged; `note_findings` calls it.
- `forget_proposals(root)`: list of proposal dicts (data-model.md) for the four kinds:
  - unreferenced: active notes with `created` (or mtime, as `promotion.archive_candidates`)
    more than 60 days before today and past `memory.probation_days`, whose slug (word
    boundary) or `notes/<slug>.md` appears in no `briefs/`, `decisions/` or `retro/` file of
    any date in the last 60 days, read with `day_records`. `UNREFERENCED_DAYS = 60` is a
    module constant.
  - duplicate: the near-duplicate note pairs `note_findings` finds (same
    `SequenceMatcher` and threshold); survivor is the one with more loads in
    `promotion.adherence_counts(root)['note_loads']`, ties to the first in slug order.
  - superseded: near-duplicate rule lines within the same `.wuwei/charters/<name>.md`; the
    earlier line is the target `old_text` (full line with its newline).
  - contradicted: for each raw day's `decisions/D-*.md` with an `Outcome:` other than
    pending, parse with `decision.evaluate` and `decision.table(fields['Options'], ['Option',
    'Description'], 'Options')`; the chosen option's description against every local
    charter rule with `_contradicts`. Invalid records are skipped (decision lint owns them).
- `merge_proposals(root, proposals)`: read `memory/forget.json` (missing is `{}`; symlink,
  invalid JSON or a row of the wrong shape is `ValueError`), add proposals whose dedup key is
  new with the next `F-n`, `status: pending`, `created: today`; write it with
  `workspace.atomic_write` only when changed; return the pending rows.
- `forget(root, ident, label, confirm=None)`: `label` is `apply` or `keep`. Unknown id or
  status not pending: `ValueError` (exit 1). `keep`: set `declined`, write, return. `apply`:
  `(confirm or integrity._host_confirm)(fingerprint, prompt=...)` with the fingerprint the
  sha256 of the row's JSON and a prompt naming the action, target and evidence; no means
  `PermissionError` (exit 1, nothing written). Yes: build the promote proposal (data-model.md),
  call `promotion.land`; a `rejected` record raises `ValueError` with its reason (proposal
  stays pending); `landed`: append `memory.folded` with `state.append_event`, set `applied`,
  write `forget.json`, run `memory.export(root)`. The archive path in the event is
  `memory/archive/<note file>` for archive and fold, `memory/archive/dropped-rules.md` for
  drop.

### `cli/wuwei/digest.py` (new, the one builder)

- `build(root, title, dates, config)`: the fixed shape of data-model.md from
  `consolidation.day_records` for each date (dates without records are skipped) and the
  ledger rows for those dates. Uses `report`'s `Outcome:` regex shape, `signal.classify`,
  `outward.lint`, `redact.known_values`. A helper `_line(structured, free, config)` returns
  `f'{structured}: {free}'` when the free text is clean, else `structured`.
- `period(day, kind)`: `(name, title, dates)` for the ISO week (`2026-W40`, `# Week 2026-W40
  (2026-09-28 to 2026-10-04)`, Monday to Sunday) or the month (`2026-09`, `# Month 2026-09`).
- `write(root, day, kind)`: no-op returning `None` when `memory.digest == "off"`; else build
  and write `memory/digests/<name>.md` with `workspace.atomic_write` when the text differs;
  returns the path. Refuses a symlinked `memory/digests`.
- `latest(root)`: `(month path or None, week path or None)`, the last of each name pattern
  in sorted order. Used by the payload, export and status. Kept tiny so the payload can
  import it lazily without `tarfile`: `digest.py` imports `consolidation` inside `build`
  only.

### `cli/wuwei/memory.py` (payload and export)

- `session_payload(root)`: read `config['memory']`; sections in order:
  - `Digests:` the latest month then week digest text (`digest.latest`), omitted when none;
  - `Rules:` `Spine:` and the spine, `Notes:` and the index lines that do not start with a
    date;
  - `Today:` the index lines that start with `YYYY-MM-DD |`, `Full day state: wuwei state
    get`, the promote line.
  When `estimated_tokens(whole) > budget_tokens`, return digests and rules plus `Memory
  budget: <n> of <budget> estimated tokens; today left out (wuwei state get, wuwei memory
  status).` Return `(content, bytes, tokens)` as today. The constraints block is no longer in
  the content.
- `export(root)`: resolve `config['memory']['export_to']` against the root: refuse an
  absolute path, `..`, a first part `.wuwei`, or a symlink in any existing component; build
  the block (data-model.md) from `.wuwei/charters/*.md` rule lines and the Lessons section of
  the latest week digest; replace the text between the markers, or append the block; refuse
  a start marker without an end marker or more than one start marker; write with
  `workspace.atomic_write` only when the text changed. Return `(path, changed)`.

### `cli/wuwei/guards/lifecycle.py` (`session_start`)

In the memory `try`, extend lines with `memory.constraints(root, state.read_state(root))`
before the payload, then the payload and its size line as today. If `tokens >
config['memory']['budget_tokens']` after the call, add `memory: digests and rules exceed
memory.budget_tokens (<n> > <budget>); run wuwei consolidate` and `code = max(code, 1)`.

### `cli/wuwei/promotion.py`

- `_apply`, `patch` branch: when the target is a charter and `text == ''` (key present and
  empty), require `old_text` exactly once and to be one whole line starting `- `, remove it,
  append `- <today> <charter name>: <rule>` to `memory/archive/dropped-rules.md` (create the
  directory as the archive branch does; refuse a symlink) and return `[target, that file]`.
  Nonempty `text` keeps today's behaviour; empty text on a note or voice stays refused.
- `land(root, proposal, *, day, run, ledger, name)`: the body of the `promote` loop from
  `_apply` to the commit (lines 236 to 266, minus reading and renaming the proposal file),
  returning the ledger record. `promote` passes each proposal file's path, which `land`
  reads and renames to its status right after the ledger line, as before; `memory forget`
  passes a dict.
  `memory forget` calls it with `name = F-n`.

### `cli/wuwei/commands/consolidate.py`

- `--widget`: print `json.dumps([...], indent=2)` of `decision.widget(decision.gate(root) +
  f'{id}: {evidence}. {action text}?', id, [('apply', 'Recommended. ...'), ('keep', 'Keep
  it; it is not proposed again.')], f'bin/wuwei memory forget {id} <label>')` for each pending
  row of `forget.json`; write nothing; exit 1 when any, else 0.
- Default run: `note_findings`, `archive_days` (which writes the archived days' digests),
  then `digest.write` for the week and the month of today, `merge_proposals(root, forget_proposals(root))`
  printing each pending row as `F-n: <action> <target name>: <evidence>`, `memory.export`,
  then `state.append_event('memory.consolidated', {...}, root)`. Exit 1 when findings or
  pending proposals, else 0.

### `cli/wuwei/commands/payload.py`

The constraints block left the payload, so `wuwei payload` prints `memory.constraints` before
it (and still fails closed on a corrupt day state); its size line counts what it printed.

### `cli/wuwei/commands/close.py`

After `code, reason = closing.check(root)` and `code == 0`: `digest.write(root,
workspace.now().date(), 'week')`. An error there propagates as today's errors do (exit 2 by
the CLI wrapper).

### `cli/wuwei/commands/promote.py`

After printing, when any record is `landed`, call `memory.export(root)`; an `OSError` or
`ValueError` prints `wuwei promote: export: <reason>` to stderr and returns 2.

### `cli/wuwei/commands/memory.py`

Subcommands beside `lint`:

- `show <date>` (validate `YYYY-MM-DD`): `consolidation.day_records`; print each record
  sorted by name under `== <name> ==`; `None` is exit 1 `no records for <date>`;
  `ValueError` or `OSError` exit 2.
- `status`: lines `raw: <n> days, <bytes> bytes`, `archive: <n> days, <bytes> bytes`
  (tarballs plus legacy directories), `digests: <n> weeks, <m> months, <tokens> estimated
  tokens`, `rules: <n> charters, spine, <m> notes, <tokens> estimated tokens`, `payload:
  <tokens> of <budget> estimated tokens`, `last consolidate: <date or none>` (newest raw day
  whose `events.jsonl` has `memory.consolidated`, read with `watch.records`), `pending
  proposals: <n> (wuwei consolidate --widget)`. Exit 0; errors exit 2.
- `export --claude` (`required=True`): `memory.export`; prints `export: <path> written` or
  `unchanged`; errors exit 2.
- `forget <id> {apply,keep}`: `consolidation.forget`; prints the outcome; `ValueError` and
  `PermissionError` exit 1, `OSError` exit 2.

### `cli/wuwei/commands/__init__.py`

`READ_ONLY` gains `'memory show'`, `'memory status'`. `WRITES` gains `'memory export'`,
`'memory forget'`. `tests/test_cli_known_command.py` already walks every subparser and checks
both sets and that owner pairs are in `WRITES`.

### `cli/wuwei/guards/protect_state.py`

- `_OWNER_ACTIONS[('memory', 'forget')] = 'Forgetting memory is an owner action on the
  host, outside agent tools.'`
- `_protected_name`: `tail[:2] == ('memory', 'digests')` and `tail == ('memory',
  'forget.json')` are protected; with `directories`, `('memory', 'digests')` too.

### `cli/wuwei/commands/event.py`

`EVENT_PRODUCERS`: `'memory.folded': 'owner host wuwei memory forget'`,
`'memory.consolidated': 'wuwei consolidate'`.

### `cli/wuwei/interview.py` (`_recorded`)

Keep the two directory globs; add the tarballs: for each `archive/*/*.tar.gz`, read
`consolidation.day_records(root, <stem date>).get('interview.json')` and parse it with the
same checks. `# ponytail: opens every archived day; index answers in a digest if calibrate
gets slow.`

### `cli/wuwei/commands/doctor.py`

In `_workspace`, after the charter overrides row: `consolidation.expired(root)` raw days only
(not legacy directories); none is `ok` `within <window> days`; some is `warn` `<n> raw days
older than consolidation.archive_after_days (<window>); consolidate has not run` with fix
`wuwei consolidate`; an exception is `unmeasured` with the reason.

### Docs and skill

- `docs/site/configuration.md`: rows for `memory.digest`, `memory.budget_tokens`,
  `memory.export_to`; the `consolidation.archive_after_days` row says tarballs under
  `archive/<year>/`.
- `docs/site/concepts.md` `## Memory`: one paragraph: raw days for 30 days then a tarball,
  week and month digests that sessions load, rules only in charters and notes, forgetting
  only on the owner's answer with the before text kept, the export into `CLAUDE.md` and why
  (bounded context, one source).
- `docs/site/reference.md`: the `bin/wuwei memory` row names `lint`, `show`, `status`,
  `export` and `forget` (one row; the duplicate plumbing row goes); `consolidate` row names
  `--widget`; `memory forget` joins the host terminal actions list; the doctor section names
  the `memory tiers` row.
- `skills/wuwei-consolidate/SKILL.md`: step 3 becomes "run `wuwei consolidate --widget` and
  ask each proposal; the owner records it with `bin/wuwei memory forget F-n <label>` in a host
  terminal"; step 4 says days become tarballs readable with `wuwei memory show <date>` and
  digests stand for them in the payload.
- `docs/specs/2026-09-24-wuwei-design.md` section 5.14: already written.

## Test plumbing (existing tests that move with the change)

- `tests/test_consolidation.py::test_missing_changelog_does_not_block_day_archive`: assert
  the tarball and read `report.md` through `day_records`.
- `tests/test_consolidation.py::test_35_days_archive_five_and_index_keeps_summaries`: rename
  to `..._index_keeps_raw_days`; 5 tarballs under `archive/2026/`, 30 index day lines; commit
  paths start with `archive/` or `memory/index.md`.
- `tests/test_memory.py::test_payload_opens_with_active_constraints`: assert the constraints
  through `memory.constraints` and the SessionStart output (constraints before the payload);
  the payload content starts with `Rules:` when no digest exists.
- `tests/test_memory.py::test_index_sorts_days_across_live_and_archive_...`: unchanged
  (legacy directories still index until consolidate packs them).

## What must not change

- Hook path: `memory.py`, `lifecycle.py` keep their top-level imports; no `tarfile` and no
  tarball read at SessionStart, PreToolUse or Stop.
- `Active constraints:` stays before line 25 of SessionStart output (#358 SC-002,
  `tests/test_next.py`).
- `promote` behaviour for seat proposals: same ledger lines, renames, changelog, commit.
- `note_findings` output text for every existing finding.
- Raw day records: never edited; a tarball holds them byte for byte.
- Nothing reads `CLAUDE.md` or any harness memory.
- `consolidation.archive_after_days` keeps its name and default.
