# Feature Specification: the session knows the whole plugin at start

**Feature Branch**: `476-session-knows`

**Created**: 2026-10-04

**Status**: Draft

**Input**: GitHub issue #476, "feat(session): the session knows the whole plugin at start from
one generated injection, starts the day without the plan command, and a conformance test
proves a fresh session reaches dispatch without a refusal". Owner, 2026-10-04: the session
has to learn the plugin as it goes; with the plan command it should know everything, and
without it the day should still start. Amended the same day: keep the per-session cost low;
write the static part once, versioned, into the harness's own memory file.

## Root cause (read and reproduced on main, 963a839, read-only)

Reproduction: `next_command.orientation` was called in process for a `plan` row under
`guarded`, and the command, owner-action and posture tables were compared with
`docs/site/agent.md`. The notes name no dry-run workspace; the evidence is the owner's first
real items on 0.15.0 (refusals and `--help` calls) plus this comparison.

1. The SessionStart text tells the session where to look, not what to do. The orientation
   (`cli/wuwei/commands/next.py:126-156`) is 8 lines: the entry line
   (`next.py:136-138`) says "Start or resume the day with /wuwei:wuwei-plan (steps:
   .../skills/wuwei-plan/SKILL.md)" and the last line (`next.py:153-154`) points at
   `docs/site/agent.md`. Without the plan skill invoked the session has no steps, and with
   it the session still has no command list, so it calls `--help` to discover commands.
2. The only reference is hand-written and has drifted. `docs/site/agent.md` names 6 owner
   actions ("How the owner answers"); the guard table `_OWNER_ACTIONS`
   (`cli/wuwei/guards/protect_state.py:46-99`) has 19, so 11 (`drafts drop`,
   `integrity reconfirm`, `state recover`, `watch uninstall`, `listen uninstall`,
   `goals edit`, `voice edit`, `remote ack`, `config promote`, `memory forget`,
   `telemetry send`) refuse with no warning in the guide. 10 of the 21 Daily commands in
   `cli/wuwei/__main__.py:26-36` (`status`, `nudges`, `decision`, `reply`, `discover`,
   `note`, `tracker`, `metrics`, `steward`, `docs`) are not named in agent.md. The posture
   areas (`cli/wuwei/workspace.py:36-45`) appear only as prose in one orientation line.
3. The accepted command forms exist only in refusal text (`cli/wuwei/shell.py:596-601`,
   `WORKSPACE_ROOT` and `UNPARSED`) and in one orientation clause, so a session learns them
   by being refused first.
4. The harness keeps nothing between sessions except files it loads itself. The managed
   block writer inside `memory.export` (`cli/wuwei/memory.py:138-185`) already writes one
   marked block into `[memory] export_to` (CLAUDE.md by default), but only the rules block,
   and only from `memory export`, `promote` and `consolidate`; `init` never writes it.
5. A waiting decision's next step is `wuwei decision show D-n` (`next.py:67`) without
   `--widget`, so the session prints prose instead of the card the skills ask for.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A static reference, written once and versioned (Priority: P1)

`init` and `init --upgrade` write a generated plugin reference into the file `[memory]
export_to` names, in its own marked block with the plugin version and a content hash. The
same text prints on demand with `wuwei guide`. It is generated from the CLI's tables, so it
cannot drift.

**Why this priority**: it removes the `--help` calls and the form refusals for every session,
at the cost of one short block the harness already loads.

**Independent Test**: init a workspace in `tmp_path`; read the export file; compare the
block with `wuwei guide`; run `init --upgrade` again and compare bytes.

**Acceptance Scenarios**:

1. **Given** `init` in a workspace, **When** it finishes, **Then** the export file holds one
   `<!-- wuwei:guide:start -->` to `<!-- wuwei:guide:end -->` block whose stamp names the
   plugin version and a content hash, the block is under 100 lines, and its body equals the
   output of `wuwei guide`.
2. **Given** that workspace, **When** `init --upgrade` runs again on the same plugin version,
   **Then** the export file is byte-identical and the upgrade reports no guide change.
3. **Given** an export file with the owner's own text and the `wuwei:memory` rules block,
   **When** the guide block is written or rewritten, **Then** both the owner's text and the
   rules block are unchanged, and a later rules export leaves the guide block unchanged.
4. **Given** the reference, **Then** it lists every Daily and Recovery command with its
   one-line help, the owner-only commands with "ask the owner", the read-only commands, the
   accepted command forms, the records rule, the ask rule with every widget printer, the
   guard areas by posture as one table, and where each record lives.

---

### User Story 2 - The day starts without the plan command (Priority: P1)

SessionStart in a workspace with no plan today injects, after the orientation, the plan
flow's steps generated from the plan skill, ending with "Do this now.", and one line
pointing at `wuwei guide`. A closable day gets the report flow's steps instead. A stuck seat
or a waiting decision gets only its one command.

**Why this priority**: it is the owner's request: open Claude Code, say what you want.

**Independent Test**: pipe a recorded SessionStart payload through `wuwei hook SessionStart`
in a calibrated workspace without a plan; read `additionalContext`.

**Acceptance Scenarios**:

1. **Given** SessionStart in a workspace with no plan today, **Then** the injected
   orientation holds the orientation lines, a register line naming `wuwei plan session
   <this session id>`, one line per numbered step of `skills/wuwei-plan/SKILL.md`, "Do this
   now." and the `wuwei guide` pointer, and the orientation block is under 30 lines.
2. **Given** that injection, **When** a scripted session runs every `wuwei` command the
   injected lines name, in the recorded-executable form, through the PreToolUse hook under
   observe, guarded and strict, **Then** no call is refused, no `hook.refusal` event is
   written, and no call carries `--help` or `-h`.
3. **Given** a planned day whose next step is a stuck seat (the row names `wuwei seat stop`,
   #473), **Then** the injection names that command and holds no plan steps, no plan skill
   pointer and no register line.
4. **Given** a decision waiting for the owner, **Then** the next step and the injection name
   `wuwei decision show D-n --widget`.
5. **Given** a closable day (`wuwei next` state `close`), **Then** the injection holds one line
   per numbered step of `skills/wuwei-report/SKILL.md` and "Do this now.".
6. **Given** SessionStart outside a workspace, **Then** nothing is injected (#323).

---

### User Story 3 - Drift is detected and fixed by the doctor (Priority: P1)

When the command sets or the posture table change, `wuwei guide` changes, `doctor` reports
the exported block stale, and `doctor --fix` rewrites it.

**Why this priority**: a versioned block is only safe if staleness is visible and fixable.

**Independent Test**: init a workspace, change a generating table in process, run the doctor
row and the `init-upgrade` fix.

**Acceptance Scenarios**:

1. **Given** a written block, **When** `workspace.POSTURES` or `commands.READ_ONLY` changes,
   **Then** `guide.text()` changes, and `init --upgrade --dry-run` prints a "Would upgrade
   <export_to>: guide block" line and writes nothing.
2. **Given** that state, **Then** the doctor's `template` row warns with that line in its
   detail and `apply = init-upgrade`.
3. **Given** that row, **When** `doctor --fix` applies `init-upgrade`, **Then** the block body
   equals the new `guide.text()`.
4. **Given** a missing block (deleted by hand), **Then** the same row warns and the same fix
   writes it.

---

### User Story 4 - A conformance run proves it end to end (Priority: P2)

The opt-in headless runner gains a start mode: the fixture session is given only "Start the
day." plus the fixture owner's answers (no skill invocation, no step list) and must reach
the gate, dispatch and close with zero `hook.refusal` events and zero `--help` calls.

**Why this priority**: the offline tests prove the parts; only a real session proves the
whole, and that run costs money, so it stays opt-in like the existing headless day.

**Independent Test**: offline, the runner's validator on recorded evidence; live,
`python3 scripts/headless_e2e.py --start --local-login`.

**Acceptance Scenarios**:

1. **Given** complete start-mode evidence, **Then** the validator returns no findings.
2. **Given** that evidence plus one `hook.refusal` event, or one `wuwei` call or Bash command
   with `--help` or `-h`, or no `plan.approved`, `seat launched` or `day.close_requested`
   event, **Then** the validator returns one finding naming it.
3. **Given** the start prompt, **Then** it names no skill, no numbered step and no `wuwei`
   subcommand.

---

### User Story 5 - One source in the docs (Priority: P3)

`docs/site/agent.md` prints the reference (its generated block equals `wuwei guide`);
`daily.md` says to open Claude Code in the workspace and say what you want;
`configuration.md` says the guide block shares `memory.export_to`; `reference.md` lists
`wuwei guide`.

**Acceptance Scenarios**:

1. **Given** agent.md, **Then** the text between its guide markers equals `guide.text()`.
2. **Given** daily.md's first section, **Then** it says "open Claude Code in the workspace and
   say what you want; the session knows the rest".

### Edge Cases

- `memory.export_to` invalid (absolute, `..`, under `.wuwei`, a symlink): the guide write
  refuses with the same reason as the rules export; `init --upgrade` exits 2 with it.
- Two guide start markers, or a start without an end: refused with the reason and the fix
  (restore the markers or remove the block, then `bin/wuwei init --upgrade`), never a
  silent overwrite.
- The plan or report skill file unreadable at SessionStart: the injection carries one
  "steps unmeasured: <reason>" line naming the skill path; the hook does not crash.
- The skill's numbered list changes (#474, #475 edit it in parallel): the injection follows
  it with no code change; the test compares against the file, not a copy.
- A seat session (`WUWEI_SEAT_ROLE` set to a known charter) keeps its seat entry line and
  gets no plan or report steps.
- No session id in the payload: the register line shows `<session id>`.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `wuwei.guide.text()` returns the reference, built at call time from
  `__main__.GROUPS` (Daily and Recovery) with each command's argparse help,
  `commands.READ_ONLY`, `protect_state._OWNER_ACTIONS`, `shell.UNPARSED`,
  `shell.WORKSPACE_ROOT`, `protect_state._STATE_HINT`, `next.EXECUTABLE` (the orientation's
  executable rule, made a constant), `workspace.POSTURES`, `workspace.FLOORS`, the widget
  printers and the record locations. Under 100 lines with the stamp and markers. It reads no
  workspace file.
- **FR-002**: `wuwei guide` prints `guide.text()` and exits 0; it is a read-only command
  (`commands.READ_ONLY`) listed in the Daily help group.
- **FR-003**: The managed-block writer of `memory.export` is extracted into one shared
  function used by both the rules block and the guide block; there is no second exporter.
- **FR-004**: The guide block is `<!-- wuwei:guide:start -->`, one stamp line naming the
  plugin version and the first 12 hex characters of the SHA-256 of `guide.text()`, the text,
  `<!-- wuwei:guide:end -->`. The file is written only when its content changes.
- **FR-005**: `init` writes the guide block after the workspace exists; `init --upgrade`
  writes it when it changed and prints "Upgraded <export_to>: guide block"; `--dry-run`
  prints "Would upgrade <export_to>: guide block" and writes nothing. "No workspace changes
  needed" holds only when the guide is also unchanged.
- **FR-006**: The doctor reports a missing or stale guide block through its existing
  `template` row (fed by `init --upgrade --dry-run`) and fixes it with the existing
  `init-upgrade` fix. No new doctor row and no new fix.
- **FR-007**: The SessionStart orientation, for a non-seat session: state `plan` adds a
  register line with the payload's session id, the plan skill's numbered steps (first
  sentence of each) and "Do this now."; state `close` adds the report skill's numbered steps
  and "Do this now."; every other state adds nothing beyond the Next line. The entry line
  "Start or resume the day with /wuwei:wuwei-plan" is removed. The last line points at
  `wuwei guide` and keeps the owner guide path. The orientation block stays under 30 lines.
- **FR-008**: The steps are read from `skills/<name>/SKILL.md` in process at SessionStart:
  one file read, no subprocess, no new module import on the hook path (`wuwei.guide` is never
  imported by a hook).
- **FR-009**: `wuwei next`'s decision row names `wuwei decision show D-n --widget`.
- **FR-010**: `scripts/headless_e2e.py --start` runs the fixture day with the start prompt and
  validates it with the existing validator minus the scripted-only checks (refusal probe,
  explicit skill invocation, scripted Stop block) plus a conformance check: zero
  `hook.refusal` events and zero `--help` or `-h` in any `wuwei` call or Bash command.
- **FR-011**: agent.md holds the reference between the guide markers, equal to
  `guide.text()`; daily.md, configuration.md and reference.md carry the lines in US5.

### Key Entities

- **Guide text**: the generated reference; a pure function of the plugin's tables.
- **Guide block**: the guide text between owned markers, stamped, in the export file.
- **Injected steps**: the first sentence of each numbered line of a skill file, read at
  SessionStart.

## Success Criteria *(mandatory)*

- **SC-001**: A fresh session started with "Start the day." reaches the gate, dispatch and
  close with zero refusals and zero `--help` calls (live start-mode run).
- **SC-002**: The orientation block is under 30 lines; the guide block is under 100 lines.
- **SC-003**: A second `init --upgrade` on the same version leaves the export file
  byte-identical.
- **SC-004**: Changing a generating table makes `doctor` warn and `doctor --fix` restore the
  match, with no hand edit.

## Assumptions

- The relayed owner message for this run ("agents/goals are holding the main session instead
  of running in the background") is issue #477, not this issue. It does not conflict with this
  spec: the injected steps come from the plan skill, so #477's edits to that skill reach the
  injection with no change here.
- "At most 30 lines" and "under 30 lines" apply to the orientation block (header to the
  `wuwei guide` pointer). The active constraints, memory payload, lint findings and health
  lines that follow keep their existing bounds (`memory.budget_tokens` for the payload). The
  orientation stays outside the memory budget, as the constraints already are (#358,
  `lifecycle.py` comment); first-sentence steps keep it near 200 estimated tokens.
- Each injected step is the first sentence of the skill's numbered line, plus the skill path
  for the full text. Injecting whole lines would cost about 1,400 estimated tokens per
  session for the plan skill, which is what the owner asked to avoid.
- The skill's numbered list starts at `mcp check`; `plan session` is registered in a
  paragraph before it. The injection adds one generated register line with the payload's
  session id, so the steps run "from plan session to the gate and dispatch" without
  restructuring the skill (#474 and #475 edit it in parallel).
- The exit contract is the same for every command (constitution II), so the reference states
  it once above the command list instead of repeating it on each line.
- "Every command the session may run" is the Daily and Recovery help groups. Owner-group
  commands that a session also runs appear where they apply: read-only paths
  (`commands.READ_ONLY`) and widget printers. Plumbing is left out (hooks and seats call it).
- The owner-only list is `protect_state._OWNER_ACTIONS`, the table the guard enforces, not the
  "Owner" help group (which includes commands sessions run, such as `mcp check`).
- No CLI table holds the widget printers or the record locations. The guide module holds both
  as tuples. A test pins the widget tuple to every parser that defines `--widget`, so it
  cannot drift; the record table has one home, which agent.md prints.
- The reference is the same text in every workspace (it names `.wuwei/executable`, not the
  recorded absolute path, and all three postures, not the current one), so agent.md can
  carry it and the stamp alone carries the version.
- The stuck-seat row and `wuwei seat stop` come from #473 (in flight). This item keys the
  injection on the row's state and tests the stuck case with a stubbed row; nothing here
  depends on #473 being merged.
- "Nothing else about planning" for a stuck seat means no plan steps, no plan skill pointer
  and no register line; the one general "Day loop" orientation line stays.
- The conformance run stays opt-in (paid, real Claude) like the existing headless day. The
  start prompt carries the fixture owner's answers (approve the supplied proposal, park the
  verification-only item with the supplied decision, close) because a headless run cannot
  ask the owner; it names no skill, step or subcommand. The suite proves the parts offline:
  the validator on recorded evidence and a hook replay of the injected commands.
- daily.md's "first section" is section 1 (install and set up); the new sentence closes it.
- The `--help` count covers `wuwei` calls recorded by the runner's observer and Bash command
  words `--help` or `-h`.

## Deferred

- None found. Other harnesses reading the same file (#415) need no change here: the block is
  plain Markdown.
