# Feature Specification: Verbosity levels for what the owner reads, and humanizer-checked text

**Feature Branch**: `303-owner-verbosity`
**Created**: 2026-10-01
**Status**: Ready
**Input**: GitHub issue #303, "feat(owner): verbosity levels for everything the owner reads, and
humanizer-checked text from seats and the CLI". Owner request 2026-10-01: "control the level of
verbosity ... I don't like when I need to read too much, because it makes the decisioning
difficult ... always use humanizer skill for the texts".

## Problem (reproduced)

Reproduced read-only on `main` (56e9107) from this worktree with `bin/wuwei` and the record
`bin/wuwei decision template` prints (23 lines):

- `control_plane.render('D-1', fields, 'summary')` returns
  `D-1: Which option should we take?\nA: Make the scoped change\nB: Defer until more evidence exists`.
  The owner's DM shows no score and no recommendation, so the owner cannot decide from it and
  has no way to ask for the rest from the phone.
- `bin/wuwei decision show D-1` exits 2 with `invalid choice: 'show' (choose from 'template',
  'lint', 'route', 'outcome')`. On the host the only way to read a pending decision is the raw
  23-line record.

Root causes, with file and line on `main`:

1. `cli/wuwei/control_plane.py` `render` (lines 70 to 74) prints the question and the option
   descriptions only; `pending` (lines 31 to 44) drops the scores `decision.evaluate` computed.
   `escalate` (lines 81 to 91) and `poll_replies` (line 116) send that text.
2. `cli/wuwei/commands/decision.py` `register` (lines 12 to 25) has no read command for a
   decision; nothing presents a pending decision in a short form.
3. `cli/wuwei/workspace.py` `SCHEMA['owner']` (lines 41 and 42) has no verbosity key, so no
   output can be shaped for the owner. `brief.style.length` (line 61) shapes seat briefs only.
4. `cli/wuwei/interview.py` `QUESTIONS` (lines 66 to 160) has no question about how much the
   owner wants to read.
5. `cli/wuwei/remote.py` `parse` (lines 65 to 85) and `VOCABULARY` (lines 18 and 19) have no
   command that returns the rest of a decision.
6. `cli/wuwei/report.py` `build` (lines 39 to 83) always prints every section with the full
   metrics JSON; nothing leads with what changed.
7. `charters/_common-authoring.md` and `skills/wuwei-plan/SKILL.md` say nothing about the
   humanizer skill or AI writing tells; seats write records, PR bodies and drafts in the default
   model voice.
8. `cli/wuwei/outward.py` `lint` (lines 35 to 84) checks banned characters, patterns, length
   and voice; it has no notion of a structural writing tell, and `cli/wuwei/metrics.py`
   `collect` (lines 498 to 575) has no metric for them.

Already in place and reused: the digest (`cli/wuwei/watch.py` `digest`, line 108) is one line
per decision; the PR nudge (`cli/wuwei/listen.py` `notify`, lines 39 to 59) is one line; the
em-dash and emoji refusal lives in `outward.lint` through `outward.banned_characters`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A pending decision in a few lines, the rest on request (Priority: P1)

The owner reads a pending decision as its question, one line per option with its score, and the
recommendation with one reason, on the host and in the DM, and asks for the full record only when
needed.

**Why this priority**: this is the owner's complaint; decisions are where reading load blocks work.

**Independent Test**: route a decision, run `wuwei decision show D-n` and `--full`, escalate it
through a fake transport and send `more D-n` through `remote.handle`.

**Acceptance Scenarios**:

1. **Given** `owner.verbosity` at its default (`brief`) and a routed owner decision D-3, **When**
   the owner runs `wuwei decision show D-3`, **Then** it prints the question, each option on one
   line with its score (and `fails a must` where it does), and `Recommended: <id>, <one reason>`,
   under 12 lines in total, and exits 0.
2. **Given** the same decision, **When** the owner runs `wuwei decision show D-3 --full`, **Then**
   it prints every field of the record (Question to Outcome, tables included).
3. **Given** `brief`, **When** the listener escalates D-3 to the owner DM, **Then** the DM starts
   with the same brief text `decision show D-3` prints and does not contain `Context` or
   `Pre-mortem`.
4. **Given** D-3 pending, **When** the owner sends `more D-3` in the DM, **Then** the reply is the
   full form of D-3; for an id that is not pending the reply says so and exits 1.
5. **Given** `owner.verbosity.decisions = "standard"`, **When** the owner runs `decision show
   D-3`, **Then** the output adds the first Context line, Confidence, Reversibility, Blast radius,
   Pre-mortem and Revisit to the brief text.

### User Story 2 - One setting, asked once, shaped per surface (Priority: P1)

The owner sets how much the CLI prints and sends, once in the interview or in config, and can
override it for decisions, digest, nudges, DM and report.

**Why this priority**: without the setting, every surface stays at one length.

**Independent Test**: interview answer to settings; config validation; one test per surface at
`brief` and `full`.

**Acceptance Scenarios**:

1. **Given** the interview, **When** the owner answers the `verbosity` question with `Brief`,
   `Standard` or `Full`, **Then** its effect is `owner.verbosity.default` set to that level and
   `config promote` can apply it.
2. **Given** `owner.verbosity.default = "full"` and `owner.verbosity.dm = "brief"`, **Then** the
   DM uses `brief` and every other surface uses `full`.
3. **Given** an unknown level such as `owner.verbosity.default = "short"`, **Then** loading the
   config fails with a configuration error.
4. **Given** `brief` for the report, **When** `wuwei report` runs, **Then** the report leads with
   a `## Changed` section of at most three outcome lines whose value differs from the baseline
   (or `none`), keeps the Merged, Open at close, Parked, Decisions answered and Carry sections,
   and leaves out Outcome, Quality by band and Process metrics; at `standard` it is today's
   report unchanged.
5. **Given** `full` for the digest, **Then** each digest line ends with its record path
   `(decisions/D-n.md)`; at `brief` and `standard` it is today's digest.
6. **Given** `brief` or `standard` for nudges, **Then** the PR change DM is today's single line;
   at `full` it adds the changed probe field names.

### User Story 3 - Seats write for a person with the humanizer skill (Priority: P2)

Every text a seat writes for a person is rewritten with the `humanizer` skill in embedded mode
when it is installed, and checked against a ten-line checklist when it is not.

**Why this priority**: the owner asked for it; it changes seat prose, not mechanics.

**Independent Test**: a docs test over the charters, the generated agents and the planner skill.

**Acceptance Scenarios**:

1. **Given** the role charters and the planner skill, **Then** every generated agent file under
   `agents/` and `skills/wuwei-plan/SKILL.md` names the `humanizer` skill for texts written for a
   person, every generated agent carries the ten checklist lines, and the planner skill points to
   that checklist.
2. **Given** the checklist text, **Then** it contains no em-dash, no emoji and no tell from the
   lint table.
3. **Given** the docs, **Then** `concepts.md` names the humanizer skill, its MIT license and
   version 3.1.0.

### User Story 4 - The lint counts AI tells without blocking (Priority: P2)

The outward lint and the decision lint report structural writing tells as a non-blocking `style`
finding and count them per text in the metrics; only the em-dash and emoji refusal blocks.

**Why this priority**: it measures whether the humanizer rule is followed without adding a new
refusal.

**Independent Test**: create a draft and a decision record with two tells; read the draft row,
the lint message and `metrics.collect`.

**Acceptance Scenarios**:

1. **Given** a draft whose text contains two of the listed tells, **When** it is stored as a
   draft, **Then** the draft row records `style` with those two tell names and
   `metrics.collect(root)['ai_tells'][<draft id>]` is 2.
2. **Given** a decision record with two tells, **When** `wuwei decision lint` runs, **Then** it
   exits 0 and prints `OK: ...` followed by a `style:` line naming the two tells, and
   `ai_tells['D-n']` is 2.
3. **Given** a text with an em-dash, **Then** `outward.lint` still returns exit 1 and
   `drafts.approve` still refuses it.
4. **Given** text with no tell, **Then** `outward.tells` returns `[]` and the decision lint
   output is unchanged (`OK: A (80)`).

### User Story 5 - The CLI's own owner-facing lines are plain (Priority: P3)

The fixed lines the CLI prints or sends to the owner (DM vocabulary and replies, decision
presentation, nudge tails, report headings, status messages) contain no em-dash and no listed
tell, and a test keeps it that way.

**Independent Test**: one test over the string constants of the owner-facing modules.

**Acceptance Scenarios**:

1. **Given** the modules listed in plan.md, **Then** no string constant in them contains an
   em-dash or matches `outward.tells`.
2. **Given** the change, **Then** the guard, mutation and hook-level tests pass and the status
   line latency test stays within budget.

### Edge Cases

- A record with only one option passing every must: the reason is `the only option that passes
  every must`.
- A recommendation tied on score with the runner-up: the reason names the tie instead of a
  criterion.
- `control_plane.content = "none"`: every level, `more D-n` included, sends only the option ids,
  as today.
- The full record fails the outward lint in the DM (for example a Context mentioning a draft):
  `more` falls back to one fixed line pointing to the host, like `escalate_new` does today.
- `decision show` for a record that is missing exits 2 with the reason; for a symlinked record
  exits 2; for an invalid record exits 1 with the lint reason.
- Draft rows written before this change have no `style`; they are left out of `ai_tells`, never
  counted as zero.
- A record with more than eight options can exceed 12 lines at `brief`; the brief form does not
  truncate options.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Config MUST accept `[owner.verbosity]` with `default` in `brief|standard|full`
  (default `brief`) and `decisions`, `digest`, `nudges`, `dm`, `report` in
  `""|brief|standard|full` (default `""`, meaning use `default`). One helper resolves the level
  for a surface.
- **FR-002**: `decision.present(identifier, fields, level)` MUST be the only formatter of a
  decision for the owner: `brief` (question, options with scores, recommendation with one
  reason), `standard` (brief plus the one-line fields), `full` (every field).
- **FR-003**: `wuwei decision show D-n [--full]` MUST print `present` at the `decisions` level,
  or `full` with `--full`, followed at `brief` and `standard` by one line naming `--full`.
- **FR-004**: The DM escalation and the reply echo MUST use `present` at the `dm` level; at
  `brief` and `standard` the escalation adds one line naming `more D-n`.
- **FR-005**: The owner DM MUST accept `more D-n` and reply with the full form of a pending
  decision, through the same content policy and outward lint as every DM.
- **FR-006**: The interview MUST ask one `verbosity` question mapped to
  `owner.verbosity.default`.
- **FR-007**: The report, digest and PR nudge MUST follow their surface level as in User Story 2;
  `standard` keeps today's output on each.
- **FR-008**: `charters/_common-authoring.md` MUST carry a "Writing for a person" section naming
  the `humanizer` skill in embedded mode and a ten-line checklist; the generated agents MUST be
  rebuilt; `skills/wuwei-plan/SKILL.md` MUST name the skill and point to the checklist.
- **FR-009**: `outward.TELLS` (a table of named regexes) and `outward.tells(text)` MUST exist;
  `drafts.create` MUST record `style` on the draft row; `decision.lint` MUST append a `style:`
  line on a hit without changing its exit code.
- **FR-010**: `metrics.collect` MUST report `ai_tells` as `{text id: count}` over today's drafts
  that carry `style` and today's `D-*.md` records; it appears in the report's process metrics
  (standard and full) and the retro's metrics.
- **FR-011**: The em-dash and emoji refusal MUST stay the only blocking writing rule.
- **FR-012**: A test MUST pin that the CLI's owner-facing string constants contain no em-dash
  and no tell.
- **FR-013**: Docs MUST cover the keys (configuration.md), `decision show --full` (daily.md,
  reference.md), `more D-n` (remote.md) and one paragraph on voice and the humanizer attribution
  (concepts.md).

### Key Entities

- **Verbosity level**: `brief`, `standard` or `full`, per owner-facing surface.
- **Tell**: a named regex from the humanizer skill's structural sections; a hit is a `style`
  finding, never a refusal.

## Success Criteria *(mandatory)*

- **SC-001**: A pending decision reads in under 12 lines at the default setting, on the host and
  in the DM.
- **SC-002**: The owner gets the full record with one command or one DM reply.
- **SC-003**: Every generated agent and the planner skill name the humanizer skill.
- **SC-004**: `ai_tells` is reported per text in the report and the retro.
- **SC-005**: The full suite passes, with no new blocking rule.

## Assumptions

- TOML cannot hold both `owner.verbosity = "brief"` and `owner.verbosity.decisions`, so the
  issue's keys are read as the table `[owner.verbosity]` with `default` plus one key per surface;
  an empty surface value means "use default".
- Default `brief` changes today's DM decision text and today's report for everyone; tests that
  pin today's report run at `standard`. The DM at `standard` is the brief text plus the one-line
  fields, a superset of today's DM (question and options), since one formatter serves every
  surface. `standard` keeps today's output on the report, digest and nudge.
- The "one reason" is derived from the record, with no new field: the Wants criterion that
  contributes most to the recommendation's lead over the best other passing option. Adding a
  record field would change the decision lint and every record writer.
- `full` for a decision is every field of `decision.FIELDS` in order, rebuilt from the evaluated
  fields; free text outside the fields (Notes, Consequences) stays in the file only.
- The digest already lists one line per decision and the PR nudge is already one line, so
  `brief` keeps them as they are; "one line per PR" adds nothing to a digest that lists no PRs.
  "Probe lines" for nudges are the changed probe field names in the `pr.changed` payload.
- The retro has no surface key in the issue, so its output is unchanged apart from the
  `ai_tells` metric inside its metrics JSON.
- "Each role charter carries the checklist": the checklist is written once in
  `charters/_common-authoring.md`, which `wuwei agents build` embeds in every generated role
  agent; role charters are not duplicated. The planner skill names the skill and points to the
  checklist instead of copying it. #302 edits the brief prompt and the planner skill in the same
  period; this feature touches only the writing section and one paragraph of the skill.
- The checklist describes each tell in plain words and does not quote the stock words, so the
  charter itself passes the tell lint; the word lists live in `outward.TELLS`.
- The tell table counts each kind once per text; forced triads and writing for the wrong reader
  are in the checklist only, since a regex cannot tell them apart from normal prose.
- The style finding on a decision record is the `style:` line of the lint output plus the metric;
  the hook command surfaces only refusals (`cli/wuwei/commands/hook.py` `refuse`), so a seat sees
  the `style:` line when it runs `wuwei decision lint`, and the owner sees the count in the
  metrics. Surfacing exit-0 hook output is out of scope.
- The issue names no dry-run workspace for this feature; the failure was reproduced with
  `bin/wuwei` and the template record on `main`.
- `more D-n` is read-only, needs no second factor, and only answers decisions pending for the
  owner (the ones `escalate_new` sends).
