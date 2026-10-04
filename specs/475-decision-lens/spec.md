# Feature Specification: every option carries a title, rationale and consequence, the recommendation carries its reasoning, the Ask card shows all of it, and a configurable lens per decision class is applied and recorded

**Feature Branch**: `475-decision-lens`

**Created**: 2026-10-04

**Status**: Draft

**Input**: GitHub issue #475, "feat(decisions): every option carries a title, rationale and
consequence, the recommendation carries its reasoning, the Ask card shows all of it, and a
configurable lens per decision class (SOLID, twelve-factor, YAGNI, ponytail for engineering)
is applied and recorded". Owner-requested 2026-10-04: "when asked, I see the options with the
recommended option, but for me it is important to have a title, a rationale for each option,
and the recommendation. [...] For engineering and architecture decisions I'd like to use
SOLID, twelve-factor, YAGNI, ponytail type guidelines, so we always make a well informed
choice."

## Current behaviour (read and reproduced on main, 963a839)

Reproduced read-only with a scratch script outside the repository that prints `decision
template`, lints it, and builds its widget. The notes name no dry-run workspace; none is
needed.

1. The Ask card shows option ids, not titles, and no reasoning. `record_widget`
   (`cli/wuwei/decision.py:165-173`) sets `label` to the option id and `description` to the
   one-line Options description with `Recommended. ` in front; the question is
   `D-n: <Question>`. Built from the template:
   `{'label': 'A', 'description': 'Recommended. Make the scoped change'}`. The scores exist
   (`_scored`, `decision.py:53-74`); why an option scores as it does, what choosing it
   changes, and why the recommendation wins never reach the owner.
2. A record cannot carry its class. `FIELDS` (`decision.py:11-13`) has no `Class`, so the
   parser in `evaluate` (`decision.py:80-90`) appends a `Class: approach` line written after
   `Question:` to the Question text, and the one-line check (`decision.py:94-96`) then
   refuses the record with "Question: expected one line; a WUWEI record failed its
   consistency check". Design 5.8 lists `Class:` as a record field and says the lint refuses
   an unknown class; neither holds today. Telemetry (`telemetry.py:171`) and `why`
   (`commands/why.py:211`) already read an optional `Class:` row and count a missing one as
   `other`.
3. There is no lens. Nothing asks engineering decisions to be checked against SOLID,
   twelve-factor, YAGNI or the ponytail rule, and `[decisions]` has no `lenses` key.
4. The decision classes (`decision.CLASSES`, design 5.8.1) have no `design`, `boundary` or
   `refactor`; the issue's `dependency` is the existing `dependency-bump`.

## User Scenarios & Testing

### User Story 1 - A new record explains every option and the recommendation (Priority: P1)

A seat (or the CLI) writing a new decision record gives each option a title, a rationale and
a consequence, gives the recommendation its reasoning, and names the record's class. The
decision lint refuses a new record that misses any of them and names the field.

**Why this priority**: everything the owner sees comes from the record; without the fields
nothing downstream can show them.

**Independent Test**: `python -m pytest -q tests/test_decision.py -k "explained or lens"`.

**Acceptance Scenarios**:

1. **Given** a new `design`-class record from the arch sentinel with a title, rationale and
   consequence per option, one line per configured lens per option, a class and a one-line
   reasoning, **When** the decision lint runs, **Then** it exits 0.
2. **Given** the same record missing any one of: `Class:`, the `Title`, `Rationale` or
   `Consequence` column (or a cell in it), `Reasoning:`, the `Lenses:` table, one lens row,
   or one lens cell, **When** the lint runs, **Then** it exits 1 and the message names the
   missing field (for a lens, the lens name).
3. **Given** a record with `Class: desing` (unknown), **Then** the lint exits 1 naming
   `Class` and listing the classes.
4. **Given** a record whose `Class:` line comes after `Question:`, **Then** the Question
   stays one line and the record lints clean (current behaviour 2 is gone).
5. **Given** a record written before this change (`| Option | Description |`, no `Class:`,
   no `Reasoning:`) read by a history reader (the weekly re-ask, consolidation, external
   waits, `why`), **Then** it still evaluates as today; only the lint, `decision write` and
   the widget refuse it.

### User Story 2 - The Ask card shows titles, rationale, consequence, lens lines and reasoning (Priority: P1)

**Why this priority**: it is what the owner asked for; the card is where the owner decides.

**Independent Test**: `python -m pytest -q tests/test_decision.py -k widget`.

**Acceptance Scenarios**:

1. **Given** `decision show D-n --widget` on a valid design record, **Then** each option's
   `label` is its title, the first (recommended) one ending in ` (Recommended)`; each
   `description` is the rationale, then the consequence, then one `<lens>: <line>` per lens;
   the `question` is `D-n: <Question> <first sentence of Reasoning>`; the header is `D-n`,
   at most four options are shown, and the widget's limits (header at most 12 characters,
   2 to 4 options) hold.
2. **Given** `owner.verbosity.decisions` resolving to `brief` (the default), **Then** each
   part of the description is cut to its first sentence; at `standard` or `full` each part is
   whole.
3. **Given** the owner picks a label, **When** the widget's record command runs
   (`wuwei decide D-n "<label>"`), **Then** the title, with or without ` (Recommended)`, or
   the option id, records that option; a label matching no option exits 1 as today.
4. **Given** the MCP registry decision widget, **Then** its `proceed` option still carries
   the findings lines and `wuwei mcp decide D-n "<label>"` accepts the title.

### User Story 3 - A configurable lens per decision class (Priority: P1)

**Why this priority**: the owner wants every engineering choice checked against the same
guidelines, and to add a company rule of their own.

**Independent Test**: `python -m pytest -q tests/test_decision.py tests/test_workspace.py -k lens`.

**Acceptance Scenarios**:

1. **Given** no `[decisions.lenses]` in config, **Then** a record of class `design`,
   `boundary`, `refactor` or `dependency-bump` needs one row for each of `SOLID`,
   `twelve-factor`, `YAGNI` and `ponytail`.
2. **Given** `[decisions.lenses]` with `company-rule = "Does it follow our data retention
   rule?"`, **Then** every design decision needs a `company-rule` row, the lint names it when
   missing, and the card shows `company-rule: <line>` on every option.
3. **Given** `[decisions.lenses]` with `YAGNI = ""`, **Then** YAGNI is dropped: not required,
   and a `YAGNI` row is refused as an unknown lens.
4. **Given** a prioritisation decision (class `re-plan`, `defer` or `scope-cut`), **Then**
   no `Lenses:` table is required, and the plan lint's WSJF or RICE evidence lines are
   unchanged. Reversibility keeps its one-way or two-way door test, unchanged.
5. **Given** a lens name outside `[A-Za-z][A-Za-z0-9_-]*`, **Then** the config check refuses
   it, naming the key.

### User Story 4 - `decision show` and the DM print the new fields (Priority: P2)

**Independent Test**: `python -m pytest -q tests/test_decision.py -k present tests/test_control_plane.py`.

**Acceptance Scenarios**:

1. **Given** `decision show D-n` at `brief` (and the DM at `brief`), **Then** each option line
   shows its title, score and consequence, and the recommendation line ends with the
   reasoning.
2. **Given** `standard`, **Then** each option also shows its rationale and its lens lines.
3. **Given** `full` (or `--full`, or `more D-n` in the DM), **Then** the record text is
   printed whole, as today.
4. **Given** a record written before this change, **Then** brief and standard print as today.

### User Story 5 - Charters, planner skill and docs say it (Priority: P2)

**Independent Test**: `python -m pytest -q tests/test_charters.py tests/test_docs.py`.

**Acceptance Scenarios**:

1. **Given** the common charter, **Then** its decision rule lists `Class:`, the
   `Title | Rationale | Consequence` columns, `Reasoning:` and the `Lenses:` table.
2. **Given** the lead, arch sentinel and builder charters, **Then** each says when a decision
   is `design` (or `boundary`, `refactor`, `dependency-bump`) class and that its lens lines
   are mandatory; the generated `agents/*.md` match (`bin/wuwei agents check`).
3. **Given** `skills/wuwei-plan/SKILL.md`, **Then** it says the decision card shows titles
   with the recommended first, rationale, consequence and lens lines, and the reasoning.
4. **Given** `docs/site/concepts.md`, **Then** it explains the record shape and lenses in
   plain words and its glossary has `Lens`; `docs/site/configuration.md` lists
   `decisions.lenses`.

### Edge Cases

- More than four options: the card shows the recommended one and the next three, as today;
  the others stay answerable through Other.
- All default lenses dropped and none added: no `Lenses:` table is required for any class.
- A `Lenses:` table on a non-engineering record is ignored by the lint and not shown.
- Two options with the same title (case-insensitive): refused, since a label must name one
  option.
- A title with `"`, a backtick, `$` or a backslash, or over 40 characters: refused, since the
  label is pasted into a double-quoted record command and shown as a short label.
- A `Reasoning:` that spans two lines: refused (one line); the card uses its first sentence.
- A CLI-written record (scanner, day close, PR scope, MCP registry x2, build park, retro hard
  rule, remote denial) is a new record and carries the new fields and a class.

## Requirements

### Functional Requirements

- **FR-001**: The record parser reads `Class:`, `Reasoning:` and `Lenses:` as fields of their
  own. `Class:` and `Reasoning:` are one line. A present `Class:` must be a 5.8.1 class.
- **FR-002**: A new record (checked by `decision lint`, the PostToolUse write lint, the
  question guard, `decision write` and `decision show --widget`) must have: `Class:`; an
  Options table with columns `Option | Title | Rationale | Consequence` and no empty cell;
  titles unique (case-insensitive), at most 40 characters, without `"`, backtick, `$` or
  backslash; a one-line `Reasoning:`; and, for an engineering class, a `Lenses:` table
  `| Lens | <option ids> |` with exactly one row per configured lens and no empty cell. Each
  refusal names the field or the lens.
- **FR-003**: The Do nothing or Defer rule reads the title (column 2), as it reads the
  description today.
- **FR-004**: History readers keep reading records written before this change: an Options
  table `| Option | Description |` without `Class:` or `Reasoning:` still evaluates.
- **FR-005**: Classes `design`, `boundary` and `refactor` join 5.8.1 at default L0, ceiling
  L3. The engineering classes are `design`, `boundary`, `refactor` and `dependency-bump`.
- **FR-006**: `[decisions.lenses]` maps a lens name to its one-line question. Defaults:
  `SOLID`, `twelve-factor`, `YAGNI`, `ponytail`. A configured name adds or replaces a lens;
  an empty question drops it. The config check refuses a name outside
  `[A-Za-z][A-Za-z0-9_-]*`.
- **FR-007**: The decision widget: label is the title, ` (Recommended)` on the first;
  description is rationale, consequence and lens lines, each cut to its first sentence at
  `brief`; the question ends with the first sentence of `Reasoning`; the record command is
  `wuwei decide D-n "<label>"`.
- **FR-008**: `decide`, `decision outcome` and `mcp decide` accept an option id or a title,
  with or without ` (Recommended)`.
- **FR-009**: `decision show` at brief adds each option's consequence and the reasoning; at
  standard also the rationale and lens lines. The DM uses the same text.
- **FR-010**: `decision template` prints a valid `design` record with the configured lens
  rows and the lens questions in an HTML comment.
- **FR-011**: Every CLI-written decision record carries the new fields and a class.
- **FR-012**: Charters, the planner skill, concepts, configuration and the design spec (5.8,
  5.8.1) describe the record shape, the classes and the lenses.

### Key Entities

- **Option row**: id, title (short name, the card label), rationale (why it scores as it does
  against the musts and wants), consequence (what changes if chosen, what it costs, what it
  closes).
- **Reasoning**: one line under the recommendation: the one or two wants that decided it and
  what would flip it.
- **Lens**: a name and a one-line question every option of an engineering decision answers in
  one line. See `data-model.md`.

## Success Criteria

- **SC-001**: The four acceptance lines of issue #475 each have a passing test.
- **SC-002**: Records written before this change still count in the weekly re-ask,
  consolidation and external waits (their existing tests pass on legacy fixtures).
- **SC-003**: The full suite passes; no new runtime dependency.

## Assumptions

- "Every new record" is enforced where records are written or asked about (the lint, the
  question guard, `decision write`, `decision show --widget`), not in `evaluate` for every
  reader: history readers skip a record that fails `evaluate`
  (`consolidation.py:263-268`, `interview.py:600-604`), so requiring the fields there would
  silently drop every earlier record from the weekly re-ask and the cruise evidence.
- `Class:` becomes required for a new record. The lens is mandatory by class, so a record
  without a class would skip it; design 5.8 already lists `Class:` as required. Records
  before this change are exempt as above.
- The title takes the place of today's one-line description (column 2 of Options), so no
  option carries both; the card label today is the bare option id, which is what the owner
  is missing.
- "Engineering and architecture decisions (class `design`, `dependency`, `boundary`,
  `refactor`)": `dependency` is the existing `dependency-bump`; `design`, `boundary` and
  `refactor` are new 5.8.1 classes (the issue is the owner's amendment), each at L0 with
  ceiling L3 like the other beyond-the-item classes. `approach` stays outside: at L2 it is an
  assumption, not a record.
- "Any decision raised by the arch sentinel or a builder": a record does not say who wrote
  it, so the lint enforces by class and the arch sentinel and builder charters name the
  engineering class for every how-to-build decision they raise. A builder's `park` record
  stays `park`.
- Prioritisation and reversibility already have their lens (the plan lint's framework
  evidence, the one-way or two-way door); they are not configured under
  `[decisions.lenses]`, which holds the engineering set only.
- "Within the widget's size" means the limits `decision.widget` already checks (header at
  most 12 characters, 2 to 4 options); AskUserQuestion publishes no description length. The
  verbosity trim (first sentence at brief) is the size control; there is no character cap.
- Adding classes to the telemetry vocabulary keeps `schema` at 1: the definition of
  `decisions_by_class` ("per 5.8.1 class") is unchanged, only the list it points to grows.
- The record command quotes the label (`"<label>"`), like `wuwei calibrate --answer
  "<id>=<label>"` does today, because titles have spaces.
- Fixtures are neutral (options A, B; generic titles).

## Deferred

- Detecting placeholder answers (a lens cell left as template text) is not checked, the same
  as the template's Context today.
- Recording who raised a decision (a `Raised-by:` field) so the lint can enforce the lens by
  author: not needed while the charters name the class.
