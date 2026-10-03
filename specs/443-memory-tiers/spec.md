# Feature Specification: Memory tiers over time

**Feature Branch**: `443-memory-tiers`

**Created**: 2026-10-03

**Status**: Ready for planning (design section 5.14 is in the working tree)

**Input**: GitHub issue #443, "feat(memory): memory tiers over time: raw days archived after a
window, a rolling week and month digest that sessions load, promoted rules only in charters,
and forgetting proposed by the retro with evidence", with the owner's addition of 2026-10-03
("no duplicate memory": a one-way export into the harness memory). Owner: "Would be nice to
have a memory compress or something, because as time goes by the number of records can be
hard to manage." Design: `docs/specs/2026-09-24-wuwei-design.md` section 5.14 (added by this
item, spec first), building on 6.3 (index and payload), 6.6 (consolidation) and 6.8
(propose, then promote).

## Root cause (reproduced on main, 23dff23, read-only)

A growth problem, not a crash. The orchestrator notes name no dry-run workspace, so it was
reproduced in a scratch workspace outside the repository: 46 days of `report.md` and
`state.json`, `WUWEI_NOW=2026-10-03T12:00:00+02:00`, `consolidation.archive_days` with a fake
VCS, then `memory.write_index`. Result: 15 days archived, and `memory/index.md` still has 45
day lines (822 estimated tokens for the index alone). Every past day keeps one index line
forever, and SessionStart loads the whole index. Where, with file and line:

1. `cli/wuwei/memory.py` `write_index`, lines 47 to 76: one line per past day from both
   `.wuwei/days/` and `.wuwei/archive/`, with no bound.
2. `cli/wuwei/memory.py` `session_payload`, lines 110 to 122: constraints, the whole spine,
   the whole index and the promote line; no budget and no digest.
3. `cli/wuwei/guards/lifecycle.py` `session_start`, lines 52 to 60: prints the payload and its
   size; nothing compares the size with a budget.
4. `cli/wuwei/consolidation.py` `archive_days`, lines 65 to 108: renames each old day to
   `.wuwei/archive/<date>/` (line 97). Nothing compresses and nothing digests; the window is
   `consolidation.archive_after_days` (`cli/wuwei/workspace.py` line 85).
5. `cli/wuwei/commands/memory.py` lines 7 to 17: `memory` has only `lint`; there is no
   `show`, `status`, `forget` or `export`.
6. `cli/wuwei/commands/close.py` `run`, lines 43 to 55, and `cli/wuwei/commands/consolidate.py`
   `run`, lines 11 to 19: neither writes a digest; consolidate prints findings
   (`consolidation.note_findings`, lines 12 to 62) but proposes nothing the owner can apply.
7. `cli/wuwei/guards/protect_state.py` `_protected_name`, lines 211 to 243: `archive/` is
   protected (line 222); there is no digest or forgetting record to protect yet.
8. `cli/wuwei/interview.py` `_recorded`, lines 447 to 464: reads answers from
   `archive/*/interview.json`; once a day is a tarball that glob finds nothing and answered
   calibration questions would be asked again.
9. `cli/wuwei/promotion.py` `_apply`, lines 141 to 153: a `patch` needs nonempty text, so a
   charter rule cannot be removed through the one producer.
10. `cli/wuwei/commands/doctor.py`: no row looks at memory growth.

Already in place and reused: `consolidation.archive_days` (the one archiver),
`consolidation.note_findings` (near-duplicate notes, near-duplicate and contradicting charter
rules), `promotion._apply` and the landing loop in `promotion.promote` (ledger, changelog,
workspace commit, note archive under `memory/archive/`), `memory.estimated_tokens`,
`memory.constraints`, `report.decisions`, `signal.classify` (page tier), `outward.lint`,
`redact.known_values`, `workspace.atomic_write`, `state.append_event`, `watch.records`,
`decision.widget`, `decision.gate`, `decision.evaluate` and `decision.table`,
`decision.owner_confirm`, the `_OWNER_ACTIONS` table, `commands.READ_ONLY` and `WRITES`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Old days become a tarball and a digest; the session payload stays bounded (Priority: P1)

The owner runs WUWEI for weeks. Weekly `consolidate` packs days older than the window into
`archive/<year>/<date>.tar.gz`, writes week and month digests, and SessionStart loads the
digests first and stays within the token budget.

**Why this priority**: it is the owner's request and the first acceptance criterion.

**Independent Test**: build a 45-day workspace in `tmp_path` with a fake VCS, run
`consolidate`, then `memory.session_payload`.

**Acceptance Scenarios**:

1. **Given** a workspace with 45 days of records and the defaults, **When** `wuwei
   consolidate` runs, **Then** the 15 days older than 30 are `archive/<year>/<date>.tar.gz`
   files (no `days/<date>/` left for them), the ISO week and month digests covering those
   days and today exist under `memory/digests/`, `memory/index.md` lists only the 30 raw
   days, and `session_payload` returns content that starts with `Digests:` and whose
   estimated tokens are at most `memory.budget_tokens`.
2. **Given** a legacy `archive/<date>/` directory from before this change, **When**
   `consolidate` runs, **Then** it becomes `archive/<year>/<date>.tar.gz` like a raw day.
3. **Given** a day, **When** `wuwei close` passes, **Then** the current week digest is
   rebuilt and contains that day's decisions, lessons, metrics, incidents and items in the
   fixed shape; running close again leaves the file byte-identical.
4. **Given** a day whose decision question or ledger reason contains a path, a word the
   outward lint refuses, or a loaded secret, **When** its digest is built, **Then** that line
   keeps only its structured fields and the digest contains none of that text.
5. **Given** a payload that would exceed `budget_tokens`, **When** SessionStart runs,
   **Then** the payload holds the digests and rules only and one line says the today tier
   was left out and how to read it.
6. **Given** a raw day older than the archive window, **When** `wuwei doctor` runs,
   **Then** a `memory tiers` row warns with the fix `wuwei consolidate`.

---

### User Story 2 - Forgetting is proposed with evidence and applied only on approval (Priority: P1)

`consolidate` proposes what to forget, each with one evidence line. The session asks each
proposal as a widget; only the owner's approval applies it, and the before text stays in
the archive with a ledger line and a `memory.folded` event.

**Why this priority**: second acceptance criterion; forgetting without a record loses
history.

**Independent Test**: a note created 90 days ago and named by no brief, decision or retro;
run `consolidate`, then `memory forget F-1` with the host confirmation faked yes and no.

**Acceptance Scenarios**:

1. **Given** an active note past probation, created more than 60 days ago, that no
   `briefs/`, `decisions/` or `retro/` record of the last 60 days names, **When**
   `consolidate` runs, **Then** `memory/forget.json` holds a pending `F-1` (kind
   `unreferenced`, action `archive`, the note as target) with an evidence line naming the
   window, the note is unchanged, and consolidate prints the proposal and exits 1.
2. **Given** that proposal, **When** `wuwei consolidate --widget` runs, **Then** it writes
   nothing and prints one widget per pending proposal (header `F-1`, the morning gate
   citation, the evidence line, options `apply` recommended and `keep`) with record
   `bin/wuwei memory forget F-1 <label>`, and exits 1 (0 when none is pending).
3. **Given** `wuwei memory forget F-1 apply` at the host terminal and the owner's y, **Then**
   the note is moved to `memory/archive/` by the promote landing, the ledger has a `landed`
   line, today's events have one `memory.folded` event naming `F-1`, the action, the target
   and the archive path, and the proposal is `applied`. On n nothing changes, the proposal
   stays pending, exit 1.
4. **Given** `wuwei memory forget F-1 keep`, **Then** nothing moves, no event is written, the
   proposal is `declined`, and the next `consolidate` does not propose it again.
5. **Given** two near-duplicate notes, a charter rule followed later in the same charter by
   a near-duplicate rule, and a charter rule that an answered decision in the raw window
   contradicts, **When** `consolidate` runs, **Then** it proposes a `fold`, a `drop` of the
   earlier rule and a `drop` of the contradicted rule, each with its evidence line; applying
   a `drop` removes exactly that line from the charter and appends it to
   `memory/archive/dropped-rules.md`.
6. **Given** a seat in an agent tool, **When** it runs `wuwei memory forget F-1` or writes
   `memory/forget.json`, **Then** the guards refuse it like every other owner action and
   producer-only record.

---

### User Story 3 - An archived day still reads (Priority: P1)

**Independent Test**: archive a day in `tmp_path`, then call the command in process.

**Acceptance Scenarios**:

1. **Given** `wuwei memory show <archived date>`, **Then** the day's records print from the
   tarball, each under a `== <relative path> ==` line, exit 0.
2. **Given** a raw date, **Then** the same output comes from `days/<date>/`.
3. **Given** a date with neither, **Then** exit 1 with `no records for <date>`; a corrupt or
   unsafe tarball exits 2 with the reason.
4. **Given** an answered calibration question recorded in a day that is now a tarball,
   **When** the morning gate builds its interview widgets, **Then** that question is not
   asked again.

---

### User Story 4 - Digests and archives are producer-only records (Priority: P1)

**Independent Test**: table test through `protect_state.check_bash` and the write guard.

**Acceptance Scenarios**:

1. **Given** the records guard, **When** a seat writes, moves or removes
   `.wuwei/memory/digests/<file>`, `.wuwei/memory/forget.json` or anything under
   `.wuwei/archive/`, **Then** it is refused like the rest of the records; reading them is
   allowed (#349).

---

### User Story 5 - One memory: a one-way export into the harness memory (Priority: P2)

**Independent Test**: call `memory.export` in `tmp_path` twice and with bad targets.

**Acceptance Scenarios**:

1. **Given** local charter overrides with rule lines and a week digest with lessons, **When**
   `wuwei memory export --claude` runs, **Then** the workspace's `CLAUDE.md` (or the file
   `memory.export_to` names) holds one block between `<!-- wuwei:memory:start -->` and
   `<!-- wuwei:memory:end -->` with those lines; text outside the markers is unchanged.
2. **Given** the same inputs, **When** it runs again, **Then** the file is byte-identical and
   not rewritten.
3. **Given** an `export_to` that is absolute, contains `..`, points into `.wuwei/` or through
   a symlink, or a file with a start marker and no end marker, **Then** exit 2 with the
   reason and the file is untouched.
4. **Given** `consolidate`, or `promote` with at least one landed proposal, **Then** the
   export runs at its end.
5. Nothing reads the harness memory back.

---

### User Story 6 - The owner sees the tiers (Priority: P2)

**Acceptance Scenarios**:

1. **Given** `wuwei memory status`, **Then** it prints one line per tier (raw days and bytes,
   archived days and bytes, digests and tokens, rules and tokens), the payload tokens against
   `budget_tokens`, the last consolidate date (or `none`) and the pending proposals count,
   exit 0; unreadable records exit 2.
2. `configuration.md` documents `memory.digest`, `memory.budget_tokens`, `memory.export_to`
   and the archive window; `concepts.md` has one paragraph on what is kept, for how long and
   why; `reference.md` lists `memory show`, `status`, `forget` and `export` and names `memory
   forget` among the host terminal actions; the consolidate skill describes the new steps.

### Edge Cases

- `consolidation.archive_after_days = 0`: every past day is archived; the week digest is
  still rebuilt, from tarballs.
- `memory.digest = "off"`: close and consolidate write no digest; the payload has no
  `Digests:` section; archiving still runs.
- The digests and rules alone exceed the budget: they are still loaded, and the budget line
  says so; `session_start` exits 1 for it, like a memory lint finding.
- A tarball destination already exists: refuse (exit 2), as the directory move does today.
- A day directory or tarball that is a symlink, or a tar member with an absolute path, `..`
  or a link: refuse; members are only regular files and directories under `<date>/`.
- A proposal whose target changed since consolidate (note gone, rule line no longer present
  exactly once): the landing rejects it as `promote` would (a `rejected` ledger line), no
  `memory.folded` event, the proposal stays pending, `memory forget` exits 1 with the reason.
- An unknown or already applied or declined `F-n`: exit 1, nothing written.
- No `plan.md` today: a widget question would fail the question guard, so the owner runs
  the record command at the host terminal, as with `close --widget`.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `consolidation.archive_days` packs every `days/<date>/` older than
  `consolidation.archive_after_days`, and every legacy `archive/<date>/` directory, into
  `archive/<year>/<date>.tar.gz` (gzip, members under `<date>/`), verifies the tarball lists
  every source file, then removes the source; it commits the tarballs, the digests it wrote
  and `memory/index.md` through the existing VCS port.
- **FR-002**: One reader, `consolidation.day_records(root, day)`, returns a day's records as
  `{relative name: text}` from `days/<date>/`, a legacy `archive/<date>/` or the tarball,
  refusing symlinks and unsafe members. `memory show`, the digest builder, the forgetting
  scan and `interview._recorded` use it.
- **FR-003**: `memory.write_index` lists raw days only; a tarball's year directory is not a
  date and the existing loop already skips it. Archived days are represented by digests.
- **FR-004**: A digest builder `digest.build(root, title, dates)` produces the fixed shape of
  section 5.14 (title line, then `## Decisions`, `## Lessons`, `## Metrics`, `##
  Incidents`, `## Items`, `none` for an empty section, each line prefixed by its date).
  A line with free text is kept only when it passes `outward.lint(line, 'digest', config,
  to_owner=True)`, has no path-like token and is unchanged by `redact.known_values`;
  otherwise it keeps only its structured fields.
- **FR-005**: `digest.write(root, day, period)` rebuilds the week or the month containing
  `day` and writes it atomically only when the text changed. `close` calls it for the week
  after `closing.check` passes; `consolidate` calls it for the week and month of each
  archived day and of today. `memory.digest = "off"` makes it a no-op.
- **FR-006**: `memory.session_payload` builds, in order, `Digests:` (latest month digest,
  then latest week digest), `Rules:` (spine, then the note lines of the index), `Today:`
  (raw day lines of the index, `Full day state: wuwei state get`, the promote line). When
  the estimated tokens exceed `memory.budget_tokens` it returns digests and rules only plus
  one line: `Memory budget: <n> of <budget> estimated tokens; today left out (wuwei state
  get, wuwei memory status).` The `Active constraints:` block leaves the payload:
  `lifecycle.session_start` prints `memory.constraints` right after the orientation block,
  so #358 keeps it before line 25.
- **FR-007**: `consolidation.forget_proposals(root)` returns the four kinds of section 5.14
  with one evidence line each; `consolidate` merges them into `memory/forget.json` (new ids
  `F-n`; a pending or declined proposal with the same kind, target and rule text is not
  added again) and prints each pending one.
- **FR-008**: `wuwei consolidate --widget` prints the pending proposals as widgets and
  writes nothing. `wuwei memory forget F-n apply|keep` is an owner action
  (`_OWNER_ACTIONS`, refused in agent tools). `apply` asks y/N at the host terminal
  (`integrity._host_confirm`, injectable as in `commands/config.py`); on y it lands the
  change through the promote landing (ledger, changelog for charters, workspace commit,
  before text under `memory/archive/`), appends `memory.folded`, marks the proposal
  `applied` and runs the export. `keep` marks it `declined` and writes nothing else.
- **FR-009**: `promotion._apply` accepts a `patch` with empty `text` on a charter target as
  the removal of exactly one `old_text` line, and appends the removed line with the date and
  charter name to `memory/archive/dropped-rules.md`, returned with the changed paths so the
  same commit carries it. The promote loop body becomes `promotion.land`, shared by
  `promote` and `memory forget`.
- **FR-010**: `protect_state._protected_name` protects `memory/digests` and its files and
  `memory/forget.json`; `archive/` stays protected. `memory.folded` and
  `memory.consolidated` get their producers in `EVENT_PRODUCERS`.
- **FR-011**: `wuwei memory show <date>` and `wuwei memory status` are read-only;
  `wuwei memory export --claude` and `wuwei memory forget` write. All are registered and
  classified in `commands.READ_ONLY` or `WRITES`.
- **FR-012**: `memory.export(root)` writes the block of User Story 5; `consolidate` and
  `promote` (when a record landed) call it; an error is exit 2 with the reason.
- **FR-013**: `[memory]` gains `digest` (`"week"` or `"off"`, default `"week"`),
  `budget_tokens` (int >= 1, default 6000) and `export_to` (default `"CLAUDE.md"`); the
  template config and `configuration.md` list them.
- **FR-014**: `doctor` adds a `workspace` row `memory tiers`: warn when a raw day is older
  than the archive window (fix `wuwei consolidate`), ok otherwise, unmeasured on a read
  error.
- **FR-015**: Every new command exits 0 clean, 1 findings, 2 could not run, with the reason.

### Key Entities

- **Week or month digest**: Markdown under `memory/digests/`, fixed shape, rebuilt from day
  records (`data-model.md`).
- **Forgetting proposal**: a row in `memory/forget.json` keyed `F-n` (`data-model.md`).
- **Archived day**: `archive/<year>/<date>.tar.gz`, the raw day unchanged.
- **Export block**: the marked block in the workspace `CLAUDE.md` (`data-model.md`).

## Success Criteria *(mandatory)*

- **SC-001**: In the 45-day fixture the SessionStart payload is at most `budget_tokens` and
  starts with `Digests:`; `memory/index.md` has 30 day lines, not 45.
- **SC-002**: Index day lines stop growing past the archive window: after more than 30 days
  the index holds 30 day lines.
- **SC-003**: No forgetting changes a note or a rule without an owner yes, a ledger line, a
  `memory.folded` event and the before text under `memory/archive/`.
- **SC-004**: Every archived day prints with `wuwei memory show`.
- **SC-005**: The full suite passes; no new runtime dependency (`tarfile` is stdlib).

## Assumptions

- The archive window stays `consolidation.archive_after_days` (default 30). The issue names
  `[memory] archive_after_days`, but the key already exists under `[consolidation]` in every
  shipped config; a second key would be an unknown key that the strict posture refuses
  (#353), or two knobs for one value. Design 5.14 says so.
- `budget_tokens` defaults to 6000. The owner's live payload is not available here (owner
  data stays out of the repository); a fresh workspace measures 76 tokens and the index of a
  45-day workspace alone 822. 6000 holds two digests, a 60-note index, 30 day lines and the
  spine with room, about 3 percent of a 200k context. The owner can change it.
- `digest` accepts `"week"` and `"off"`. Months are always built by consolidate from the same
  builder; a month-only mode was not asked for.
- The month digest is rebuilt from the month's day records (raw or tarball) with the week's
  builder, which gives the week lines folded into the month without parsing Markdown back.
- Metrics come from the day's `report.md` outcome lines (`## Outcome` or `## Changed`), the
  report's own voice. The #421 effectiveness metrics are not on main (#422 implements them)
  and join the Metrics section when that lands. A day without `report.md` shows
  `unmeasured`.
- Incidents are the day's page-tier events (`signal.classify`), counted by kind.
- "Referenced" means the note slug, as a whole word or as `notes/<slug>.md`, appears in a
  file under `briefs/`, `decisions/` or `retro/` of a day in the last 60 days, raw or
  archived. The 60 days are a fixed value, not configuration.
- "Superseded lesson": two near-duplicate rule lines (the existing
  `consolidation.similarity_threshold`) in the same local charter; the earlier line is
  superseded, since promote appends. Cross-charter near-duplicates stay findings only.
- "Contradicted by a later decision": the chosen option's description of an answered
  decision in the raw window and a local charter rule fail the existing do or never check of
  `note_findings`. A deliberately narrow heuristic.
- Forgetting targets only WUWEI-authored files (local charter overrides and notes), never
  plugin charters or owner notes; `promotion._target` already refuses those.
- `memory forget` is a host terminal owner action with a y/N for `apply`. Letting the planner
  record an `F-n` answered at its morning gate (#354, `_GATE_EDITS`) is left out; add it if
  the weekly host run proves a burden. The widgets come from `consolidate --widget` (as
  `close --widget`), since an owner verb cannot also be in `commands.READ_ONLY`.
- Answering `keep` declines for good; a declined target is proposed again only if its kind,
  target or rule text changes.
- The export writes into the workspace root, which is normally not a Git repository; when it
  is, `CLAUDE.md` changes like any generated file. Export for other harness rules files waits
  for #441.
- Index note lines count as rules and index day lines as today, split by the existing line
  shapes (`<slug> | ...` and `<date> | ...`).
- `Active constraints:` is orientation (#358), not memory: it stays at every SessionStart
  before line 25, outside the budget. This keeps #358 SC-002 and this issue's "payload starts
  with the digests" both true.
- Per AGENTS.md strict mode, clarify, analyze and checklist follow in the pipeline after this
  step; no clarification marker is left open.
