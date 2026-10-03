# Feature Specification: readable nudges, grouped help and a short session-start block

**Feature Branch**: `367-nudges-help`

**Created**: 2026-10-03

**Status**: Draft

**Input**: GitHub issue #367, "fix(cli): readable nudges, grouped help and a short session-start block". UX sweep of 2026-10-03, findings F13, F20 and F21. Depends on #358 (merged: `wuwei next` and the SessionStart orientation block).

## Problem and root cause

Owner's brief for the sweep: adoption should be as easy as possible, and the workflow should
coach people with less experience instead of simply blocking.

Reproduced on `main` (read-only, a scratch workspace built the way `tests/test_next.py`
builds one: calibrated config, empty memory files, an approved item whose build record holds
a 4000-character launch prompt, one routed decision, and two `adapter: none` plus two
`mcp.checked` exit-2 events, as setup leaves them on day one).

| Finding | What happens now | Root cause |
|---|---|---|
| F13 | `bin/wuwei nudges` prints one JSON array: `{"source": "adapter: none", "reason": "unmeasured"}` and `{"source": "mcp.checked", "reason": "mcp.checked"}`, each twice, then `D-1 pending owner decision`. No row says what to do. | `cli/wuwei/commands/nudges.py:17` prints `json.dumps(attention(...))` and nothing else. `cli/wuwei/registry.py:127` (`record_none`) appends an `adapter: none` event for every call to an adapter the owner set to `none`, and `cli/wuwei/signal.py` (`SILENT`, line 6) does not list that kind, so `classify` returns `nudge`. `cli/wuwei/commands/status.py:123` keys generic events by `(kind, line number)`, so two identical events are two rows; `status.py:127` falls back to the kind as the reason when the payload has none (`mcp.checked`, `draft.created`). |
| F20 | `bin/wuwei --help` prints a 55-name `{agents,board,...}` choice list and 55 rows in alphabetical order; plumbing (`event`, `hook`, `git-hook`, `payload`, `signal`, `board`) sits next to `next` and `plan`. | `cli/wuwei/__main__.py:27-28` builds one plain `ArgumentParser` with one `add_subparsers` and lets argparse format the help. |
| F21 | SessionStart context is 6017 bytes for one item; after the #358 orientation block and `Active constraints:` it carries `Today state:` with the whole day state as JSON, including the launch prompt (with absolute plugin paths). | `cli/wuwei/memory.py:116-125` (`session_payload`) dumps `state.read_state(root)` as JSON after the constraints block. `lifecycle.session_start` (`cli/wuwei/guards/lifecycle.py:48`) and `wuwei payload` both print it. |

#358 already gives SessionStart the orientation block with the `Next:` line, and
`memory.constraints` already gives goals, plan, open decisions and running briefs. What is
left for F21 is dropping the raw state and holding the result to a byte budget.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - nudges a person can act on (Priority: P1)

The owner or a session runs `bin/wuwei nudges` and reads one line per open page or nudge,
each with the command that clears it. Identical rows show once with a count. Tools keep the
JSON with `--json`.

**Why this priority**: it is the list every doc and refusal points at ("bin/wuwei nudges
lists open decisions"); on day one it reads as noise.

**Independent Test**: write today's events and state in `tmp_path` and call
`main(['nudges'])` and `main(['nudges', '--json'])` in process.

**Acceptance Scenarios** (issue Acceptance 1 and 2):

1. **Given** a routed decision `D-1` with no owner outcome, **When** `bin/wuwei nudges`
   runs, **Then** it prints the line
   `nudge: D-1 pending owner decision. Run: wuwei decision show D-1` and exits 0.
2. **Given** two `mcp.checked` events with exit 2 today, **Then** one line is printed for
   them, ending ` (2 times). Run: wuwei mcp check`, with a readable text instead of the
   bare kind.
3. **Given** a row whose reason already names a command (the stale planner row
   `... take over from the live session with: wuwei plan session <session id> --take-over`,
   or the phone-answer row `... confirm with decision outcome D-2 A`), **Then** the line
   is the reason with no `Run:` suffix.
4. **Given** a row whose source has no entry in the action table and whose reason names no
   command, **Then** the line ends `Run: wuwei next`.
5. **Given** no open rows, or no day state yet, **Then** it prints
   `No open pages or nudges.` and exits 0.
6. **Given** any of the above, **When** `--json` is passed, **Then** stdout is exactly
   today's output: `json.dumps(attention(day_dir))`, every row and duplicate kept, and
   `[]` when there is no day state.
7. **Given** an unreadable decision ledger, **Then** exit 2 with `wuwei nudges: <reason>`
   on stderr, with or without `--json` (unchanged).
8. **Given** two `adapter: none` events today (an adapter configured `none` was called),
   **Then** neither `nudges`, `nudges --json` nor `status --line` counts them.

### User Story 2 - grouped help (Priority: P1)

`bin/wuwei --help` lists commands in four groups, daily, owner (host terminal), recovery
and plumbing, with plumbing hidden unless `--all` is given.

**Why this priority**: help is the first thing a newcomer runs.

**Independent Test**: `main(['--help'])` and `main(['--help', '--all'])` in process.

**Acceptance Scenarios** (issue Acceptance 3):

1. **Given** `bin/wuwei --help` (or `-h`), **Then** exit 0 and stdout shows a short
   usage line, then the headings Daily, Owner, Recovery in that order, each command on its
   own line with its one-line help, `next` under Daily, `setup` under Owner, `doctor`
   under Recovery, no `hook`, `event`, `git-hook`, `payload`, `signal` or `board`, and a
   last line naming `bin/wuwei --help --all` and `bin/wuwei <command> --help`.
2. **Given** `bin/wuwei --help --all` (or `--all --help`, or `--all` alone), **Then** the
   Plumbing heading follows with the plumbing commands, and every registered command
   appears exactly once across the groups.
3. **Given** a command module that no group names (a new or third-party command),
   **Then** it is listed under a final `Other` heading in the default help, never hidden.
4. **Given** the shipped CLI, **Then** no command falls under `Other`.
5. **Given** `bin/wuwei <command> --help`, `bin/wuwei --version`, a bare `bin/wuwei` or an
   unknown command, **Then** behaviour is unchanged (exit codes and argparse messages).

### User Story 3 - a short session-start block (Priority: P1)

A session starting inside a workspace gets the orientation block, the active constraints
(goals, plan, open decisions, running briefs), spine, index, the promote line and the
health lines, and one line that says where the full state is. No raw state JSON and no
launch prompts.

**Why this priority**: every session pays for this context; launch prompts with absolute
paths are noise for the planner and leak local paths into the transcript.

**Independent Test**: pipe the recorded SessionStart payload through `hook.run` for a busy
day fixture and measure `additionalContext`.

**Acceptance Scenarios** (issue Acceptance 4):

1. **Given** a busy day (three approved items in `implement`, each build record holding a
   4000-character launch prompt, one running seat, two open decisions, the template spine,
   index and goals), **When** SessionStart runs, **Then** `additionalContext` is at most
   4096 bytes (UTF-8), contains the `Next:` line, `Goals:`, `Plan:`,
   `Open decisions: D-1, D-2`, and `Full day state: wuwei state get`, and contains neither
   the launch prompt text, `Today state:` nor `"approved_items"`.
2. **Given** `bin/wuwei payload`, **Then** it prints the same shortened payload and its
   size (it is the same function).
3. **Given** pending drafts, **Then** no draft body, input or destination is in the
   payload (the drafts nudge still shows them in `bin/wuwei nudges`).
4. **Given** SessionStart outside a workspace, **Then** nothing is printed and exit is 0
   (#323, unchanged).

### Edge Cases

- A `decision.pending` or `item.escalated` row whose reason is empty: the action falls back
  to `wuwei next`; never a crash on the first word.
- Rows merge only when tier, source and reason are all equal, so a page never hides inside
  a nudge count.
- Order: lines keep the order `status.scan` returns (PR changes first); a merged line takes
  the position of its first row.
- `--all` together with a subcommand (`bin/wuwei plan --all`) is not top-level help; it
  goes to argparse as today.
- The `adapter: none` silence covers every kind, including `tracker` (already silent through
  `tracker.call`) and `scanner`. An `mcp.checked` exit 2 is a security measurement that did
  not finish, not an adapter event, so it stays a nudge; `security.areas.mcp = "off"`
  already stops the check before it records one.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `wuwei nudges` without flags prints one line per distinct
  `(tier, source, reason)` row of `status.attention(day_dir)`, in first-seen order:
  `<tier>: <text>[ (<n> times)][. Run: <command>]`.
- **FR-002**: `<text>` and `<command>` come from one small table in `commands/nudges.py`
  keyed by source; `{reason}` and `{id}` (the reason's first word) are the only
  placeholders, and an entry whose command is `None` prints no `Run:` (the reason already
  says what to do). Without a table entry, `<text>` is the reason; the command is omitted when
  the reason already contains `wuwei ` or `/wuwei:`, else it is `wuwei next`.
- **FR-003**: `wuwei nudges --json` prints exactly what `wuwei nudges` prints today.
- **FR-004**: `adapter: none` is a silent kind in `signal.SILENT`, so no surface (nudges,
  status line, board, DM digest) counts a call to an adapter configured `none`. The adapter
  call itself still returns exit 2 `unmeasured` to its caller (Principle II unchanged).
- **FR-005**: `bin/wuwei --help`, `-h`, `--all` and their combinations with no subcommand
  print grouped help from one `GROUPS` table in `cli/wuwei/__main__.py` and exit 0;
  plumbing is printed only with `--all`; unnamed commands print under `Other`.
- **FR-006**: The subcommand usage metavar is `<command>`, so usage lines no longer print
  the 55-name brace list.
- **FR-007**: `memory.session_payload` drops the `Today state:` JSON (and the drafts
  mapping that only existed for it) and puts the line `Full day state: wuwei state get` in
  its place. The `Active constraints:` block, spine, index and promote line stay, in order.
- **FR-008**: A test pins the SessionStart context of the busy-day fixture at 4096 bytes or
  less.
- **FR-009**: Docs follow the behaviour: `reference.md` says `bin/wuwei --help --all` lists
  every command and marks every plumbing command; `configuration.md` describes the line
  format, the merge, `--json` (whose count matches the status line) and that calls to any
  adapter set to `none` are silent; `daily.md` Re-anchoring names `bin/wuwei state get` for
  the full state.
- **FR-010**: No new state key, event kind, config key or file. Nothing trusts the new
  output, so no `state.RESERVED` change.

### Key Entities

- **Nudge line**: display text derived from an attention row `{tier, source, lane, reason}`
  plus a count; never stored.
- **Command group**: a heading and an ordered tuple of command names in `__main__.GROUPS`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The day-one reproduction prints two lines from `bin/wuwei nudges` (one MCP
  line with a count, one decision line) instead of five JSON rows, and no adapter row.
- **SC-002**: `bin/wuwei --help` shows 42 command rows (55 minus the 13 plumbing commands)
  under three headings.
- **SC-003**: The busy-day SessionStart context is at most 4096 bytes; the same fixture on
  `main` is over 12000.
- **SC-004**: The full suite passes, including `test_reference_lists_every_cli_command`
  (now reading `--help --all`) and the hook latency tests.

## Assumptions

- The notes name no dry-run workspace; the failure was reproduced in a scratch workspace
  built like the `tests/test_next.py` fixture, with the day-one events the review quotes.
- "No nudge for an adapter configured none": every `adapter: none` event comes from an
  `adapters/<kind>/none.py` module, which `registry.load` loads only when config selects
  `none`, so silencing the kind is exactly that rule. It is done in `signal.SILENT`, the
  shared classifier, not in `nudges`, so the status line count agrees with the list.
- `mcp.checked` with a nonzero exit stays a nudge: it is the MCP registry check (design
  spec 7, S3) reporting unmeasured or findings, and Principle II says unmeasured is never
  quiet. It gets readable text and `wuwei mcp check`. Whether a scanner set to `none`
  should switch the MCP area off is a setup question for the first-day issue, not here.
- Merging happens only in the human output. `--json` and `status --json` keep one row per
  cause, because the watch sweep deliberately emits one row per owed reply and the counts
  on the status line, board and SwiftBar read those rows.
- The action table covers the sources whose reason names no command and whose command is
  certain: `decision.pending`, `item.escalated`, `mcp.checked`, `draft.created`,
  `watch: health`, `listen: health`, `watch: sweep:unmeasured`, plus `decision.answered`
  with no command because its reason already names `decision outcome D-n <option>`.
  Everything else falls back
  to its own reason or `wuwei next` (the single next-step derivation from #358). Rewriting
  the reason strings at their producers belongs to the sweep's reason-format issue
  (catalogue d), as do the `lifecycle.py:38` and `:96` unmeasured messages.
- Commands in lines use the `wuwei ...` form, as `wuwei next` does; owner-only steps keep
  `bin/wuwei` (`drafts`). F15 (launcher path in fixes) is a separate finding.
- Group membership is a judgment the issue leaves open. Daily: next, status, nudges, plan,
  decision, worktree, brief, build, dispatch, pr, merge, reply, discover, note, metrics,
  report, retro, close, steward. Owner (host terminal): setup, init, config, calibrate,
  goals, voice, drafts, remote, mcp, outbound, watch, listen, dashboard, promote,
  consolidate. Recovery: doctor, why, state, shadow, heartbeat, integrity, runtime,
  sessions. Plumbing: agents, board, event, fast-checks, git-hook, hook, index, memory,
  payload, rank, signal, sweep, verdict.
- The byte budget is a test over a fixed busy-day fixture, not runtime truncation. Spine
  and index are owner memory already bounded by `memory.max_notes` and the memory lint;
  truncating them would hide owner content. 4096 bytes leaves room for a long plugin path
  (the orientation block prints it four times).
- The SessionStart payload loses the draft id-to-destination map added by #227 FR-010.
  Pending drafts are owner attention and show in `bin/wuwei nudges`; `wuwei state get`
  prints the full record on request.
- Design spec 6.3 says session start "loads spine, index and today's state". After this
  change today's state is loaded as the constraints summary with a pointer to
  `wuwei state get`. The design spec is amended only by its owner, so it is not edited
  here; this is raised for the owner in the delivery report.
- `--all` is read only for top-level help, by a check on `argv` before argparse, because
  argparse prints help as soon as it meets `--help`, before it reads later flags.

## Deferred

- Producer-side reason rewrites (catalogue d of the sweep), including a `reason` in the
  `mcp.checked` and `draft.created` payloads.
- Feeding the nudge lines to the DM digest or the board; both read rows, not lines.
