# Tasks: Memory tiers over time

Test first: run each test task, see it fail for the stated reason, then do the implementation
task that follows it. Run tests with `python -m pytest -q <file>` from the repository root
using the interpreter the task names. Signatures, formats and texts are in plan.md and
data-model.md. Fixtures: `tmp_path` workspaces as in `tests/test_consolidation.py`
(`workspace(tmp_path)`), a fake VCS through `monkeypatch.setattr(registry, 'load', ...)`,
`WUWEI_NOW` for the clock, neutral names only.

## Config keys (FR-013)

- [X] T001 In `tests/test_workspace.py`, add a failing test: a default config gives
  `config['memory']['digest'] == 'week'`, `budget_tokens == 6000`, `export_to == 'CLAUDE.md'`;
  `digest = "month"` and `budget_tokens = 0` raise `ConfigError`; the shipped
  `templates/workspace/config.toml` loads and sets the three keys. Fails today: `KeyError:
  'digest'`.
- [X] T002 In `cli/wuwei/workspace.py`, add the three keys to `SCHEMA['memory']` and bump
  `CONFIG_CACHE_VERSION`; in `templates/workspace/config.toml`, add the three lines under
  `[memory]`.

## One reader for a day (FR-002, US3)

- [X] T003 In `tests/test_consolidation.py`, add failing table tests for
  `consolidation.day_records`: a raw day returns `{'report.md': ..., 'decisions/D-1.md':
  ...}`; a legacy `archive/<date>/` the same; a tarball written with `tarfile` under
  `archive/2026/<date>.tar.gz` the same; a missing date returns `None`; a symlinked day, a
  member named `../x`, an absolute member, a symlink member and a member outside `<date>/`
  raise `ValueError`; a truncated gzip raises `ValueError` or `OSError`. Fails today:
  `AttributeError: day_records`.
- [X] T004 In `cli/wuwei/consolidation.py`, add `day_records`.

## Archive as tarballs (FR-001, FR-003, US1)

- [X] T005 In `tests/test_consolidation.py`, update
  `test_35_days_archive_five_and_index_keeps_summaries` (rename to
  `test_35_days_archive_five_tarballs_and_index_keeps_raw_days`) and
  `test_missing_changelog_does_not_block_day_archive` to the tarball layout, and add failing
  tests: every source file is a member and the source directory is gone; a legacy
  `archive/2026-08-01/` becomes `archive/2026/2026-08-01.tar.gz`; an existing tarball
  destination raises and leaves the source; a symlink inside a day raises and writes no
  tarball; `consolidation.expired` lists raw and legacy sources older than the window. Fails
  today: `archive/<date>/` directories, no `expired`.
- [X] T006 In `cli/wuwei/consolidation.py`, extract `expired` from `archive_days` and make
  `archive_days` write, verify and commit tarballs (plan.md).

## Interview answers survive archiving (FR-002, US3 scenario 4)

- [X] T007 In `tests/test_interview.py`, add a failing test: an `interview.json` answer in a
  day that `archive_days` packed is still in `interview._recorded(root)`, so
  `interview.widgets` does not ask it. Fails today: the `archive/*/interview.json` glob finds
  nothing.
- [X] T008 In `cli/wuwei/interview.py` `_recorded`, read tarballs through
  `consolidation.day_records`.

## Digest builder (FR-004, FR-005, US1)

- [X] T009 In `tests/test_digest.py` (new), add failing tests for `digest.build` and
  `digest.period` on a three-day fixture (decisions with `Question:` and `Outcome:`, one
  pending; ledger rows landed and rejected; a `report.md` with `## Outcome`; one page-tier
  `mcp.finding` event with severity high; items merged, parked and building): the exact text
  of data-model.md's shape, `none` for an empty section, a day without `report.md` shows
  `unmeasured`; a question containing `src/app.py`, one containing `the seats`, and a ledger
  reason containing a value in `redact.VALUES` fall back to the structured line and the
  digest contains none of those texts; `period(date(2026, 10, 3), 'week')` is `2026-W40`
  Monday to Sunday and `'month'` is `2026-10`. Fails today: no module `wuwei.digest`.
- [X] T010 Create `cli/wuwei/digest.py` with `build`, `period` and the `_line` helper.
- [X] T011 In `tests/test_digest.py`, add failing tests for `digest.write` and
  `digest.latest`: writes `memory/digests/2026-W40.md`, a second call with the same records
  leaves the file's mtime and bytes unchanged; a day in a tarball is read; `digest = "off"`
  writes nothing and returns `None`; a symlinked `memory/digests` raises; `latest` returns
  the newest month and week. Fails today: `AttributeError: write`.
- [X] T012 In `cli/wuwei/digest.py`, add `write` and `latest`.

## Payload: digests, rules, today, under a budget (FR-006, US1)

- [X] T013 In `tests/test_memory.py`, update `test_payload_opens_with_active_constraints` to
  assert the constraints through `memory.constraints` and that the payload no longer holds
  them, and add failing tests: with a month and a week digest the payload starts with
  `Digests:` then the month then the week, then `Rules:` with the spine and only the note
  lines of the index, then `Today:` with only the day lines, the state pointer and the
  promote line; with `budget_tokens` below the whole, the payload has no `Today:` section and
  ends with the `Memory budget:` line; `test_payload_content_size_and_missing_source` still
  passes. Fails today: the payload starts with `Active constraints:`.
- [X] T014 In `cli/wuwei/memory.py`, rewrite `session_payload` (plan.md).
- [X] T015 In `tests/test_next.py`, add a failing test next to
  `test_issue_acceptance_session_start_orients`: with a 40-line week digest present,
  SessionStart output has `Active constraints:` before line 25 and before `Digests:`; and in
  `tests/test_memory.py` a test that SessionStart exits 1 with the `memory: digests and
  rules exceed` line when digests and rules alone exceed the budget. Fails today: constraints
  sit inside the payload after the digests (after T014), and no budget finding exists.
- [X] T016 In `cli/wuwei/guards/lifecycle.py` `session_start`, print `memory.constraints`
  before the payload and add the budget finding.

## Close writes the week (FR-005, US1 scenario 3)

- [X] T017 In `tests/test_close_branches.py`, add a failing test: a close that passes
  (patch `closing.unresolved`, `steward.run` and `closing.check` to clean as the existing
  close tests do) writes `memory/digests/<week>.md`; a refused close writes none; running the
  passing close twice leaves the bytes unchanged. Fails today: no digest.
- [X] T018 In `cli/wuwei/commands/close.py` `run`, call `digest.write(root, today, 'week')`
  when `closing.check` passes.

## Promote landing shared, and a rule drop (FR-009)

- [X] T019 In `tests/test_promotion.py`, add failing tests: a charter `patch` proposal with
  `text: ""` and `old_text` one whole rule line removes exactly that line, appends `- <today>
  <name>: <rule>` to `memory/archive/dropped-rules.md`, and the commit paths include both
  files; `old_text` that occurs twice or is not a whole `- ` line is rejected; empty text on a
  note target is still rejected; `promotion.land` called directly returns the same ledger
  record `promote` writes for one proposal file. Fails today: `text or delta is required`,
  no `land`.
- [X] T020 In `cli/wuwei/promotion.py`, extend `_apply` and extract `land` from `promote`.

## Forgetting proposals (FR-007, US2)

- [X] T021 In `tests/test_consolidation.py`, add failing tests for
  `consolidation.forget_proposals`: a note created 90 days ago, past probation, named by no
  brief, decision or retro in the last 60 days (raw and tarball days) gives one
  `unreferenced` `archive` proposal with the evidence line; the same note named in a
  tarball day's `briefs/x.md` 45 days ago gives none; a note created 30 days ago gives none;
  two near-duplicate notes give one `duplicate` `fold` with the more loaded note as survivor;
  two near-duplicate lines in one charter give one `superseded` `drop` of the earlier line;
  the same lines in two charters give none; an answered decision whose chosen option is `Do
  carry parked items` against the rule `- Do not carry parked items.` gives one
  `contradicted` `drop`. `note_findings` output is unchanged for the existing tests. Fails
  today: `AttributeError: forget_proposals`.
- [X] T022 In `cli/wuwei/consolidation.py`, extract `_contradicts` and add
  `forget_proposals` and `UNREFERENCED_DAYS`.
- [X] T023 In `tests/test_consolidation.py`, add failing tests for
  `consolidation.merge_proposals`: first run writes `F-1` pending; a second run with the same
  proposals adds nothing and does not rewrite the file; a declined row blocks the same
  proposal; a new proposal gets `F-2`; a symlinked or invalid `forget.json` raises. Fails
  today: `AttributeError: merge_proposals`.
- [X] T024 In `cli/wuwei/consolidation.py`, add `merge_proposals`.

## Applying a proposal (FR-008, FR-010, US2)

- [X] T025 In `tests/test_consolidation.py`, add failing tests for `consolidation.forget`
  with an injected `confirm`: `apply` with yes archives the note under `memory/archive/`,
  appends a `landed` ledger line, appends one `memory.folded` event with `id`, `kind`,
  `action`, `target` and `archive`, sets `applied`, and calls `memory.export` (patched);
  `apply` with no raises `PermissionError` and changes nothing; `keep` sets `declined`
  without calling `confirm`; an unknown id or an `applied` row raises `ValueError`; a target
  removed since the proposal gives a `rejected` ledger line, no event, the row stays pending
  and `ValueError`; a `drop` lands through `land` and names `dropped-rules.md`. Fails today:
  `AttributeError: forget`.
- [X] T026 In `cli/wuwei/consolidation.py`, add `forget`; in `cli/wuwei/commands/event.py`,
  add `memory.folded` and `memory.consolidated` to `EVENT_PRODUCERS`.

## Export into the harness memory (FR-012, US5)

- [X] T027 In `tests/test_memory.py`, add failing tests for `memory.export`: with two
  charter overrides and a week digest the target `CLAUDE.md` holds the block of
  data-model.md; existing text before and after the markers is unchanged; a second call
  returns `changed` False and keeps the mtime; `export_to` absolute, with `..`, under
  `.wuwei/`, or through a symlinked directory raises `ValueError` and writes nothing; a start
  marker without an end marker raises. Fails today: `AttributeError: export`.
- [X] T028 In `cli/wuwei/memory.py`, add `export`.

## Commands (FR-008, FR-011, FR-012, FR-015, US1, US2, US3, US6)

- [X] T029 In `tests/test_memory.py`, add failing in-process command tests (call the
  registered `func` with an `argparse.Namespace`, as other command tests do): `memory show
  <archived date>` prints `== report.md ==` and its text, exit 0; a raw date the same; an
  unknown date exit 1 with `no records for`; a corrupt tarball exit 2; `memory status` prints
  the seven lines of plan.md with counts for a fixture of 3 raw days, 2 tarballs, 1 week and
  1 month digest, 1 pending proposal and a `memory.consolidated` event, exit 0; `memory
  export --claude` prints `written` then `unchanged`; `memory forget F-1 keep` exit 0 and
  `memory forget F-9 apply` exit 1. Fails today: `invalid choice: 'show'`.
- [X] T030 In `cli/wuwei/commands/memory.py`, add `show`, `status`, `export` and `forget`; in
  `cli/wuwei/commands/__init__.py`, add `memory show` and `memory status` to `READ_ONLY` and
  `memory export` and `memory forget` to `WRITES`.
- [X] T031 In `tests/test_consolidation.py`, add the issue acceptance test: 45 raw days of
  records (each with `report.md`, `state.json`, `events.jsonl`) and the defaults, run the
  `consolidate` command in process: 15 tarballs, 30 raw days, the week and month digests for
  the archived days and today exist, `memory/index.md` has 30 day lines,
  `memory.session_payload` starts with `Digests:` and its tokens are at most 6000, the
  export file exists, today's events have `memory.consolidated`; and `consolidate --widget`
  with one pending proposal prints one widget (header `F-1`, record `bin/wuwei memory forget
  F-1 <label>`, options `apply` then `keep`) and writes nothing, exit 1. Fails today: no
  digests, directories instead of tarballs, no `--widget`.
- [X] T032 In `cli/wuwei/commands/consolidate.py`, add `--widget` and the default run of
  plan.md.
- [X] T033 In `tests/test_promotion.py`, add a failing test: the `promote` command with one
  landed proposal calls `memory.export` (patched to record the call), with only rejected
  ones does not, and an export `ValueError` exits 2 with the reason. Fails today: no export
  call.
- [X] T034 In `cli/wuwei/commands/promote.py`, call `memory.export` after a landing.

## Records guard and owner action (FR-010, US2 scenario 6, US4)

- [X] T035 In `tests/test_protect_state.py`, add failing table rows: writes (Write tool,
  `cp`, `mv`, `rm`, `>`) to `.wuwei/memory/digests/2026-W40.md`, `.wuwei/memory/forget.json`
  and `rm -rf .wuwei/memory/digests` are refused with exit 1; `cat` of each is allowed;
  `bin/wuwei memory forget F-1 apply` from an agent tool is refused with the owner reason;
  `bin/wuwei memory show 2026-08-01` and `memory status` are allowed;
  `bin/wuwei consolidate --widget` is allowed. Fails today: digest and forget writes pass,
  the forget command passes.
- [X] T036 In `cli/wuwei/guards/protect_state.py`, add the `_OWNER_ACTIONS` row and the two
  `_protected_name` rules.

## Doctor (FR-014, US1 scenario 6)

- [X] T037 In `tests/test_doctor.py`, add a failing test: a raw day older than
  `consolidation.archive_after_days` gives a `workspace` row `memory tiers` with status
  `warn` and fix `wuwei consolidate`; none gives `ok`; an unreadable `days/` (a symlink) gives
  `unmeasured`. Fails today: no row.
- [X] T038 In `cli/wuwei/commands/doctor.py` `_workspace`, add the row through
  `consolidation.expired`.

## Docs and skill (US6 scenario 2)

- [X] T039 In `tests/test_docs.py`, add a failing test: `configuration.md` names
  `memory.digest`, `memory.budget_tokens`, `memory.export_to` and `archive/<year>/`;
  `concepts.md` `## Memory` names `digest`, `30 days`, `wuwei memory forget` and `CLAUDE.md`;
  `reference.md` names `memory show`, `memory status`, `memory export`, `memory forget` (also
  in the host terminal actions sentence), `consolidate --widget` and `memory tiers` in the
  doctor section; `skills/wuwei-consolidate/SKILL.md` names `consolidate --widget`, `memory
  forget` and `memory show`; add `memory forget` to the command list of
  `test_host_terminal_actions_and_morning_references`. Fails today: none of these phrases.
- [X] T040 Update `docs/site/configuration.md`, `docs/site/concepts.md` (Memory paragraph and
  host terminal actions sentence), `docs/site/reference.md` and
  `skills/wuwei-consolidate/SKILL.md` as plan.md says.

## Finish

- [X] T041 Run the full suite with `python -m pytest -q`; everything passes, including
  `tests/test_cli_known_command.py`, `tests/test_hygiene.py` and `tests/test_stdlib.py`.
- [X] T042 Check every file written for em-dashes, emojis and absolute local paths; remove
  any.
