# Feature Specification: a quoted mention of an owner command is data, rank and propose take the lead's goals in either shape, and the gate-citation lint on AskUserQuestion warns outside strict

**Feature Branch**: `471-gate-shapes`

**Created**: 2026-10-04

**Status**: Draft

**Input**: GitHub issue #471, "fix(guards): a quoted mention of an owner command is data, rank
and propose take the lead's goals in either shape without sending the owner to a terminal,
and the gate-citation lint on AskUserQuestion warns outside strict". Owner report
2026-10-04, confirmed by probes on the 0.15.0 asset in a guarded workspace.

## Root cause (read and reproduced on main, 963a839)

Reproduced read-only with the worktree's code against the v0.15.0 smoke workspace (template
`goals.md`, default `guarded` posture, no `days/2026-10-04/plan.md`), calling
`protect_state.check_bash`, `decision.check_question` and `wuwei rank` in process:

| Probe | Result on main |
| --- | --- |
| `jq '.sweep.ranking = "wuwei rank exit 2: ... bin/wuwei goals edit ..."' lead.json > <scratch>/lead.ranked.json` | `(2, 'Opaque owner action: ...')` |
| `echo 'run bin/wuwei goals edit later' > <scratch>/note.txt` | `(2, 'Opaque owner action: ...')` |
| `echo 'run bin/wuwei goals edit later'` (no redirect) | `(0, '')` |
| `cat <<'EOF' > x.txt` with body `bin/wuwei goals edit` | `(2, 'Opaque owner action: ...')` |
| `bin/wuwei goals edit`, `sh -c 'bin/wuwei goals edit'`, `xargs bin/wuwei goals edit` | `(1, owner reason)` each |
| goals gate question, header `Goals`, text `Morning gate (days/2026-10-04/plan.md): ...` | `(1, 'Cite a decision D-n ... or mark Morning gate and cite today's plan file.')`; `guards.level` gives `('decision', 'records', 'block', 'posture: records = block (floor; no setting lowers it)')` |
| `wuwei rank lead.json`, `"goals": ["G-1"]` | exit 2, `wuwei rank: goals line 1: no goals; the owner fixes memory/goals.md with bin/wuwei goals edit in a host terminal` |
| `wuwei rank lead.json`, goals as blocks | exit 0 |

1. **Owner-action guard reads data as commands.** In
   `cli/wuwei/guards/protect_state.py` `_owner_action`:
   - line 174 builds `readers` from `_READERS` only (`grep rg echo printf head tail wc cut
     tr`), so `jq`, `cat`, `sed -n Np`, `ls` and the other read-only words the shared
     classifier knows (`wuwei.shell.reads`) are treated as possible executors;
   - lines 194-212: for such a program every argv word is scanned with `_CLI_WORD`
     (line 210), so the jq filter string `... "wuwei rank ..."` returns `Opaque owner
     action` at line 211;
   - lines 183-188: a reader's mentions count as seen only when it has no redirect, so
     `echo '...' > note.txt` and a heredoc body fed to `cat > x.txt` leave `unseen > 0`
     and lines 235-238 refuse.
2. **`rank` and `plan propose` drop ids-only lead goals into the old reason.**
   `cli/wuwei/goals.py` `proposed` (lines 71-73) returns the template text unchanged when
   the lead's `goals` are strings, so `goals.parse` raises `goals line 1: no goals; the
   owner fixes memory/goals.md with bin/wuwei goals edit in a host terminal` (line 59).
   Both callers route through it: `cli/wuwei/commands/rank.py:40-42` and
   `cli/wuwei/plan.py:99-102`. The same host-terminal sentence ends every other `parse`
   reason (lines 29, 32, 37, 40, 47, 52, 57), against #357's rule that no step asks the
   owner to edit a record; the #357 lint (`tests/test_owner_records_lint.py`) has no
   pattern for it.
3. **The question lint inherits the records floor.** `cli/wuwei/guards/__init__.py:39-43`
   maps the whole `decision` module to `records`, which is a floor
   (`cli/wuwei/workspace.py:45`), so `level()` (lines 67-68) blocks
   `decision.check_question` in every posture. A question writes nothing. Its reason
   (`decision.py:162-163`, appended at line 191) does not say that the gate question was
   recognised and that only `days/<date>/plan.md` is missing (`gate_question`,
   `decision.py:119-130`, needs the file to exist).

## User Scenarios & Testing

### User Story 1 - A mention of an owner command in data is data (Priority: P1)

A planner or seat writes text that mentions `bin/wuwei goals edit` (a jq update of the
lead JSON, a note, a heredoc into a file). When every command in the call only reads or
prints text (`_READERS` or `wuwei.shell.reads`), nothing in the call can run an owner
command, so the guard passes it. A call that runs anything else keeps today's rules.

**Why this priority**: it stopped the owner's planner mid-plan with a records-floor refusal.

**Independent Test**: `python -m pytest -q tests/test_owner_actions.py -k "data or regression"`.

**Acceptance Scenarios**:

1. **Given** a guarded workspace, **When** a call runs
   `jq '.sweep.ranking = "wuwei rank exit 2: ... bin/wuwei goals edit ..."' lead.json > <scratch>/lead.ranked.json`
   or `echo 'run bin/wuwei goals edit later' > <scratch>/note.txt`, **Then**
   `check_bash` returns `(0, '')` and the PreToolUse hook exits 0 and appends no
   `hook.refusal` or `guard.would_refuse` event.
2. **Given** the same workspace, **When** a seat (payload with `agent_id`) runs
   `bin/wuwei goals edit`, `sh -c 'bin/wuwei goals edit'` or `xargs bin/wuwei goals edit`,
   **Then** each is refused as today (exit 1, the owner reason).
3. **Given** a reader whose text reaches an executor in the same call
   (`echo 'exec bin/wuwei goals edit' > x.tcl; tclsh x.tcl`, `cat <<'EOF' | tclsh`,
   `awk 'BEGIN { system("bin/wuwei ...") }'`, every row of `EXECUTOR_PROBES`), **Then** it
   is refused as today.

---

### User Story 2 - `rank` and `plan propose` take the lead's goals in either shape (Priority: P1)

While `memory/goals.md` has no `## G-n` heading, goal blocks in the lead JSON run as
provisional goals (#357, unchanged). Ids alone get a seat-facing reason that says what to
do; no reason sends the owner to a host terminal to edit `goals.md`.

**Why this priority**: the planner could not propose and fell back to asking the owner.

**Independent Test**: `python -m pytest -q tests/test_goals_rank.py tests/test_plan.py -k "ids_only or no_goals or provisional"`
and `python -m pytest -q tests/test_owner_records_lint.py`.

**Acceptance Scenarios**:

1. **Given** an empty-template `goals.md` and a lead JSON whose `goals` are blocks,
   **When** `wuwei rank lead.json` or `wuwei plan propose lead.json` runs, **Then** each
   exits 0 on provisional goals (the #357 tests stay green).
2. **Given** the same `goals.md` and `"goals": ["G-1"]`, **When** `wuwei rank lead.json`
   runs, **Then** it exits 2 and stderr is
   `wuwei rank: the lead JSON names G-1 without its block; have the lead write goals as blocks (outcome, measure, target, date, priority), or run /wuwei:wuwei-plan again`,
   with no `host terminal`. `plan propose` raises the same reason (`wuwei plan: ...`).
3. **Given** the template `goals.md` and no lead goals, **When** `goals.parse` runs,
   **Then** the `no goals` reason ends with the same `have the lead ... or run
   /wuwei:wuwei-plan again` step and no `host terminal`.
4. **Given** the #357 records lint, **When** it runs over the repository, **Then** it
   passes, and it reports a planted `the owner fixes memory/goals.md ...` sentence.

---

### User Story 3 - The gate-citation lint on AskUserQuestion warns outside strict (Priority: P2)

A question writes nothing, so the citation lint takes the `outward` posture area (warn
under `observe` and `guarded`, block under `strict`, overridable by
`security.areas.outward`). A question marked `Morning gate` that cannot cite today's plan
gets a one-line reason naming what is missing.

**Why this priority**: it turned a planner that could not propose into a blocked gate.

**Independent Test**: `python -m pytest -q tests/test_decision.py tests/test_posture.py -k "question or areas"`.

**Acceptance Scenarios**:

1. **Given** a guarded workspace without `days/<date>/plan.md`, **When** the planner asks
   the goals gate question (`Morning gate (days/<date>/plan.md): ...`, header `Goals`),
   **Then** the PreToolUse hook exits 0 and appends exactly one `guard.would_refuse`
   event with `guard` `decision`, `area` `outward` and a `reason` of
   `Morning gate questions cite days/<date>/plan.md; run bin/wuwei plan propose <lead.json> first`.
2. **Given** the same under `strict`, **Then** the hook exits 2, denies, and the reason
   carries that line.
3. **Given** a question with no `D-n`, `C-n` or `Morning gate` mark, **Then** the reason is
   today's citation hint (warned outside strict, refused under strict).
4. **Given** `goals edit --file` from the planner, **Then** the #357 allowance still needs
   an answered gate question that passes `gate_question` (unchanged), and decision record
   writes (`decision.check_write`) stay on the records floor.

### Edge Cases

- `jq ... > a && mv a lead.json`: `mv` is not a reader, so the call keeps today's rule
  (refused while the text names an owner command). The planner writes the result to a new
  file or uses the Write tool. See Assumptions.
- A reader piped into a reader (`jq ... | grep x > f`) is still all readers: passes.
- A reader piped into anything else (`echo ... | at now`, `| ssh`, `| xargs sh -c {}`):
  refused as today through `feeds` and `unseen`.
- `find` with `-exec` and `sed` without `-n Np` are not `reads()`; unchanged.
- An unquoted heredoc delimiter or other parse failure goes through the `ParseError`
  branch of `check_bash`, unchanged.
- A goals list mixing blocks and ids while `goals.md` has no goals: the ids-only reason
  names the string entries.
- `goals.md` with confirmed goals and an ids-only lead JSON: unchanged (ids cite confirmed
  goals; #357 scenario 4 still refuses blocks then).
- A multi-question AskUserQuestion: the guard returns one result per call, so one
  `guard.would_refuse` per call.

## Requirements

### Functional Requirements

- **FR-001**: `_owner_action` MUST treat a command as a reader when its program is in
  `_READERS` or `wuwei.shell.reads(argv, cwd)` is true, and MUST NOT scan a reader's argv
  for the CLI word.
- **FR-002**: When every command in the call is a reader, `_owner_action` MUST NOT refuse
  on CLI mentions no argv shows (heredoc bodies, comments, a reader's redirected text).
- **FR-003**: Every refusal of a CLI command at command position (direct, wrapped,
  `sh -c`, `xargs`, `eval`, renamed launcher, script file, interpreter snippet, executor
  fed by a reader) MUST stay as today.
- **FR-004**: `goals.proposed` MUST raise `ValueError('the lead JSON names <ids> without
  its block; have the lead write goals as blocks (outcome, measure, target, date,
  priority), or run /wuwei:wuwei-plan again')` when `memory/goals.md` has no goal heading
  and the lead's `goals` list holds any string.
- **FR-005**: Every `goals.parse` reason MUST end with `have the lead write goals as blocks
  (outcome, measure, target, date, priority), or run /wuwei:wuwei-plan again` in place of
  the host-terminal sentence.
- **FR-006**: The #357 lint MUST report `the owner fixes memory/...` sentences.
- **FR-007**: `decision.check_question` MUST run in the `outward` posture area; every other
  `decision` check stays `records`.
- **FR-008**: For a question marked `Morning gate` that fails `gate_question` and cites no
  `D-n`/`C-n`, `check_question` MUST return exit 1 with
  `Morning gate questions cite days/<date>/plan.md`, followed by
  `; run bin/wuwei plan propose <lead.json> first` when that file does not exist.
- **FR-009**: `charters/lead.md` (and the regenerated `agents/lead.md`),
  `skills/wuwei-plan/SKILL.md`, the design spec 9 posture table and
  `docs/site/security.md` MUST say what changed (goals as blocks while proposing; the
  question lint in `outward`).

### Key Entities

- **Reader** (guard-internal): a command whose program is in `_READERS` or for which the
  shared `wuwei.shell.reads` is true. No new state, event kind or file.

## Success Criteria

- **SC-001**: The probe table above, rerun on the change, shows `(0, '')` for the two
  quoted shapes and the heredoc into a file, and today's result for every other row.
- **SC-002**: `wuwei rank` on an ids-only lead JSON exits 2 with the new reason; no string
  under `cli/wuwei/goals.py` contains `host terminal`.
- **SC-003**: Under `guarded` the goals gate question before `plan propose` goes through
  with one `guard.would_refuse`; under `strict` it is denied.
- **SC-004**: The full suite passes. Existing expectations that change are the ones this
  issue asks to change: `test_owner_actions.py::test_regression_list` row
  `echo 'bin/wuwei decision outcome' > notes.md` (2 to 0) and any hook-level test that
  expects an uncited question to be denied under the default posture (it moves to
  `strict`).

## Assumptions

- "Command positions from the shared classifier" is implemented with the classifier's own
  per-command read-only test, `wuwei.shell.reads` (shared by `classify` and this guard,
  #349), plus the guard's `_READERS`. A call of readers only cannot run anything, so its
  mentions are data. `shell.py` is not changed (#469 and #470 change it in parallel).
- The rule is per call, not per word: a mention inside a quoted argument of a non-reader
  (`awk`, `deno eval`, `env -S`, `git -c alias...`) stays refused, because those programs
  run their arguments (`test_regression_list`, `EXECUTOR_PROBES`). This keeps every #222
  bypass row green; it was checked in a scratch copy (owner-action, protect_state,
  launcher-relevance and owner-edits suites passed with only the one row flipped).
- `mv` and `cp` are not readers. The owner's original shape `jq ... > a && mv a lead.json`
  stays refused; the acceptance names the shape without `mv`. Making movers inert is a
  follow-up if the planner keeps hitting it.
- The ids-only reason is produced once in `goals.proposed`; each CLI adds its own prefix,
  so `rank` prints `wuwei rank: the lead JSON names G-1 ...` and `plan propose` prints
  `wuwei plan: ...`. The issue's `rank:` prefix is read as that.
- "Goals are always written as blocks" means whenever the lead proposes goals
  (`memory/goals.md` has none). With confirmed goals the lead cites ids, because
  `plan._proposal` refuses objects then (#357 scenario 4).
- The question lint moves to the existing `outward` area (warn, warn, block), the area for
  text addressed to people; no new posture area. The owner can still block it under
  `guarded` with `security.areas.outward = "block"`. Malformed question payloads (exit 2)
  follow the same level.
- "One `guard.would_refuse` per question" is one per AskUserQuestion call: the hook records
  one event per refused guard result, and the planner asks the gate as one question.
- `<date>` in the new reason is today's day directory name; `<lead.json>` stays a literal
  placeholder.
- The posture table in design spec 9 and `docs/site/security.md` gets the one-cell change
  the owner's issue implies (the `outward` row names the question citation check). This
  follows #357, which updated the design spec for an owner-filed issue.
- `promotion.py`, `merge.py`, `shepherd.py` and `commands/goals.py` host-terminal texts are
  owner actions on config or history, not record edits; out of scope.
- Steps run here: specify, plan, tasks (the task scope). Clarify, analyze and checklist
  are left to the pipeline.
- Neutral fixtures only; no owner goal text.
- Build: the owner's addition (a `grep ... | head` over the plugin's own source with
  `'set'` in the pattern and `wuwei/commands/state` in paths) is a fourth row of
  `test_owner_mentions_in_data_pass`; the reader rule covers it. The site page says "the
  question citation check" because its pages never say "the owner" (#362).

## Deferred

- None found.
