# Feature Specification: protect_state blocks writes to records and config, never reads of them

**Feature Branch**: `349-protect-state-reads`

**Created**: 2026-10-03

**Status**: Draft

**Input**: GitHub issue #349, "fix(guards): protect_state blocks writes to records and config,
never reads of them". Second first-day trial, 2026-10-03 (development build of 0.12.0): the
planner's reads of `config.toml`, the registry reports under `.wuwei/ziran/` and a decision
record were refused by the state guard. Same chain as #347 (shared shell classifier) and
#348 (the plugin CLI as a known command).

## Root cause (reproduced on main at #397, read-only, in a fixture workspace)

The trial build predates #347 and #391 (its refusal text is the pre-#391 hint). On current
`main` the literal trial shapes `grep -n posture .wuwei/config.toml`,
`cat .wuwei/days/<date>/decisions/D-1.md` and `python3 read_reports.py` already pass with no
event. Reads of protected records are still refused, in every posture (the `records` area is
a floor), through four spots in `cli/wuwei/guards/protect_state.py` and one in
`cli/wuwei/shell.py`:

1. `_write_targets`, lines 358-362 and 368-392: the only programs whose operands are data are
   the guard's private list (`_READERS`, line 87, plus `cat`, `less`, `jq`). Every other
   program, including the shared classifier's own read-only words (`shell.READ_ONLY`, line
   600: `ls`, `diff`, `find` without an action), has each protected operand counted as a write
   target. Refused with exit 1: `ls .wuwei/ziran`, `find .wuwei/ziran -name report.json`,
   `diff .wuwei/charters/a.md .wuwei/charters/b.md`, and from cwd `.wuwei`: `ls ziran`,
   `find ziran -name report.json`.
2. `check_bash`, lines 479-482: any interpreter whose argv mentions `.wuwei` or a state file
   name is refused with exit 2, "Opaque interpreter", even when it runs a file:
   `python3 read_reports.py .wuwei/ziran/a/report.json` and
   `python3 -m json.tool .wuwei/ziran/a/report.json`.
3. `check_bash`, lines 454-460 (a call `normalize` cannot read): in a protected cwd the guard's
   own regexes `_DYNAMIC` and `_WRITE_CONSTRUCT` (lines 19-22) refuse a read loop because
   `2>/dev/null` contains `>`: from cwd `.wuwei`,
   `for f in ziran/*/report.json; do cat $f 2>/dev/null; done` is exit 2, although the shared
   classifier marks it read-only.
4. `check_file` line 296 and `check_bash` lines 496 and 501: every refused write returns the
   same two-sentence `_STATE_HINT` (line 13); it never names the command that performs the
   change.
5. `shell._classify`, line 851: `argv[0]` is read for a simple command that has only a
   redirect, so `for f in a; do cat $f; done > out.txt` raises `IndexError`, which no guard
   catches; the hook fails closed with exit 2 under the records floor.

Facts the issue states differently:

- `.wuwei/credentials/**`: no PreToolUse guard refuses a read today. The default decoy
  `credentials/backup.env` is the honeytoken: a read of it is let through and then paged as a
  `security.honeytoken` finding by the traces guard (`tests/test_canary.py`), and its egress
  blocks at the outward floor. Writes to it are refused by `protect_state`.
- `decisions/*.md` is not in the `protect_state` set: seats write decision records with Write
  and the PostToolUse decision lint checks them (design spec 5.8).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A seat reads records and config (Priority: P1)

The planner and the other seats read `config.toml`, the day's state, decisions, charters,
memory and the registry reports to learn what to do. Reading must never be refused and must
leave no event, in every posture.

**Why this priority**: a refused read stops the planner before its first decision; the trial
lost eleven calls to it.

**Independent Test**: pipe each read shape through the PreToolUse hook in a fixture
workspace under `observe`, `guarded` and `strict`; assert exit 0 and no `hook.refusal` or
`guard.would_refuse` event.

**Acceptance Scenarios**:

1. **Given** a workspace in any posture, **When** a seat runs
   `grep posture .wuwei/config.toml`, `cat .wuwei/days/<date>/decisions/D-1.md` or
   `python3 read_reports.py` (a file that opens the reports read-only), **Then** exit 0 and
   no event.
2. **Given** the same, **When** a seat runs `head`, `tail`, `sed -n 1,5p`, `less`, `wc`,
   `jq`, `ls`, `find` (without an action) or `diff` on protected paths, or
   `python3 read_reports.py .wuwei/ziran/a/report.json`, or
   `python3 -m json.tool <report>`, **Then** exit 0 and no event.
3. **Given** cwd `.wuwei`, **When** a seat runs `ls ziran`, `find ziran -name report.json` or
   `for f in ziran/*/report.json; do cat $f 2>/dev/null; done`, **Then** exit 0 and no event.
4. **Given** Read, Grep or Glob on a protected path, **Then** exit 0 and no event, as before.

---

### User Story 2 - A write to a protected path is refused with the command to use (Priority: P1)

A write to a protected record keeps the refusal it has today (records floor, every posture),
and the reason is one line that names the CLI command performing that change when one exists.

**Why this priority**: the refusal is the guard's purpose; naming the command saves the seat
a retry loop.

**Independent Test**: call `check_file` and `check_bash` with writes to each protected kind;
assert exit 1, a reason without a newline, and the named command.

**Acceptance Scenarios**:

1. **Given** `sed -i`, `tee`, `>`, `>>`, `cp` into, or Edit, Write, MultiEdit or NotebookEdit
   on any protected path, **Then** refused as today (exit 1 from the guard, hook exit 2 with a
   `hook.refusal` event in every posture).
2. **Given** a refused write to `config.toml`, **Then** the reason names
   `wuwei config set` (owner, host terminal).
3. **Given** a refused write to a day `state.json` or `state.snapshot.json`, **Then** the
   reason names `wuwei state set` and `wuwei state transition`; to `events.jsonl`,
   `wuwei event`; to `.wuwei/ziran/**`, `wuwei mcp check` and `wuwei mcp decide`; to
   `memory/goals.md` or `memory/voice.md`, `wuwei goals edit --file` and
   `wuwei voice edit --file`; to `.wuwei/integrity/**`, `wuwei integrity reconfirm`.
4. **Given** a refused write to any other protected path, **Then** a one-line generic reason
   that still says to use the wuwei CLI and that owner edits run outside agent tools.
5. **Given** inline interpreter code that names state
   (`python3 -c 'open(".wuwei/days/<date>/state.json", "w")'`) or an interpreter whose
   output is redirected into a protected path, **Then** refused as today.

---

### User Story 3 - Credentials stay as they are (Priority: P2)

**Acceptance Scenarios**:

1. **Given** `cat .wuwei/credentials/<name>` on the decoy, **Then** handled as today: the
   PreToolUse guards let it through and the traces guard pages it as a honeytoken finding
   (`tests/test_canary.py` stays green unchanged).
2. **Given** a write to the decoy (`echo x > .wuwei/credentials/backup.env`, Edit), **Then**
   refused as today.

### Edge Cases

- `find` with an action (`-delete`, `-exec`), `sed -i`, `rg --pre`, `awk`, `sort` and any
  unknown program with a protected operand keep today's refusal: only the shared read set
  passes.
- `for f in *; do echo x > $f; done` from a protected day directory keeps its exit 2.
- A read loop whose output goes to an unprotected file
  (`for f in a; do cat $f; done > out.txt`) is decided by the #347 table (warn), never by an
  uncaught exception.
- A symlink or hard link alias of a protected file refused by Write gets the generic reason
  when the resolved path is not under `.wuwei`.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `protect_state` MUST treat a command the shared classifier calls read-only
  (`shell.READ_ONLY`, `sed -n <lines>p`, `find` without an action, a read-only call of the
  known CLI) as writing none of its operands; redirects stay checked.
- **FR-002**: `less` MUST be in `shell.READ_ONLY`.
- **FR-003**: An interpreter that runs a file or module (no inline code) MUST have its
  operands treated as data; the "Opaque interpreter" refusal MUST apply only to inline code
  (`-c`, `-e`, `--eval`) whose argv names state.
- **FR-004**: In the unparsed path, a shape the shared classifier marks read-only MUST NOT hit
  any of the records refusal clauses; the `cd` rule and everything else stay as they are.
- **FR-005**: A refused write MUST return one line naming the CLI command for that record
  kind (table in User Story 2), or the generic one-line reason.
- **FR-006**: `shell.classify` MUST NOT raise on a simple command that is only a redirect.
- **FR-007**: The protected set, the owner-action table, the Read/Grep/Glob behaviour, the
  credentials behaviour and every refusal of a write MUST stay as they are.

### Key Entities

- **Shared read predicate** (`shell.reads(argv, cwd)`): one command only reads. Extracted
  from `shell._classify`, which keeps using it.
- **Inline code predicate** (`shell.inline_code(argv)`): an interpreter given code inline.
  Extracted from `shell._classify`.

## Success Criteria *(mandatory)*

- **SC-001**: every read shape in User Story 1 exits 0 with no event under `observe`,
  `guarded` and `strict`.
- **SC-002**: every write shape in User Story 2 is refused in every posture, and its reason is
  one line naming the command where the table has one.
- **SC-003**: the full suite passes with no existing test expectation changed.

## Assumptions

- "Protected set stays" means the set `_protected_name` implements today stays unchanged.
  `decisions/*.md` is not added (seats write decision records; the decision lint guards
  them) and `.wuwei/credentials/**` is protected for writes only.
- "Credentials: reads refused too, as today" is read as "do not loosen credentials". Today no
  PreToolUse guard refuses that read; it is the honeytoken tripwire, which needs the read to
  happen so the PostToolUse finding pages. Adding a read refusal would change the canary
  design (#105) and is out of scope.
- `python3 <file>` passes with protected operands: the file's code is unseen either way (a
  path written inside the file already passes today), so refusing only the operand form
  blocks reads without stopping writes. The hooks are cooperative mistake prevention (spec
  9.1).
- The read set is the shared classifier's (plus `less`, which the issue names). `stat`,
  `awk`, `sort` and other programs stay unknown and keep today's refusal on protected
  operands; widening the set is a separate change.
- `_READERS` stays in `protect_state`: `_owner_action` uses it for owner-action relevance,
  and its text-only programs (`echo`, `printf`, `cut`, `tr`, `rg` without `--pre`) keep
  passing. `_WRITE_CONSTRUCT` and `_DYNAMIC` stay for non-read shapes in a protected cwd:
  the classifier has no write-word output, and dropping them would either loosen the records
  floor or refuse non-writes.
- The trial's literal shapes already pass on `main`; the tests pin them so they stay passing.
- `wuwei event` is the seat-facing CLI for events; owner commands are marked as host
  terminal in the reason.
