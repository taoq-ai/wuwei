# Feature Specification: delete what the derived next replaced

**Feature Branch**: `b9-cleanup` (feature directory `specs/847-replaced-machinery-out/`)

**Created**: 2026-10-12

**Status**: Draft

**Input**: Issue #847, part 23 of the #789 deletion pass: "chore(loop): delete what the derived
next replaced: watch, heartbeat, headless shepherd, sessions, obligations, the records and stop
guards".

## Context

Part 22 (#844, batch 8) made `wuwei next` derive the day from the event log, the worktree
HEADs, the verdict files and one cached PR listing, and made `state.json` a cache of the log.
Outward steps became duties that `next` lists and `close` waits on. What the loop used before
is now dead weight or a second source of truth:

- the watch: a background process (launchd or systemd unit) that polled owned PRs, swept
  obligations and staleness, woke the planner and ran the steward, the tracker log and the
  telemetry week;
- the heartbeat: a timed probe of the hooks and the day, written into state for the status
  line and doctor;
- the headless shepherd: a scheduled model-free PR sweep with an overnight report;
- the session registry: every hook touched a session row, claims tied items to sessions, the
  Stop hook rotated long sessions;
- obligations as a close gate and as a sweep;
- commands that only fed the above or let a model hand-edit records: `event`, `state`,
  `git-hook`, `fast-checks`, `runtime`, `watch`, `heartbeat`, `shepherd`, `sessions`, and the
  `obligations` and `watch` subcommands of `sweep`;
- in `state.py`: the snapshot, `recover`, the generic state writer with its producer table,
  and the phase transition check (the `state.json` cache stays, lead call B9(a));
- guards: the Stop guard, the PreCompact and Stop hook branches, the state-file hint of the
  records guard.

Batch 8's builder named what this part may delete: the watch's PR polling, `merge.monitor`'s
tracker call, `status.scan` as a `next` row, the headless shepherd, obligations as the close
gate for pings, `state.py`'s snapshot and recover, and the `state.json` existence checks. The
batch 8 review fix round (findings F1 to F9, G1 to G9) runs in parallel; this part designs
against its fixed end state (plan.md, "Batch 8 fix round").

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The loop runs a whole day with no background process (Priority: P1)

**Why this priority**: the issue's first acceptance line; the derived `next` must carry the day
alone.

**Independent Test**: `tests/test_e2e_day.py`, `tests/test_path_day.py` and
`tests/test_loop.py` pass with the watch, heartbeat, headless shepherd and session registry
deleted.

**Acceptance Scenarios**:

1. **Given** a scripted day, **When** the planner walks only `wuwei next`, **Then** the day
   closes and no step names `watch`, `heartbeat`, `shepherd`, `sessions`, `event`, `state`,
   `git-hook`, `fast-checks` or `runtime`.
2. **Given** the CLI, **When** any of those commands or `sweep obligations` or `sweep watch`
   runs, **Then** argparse refuses it as unknown (exit 2).
3. **Given** `hooks/hooks.json`, **When** Claude Code loads the plugin, **Then** only
   PreToolUse, PostToolUse, SubagentStop and SessionStart are registered.

### User Story 2 - Outward duties, the close wait and the edges still hold (Priority: P1)

**Why this priority**: the issue's second acceptance line and the owner's outward-duty rule.

**Acceptance Scenarios**:

1. **Given** an item with a PR and `duties.on = ["ping", "shepherd", "tracker"]`, **When**
   `next` runs, **Then** each due duty is listed with its prompt and `close` refuses until each
   is `duty.done` or `duty.skipped`.
2. **Given** a builder worktree, **When** a Bash call runs `git push origin HEAD:main` against
   the repository's default branch, **Then** the PreToolUse edge refuses it naming
   `wuwei pr raise --item` (#839), although no managed Git hook exists.
3. **Given** a merged PR, **When** `next` runs, **Then** the tracker duty is due; no code path
   calls the tracker's `done` on its own.

### User Story 3 - The event log is the only record (Priority: P1)

**Why this priority**: two sources of truth were the root of the drift the study days found.

**Acceptance Scenarios**:

1. **Given** any state write, **When** it completes, **Then** `events.jsonl` holds the patch and
   no `state.snapshot.json` is written; `state.json` stays the cache of the log (fingerprint,
   log identity and size), so no hook folds the whole day log (lead call B9(a)).
2. **Given** a day log whose last line is torn, **When** any command reads state, **Then** the
   torn line is skipped and the records before it are read (batch 8 F4).
3. **Given** a day from before #844 (a `state.json` and no patch in its log), **When** a reader
   folds it, **Then** it reads that `state.json` once, read-only, and the next write carries it
   into the log.
4. **Given** a malformed patch line that is not the torn tail, **When** state is read, **Then**
   the read refuses with DAMAGED naming `bin/wuwei doctor`, never `state recover`.

### User Story 4 - The jobs the watch did that stay still happen (Priority: P1)

**Why this priority**: the watch carried four kept jobs; deleting it must not delete them.

**Acceptance Scenarios**:

1. **Given** a merge recorded by `wuwei merge`, **When** `next` refreshes the PR listing or the
   day's `report` runs, **Then** `merge.poll` supervises base checks (a red base trips
   auto-merge and reverts) and records the 14-day outcome the 5.6 escaped-defect metric reads.
2. **Given** seat traces with a scanner chain, **When** a gate verdict is received or the day
   closes, **Then** `scanner.trace_sweep` pages and parks as the watch sweep did.
3. **Given** a finished telemetry week, **When** `report` runs, **Then** `telemetry.step`
   records it (never the report's exit).
4. **Given** tracker comments owed, **When** `close` runs clean, **Then** `tracker.log` writes
   them (unchanged).

### User Story 5 - `init --upgrade` cleans an existing workspace (Priority: P2)

**Acceptance Scenarios**:

1. **Given** a workspace with item worktrees whose worktree-scoped `core.hooksPath` points at
   `.wuwei/git-hooks` or at the chain directory `<git dir>/wuwei-hooks`, **When**
   `init --upgrade` runs, **Then** each such `core.hooksPath` is unset, the chain directory and
   `.wuwei/git-hooks/` are removed, the workspace anchor stays, and one line per worktree says
   so; `--dry-run` prints `Would ...` and changes nothing.
2. **Given** an installed watch or shepherd launchd or systemd unit, **When** `init --upgrade`
   runs, **Then** the unit is stopped and removed, as the `listen` unit is today, and its lock
   and log files under `.wuwei/` are removed.
3. **Given** a config with `[watch]`, `[sessions]` or `worktree.git_hooks`, **When**
   `init --upgrade` runs, **Then** each key is removed and reported.

### Edge Cases

- A worktree whose `core.hooksPath` the owner set to their own directory keeps it: only the two
  WUWEI values are unset.
- A repository's own hooks that the chain used to run now run natively (no chain is left).
- A legacy `state.json` written by hand into today's directory: the records guard still refuses
  a seat write to `days/*/state.json` (the records floor), so it cannot inject records.
- Past days keep their `state.json`, `state.snapshot.json` and events; history is not rewritten.
- `pr act --reply` still posts a reply through the PR-thread helpers; the merge policy still
  refuses a merge with an unanswered review thread.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: These files MUST be deleted with their tests: `cli/wuwei/heartbeat.py`,
  `cli/wuwei/commands/{heartbeat,watch,shepherd,sessions,event,state,git_hook,fast_checks,runtime}.py`,
  `cli/wuwei/guards/stop.py`, `templates/wuwei-watch.plist`, `templates/wuwei-watch.service`.
- **FR-002**: `cli/wuwei/watch.py` MUST keep only the day record readers (`ERRORS`, `records`,
  `_rows`, `_not_json`, `_finite`, `days`) and the PR helpers kept code calls (`owned`,
  `evidence`, `saved`, `save`, `previous`); the loop, health, wake, sweep, poll and flush go.
- **FR-003**: `cli/wuwei/shepherd.py` MUST lose the headless half (`owning_day` to the end);
  `plan.propose` loses its overnight lines; `workspace._DAY` goes.
- **FR-004**: `cli/wuwei/sessions.py` MUST keep the Owner step card API (`card_topic`,
  `OWNER_STEP`, `owner_card`, `owner_topic`, `owner_answer`, `needs_owner`,
  `owner_step_call`), the session identity (`current`, `export`) and the planner and seat
  rows (`record`, `registered`); `touch`, `rotation`, `_due`, `rows`, `claim`, `claim_item`,
  `stale_seconds`, `COUNTED` and `count` go, with every claim write and read.
- **FR-005**: `obligations.evaluate` and `obligations.sweep` MUST go; `closing.check` MUST NOT
  call them. The PR-thread helpers the merge policy and `pr act --reply` read stay.
- **FR-006**: `state.py` MUST write no snapshot and MUST keep the `state.json` cache of the log
  with batch 8's fingerprint, log identity and size checks (F4 to F8, lead call B9(a)); MUST
  read a pre-#844 day's `state.json` when its log holds no patch; MUST drop `SNAPSHOT`, `_load`, `recover`, `write_state`, `set_state`,
  `get_state`, `_parts`, `_generic_allowed`, `_protected`, `_producer_error`,
  `STATE_PRODUCERS`, `OWNER_FIELDS`, the `reserved` branch of `_write_state` and
  `_check_transition`. `transition` stays as a phase write without the check.
- **FR-007**: No refusal or error text MUST name `state recover`, `state set`,
  `state transition`, `state get`, `wuwei event`, `wuwei fast-checks`, `git-hook`,
  `watch install`, `runtime dispatch` or `wuwei sessions`.
- **FR-008**: The PreCompact and Stop hooks MUST go from `hooks/hooks.json`,
  `guards/__init__.py`, `guards/lifecycle.py` and `commands/hook.py`.
- **FR-009**: `merge.poll` MUST run from `next.run` whenever it refreshes the PR listing and
  from `report`; `merge.monitor` MUST NOT call the tracker.
- **FR-010**: `scanner.trace_sweep` MUST run from `dispatch receive` and from `close`;
  `telemetry.step` MUST run from `report`.
- **FR-011**: Worktree creation and adoption MUST write the workspace anchor without managed
  Git hooks; `init --upgrade` MUST unset WUWEI's `core.hooksPath` in every existing worktree,
  remove `.wuwei/git-hooks/` and the chain directories, and remove the watch and shepherd units
  with their lock and log files.
- **FR-012**: `doctor` MUST keep a hooks row (a refused and an allowed probe through
  `wuwei hook`, exit codes only, no timings) and a day row (state readable, stuck seats from
  the seat ledger) without the heartbeat.
- **FR-013**: The `watch` and `sessions` tables and `worktree.git_hooks` MUST leave the schema
  and template and join `workspace.RETIRED`.
- **FR-014**: The design spec, the constitution's long-running-process line and the builder
  charter's heartbeat line MUST stop naming deleted units; agents are rebuilt.

### Key Entities

- **Day log** (`days/<date>/events.jsonl`): append-only; each state write carries its patch.
- **PR-thread ledger** (obligations helpers): replies and visibility the merge policy reads.
- **Merge journal** (`merge.py`): what `merge.poll` supervises for 28 days after a merge.

## Success Criteria *(mandatory)*

- **SC-001**: `grep -rnE "wuwei\.heartbeat|commands\.(watch|shepherd|sessions|event|state|git_hook|fast_checks|runtime)\b|state recover|state\.snapshot|SNAPSHOT|sessions\.(touch|rotation|claim|rows)|guards\.stop|PreCompact"`
  over `cli/`, `adapters/`, `hooks/`, `charters/`, `skills/`, `agents/`, `templates/` and
  `scripts/` returns nothing.
- **SC-002**: The scripted day, the path day and the loop property test pass.
- **SC-003**: `bin/wuwei --help` lists 36 commands (45 less the 9 deleted).
- **SC-004**: The edge tables in `tests/test_edges.py` pass unchanged, including the
  default-branch push rows.
- **SC-005**: Every touched test file passes; no test is loosened.

## Assumptions

Open questions answered with the recommendation (strict, non-interactive):

1. Superseded by lead call B9(a) (2026-10-12): the `state.json` cache stays, with batch 8's
   fingerprint, log identity and size (F4 to F8), so a hook reads the cache and folds only the
   log tail past its size, never the whole day log. Only the snapshot, `recover` and the
   `state.json` existence checks go.
2. `closing.py` stays as `close`'s library (open items, duties, pushed branches, scanner hold,
   retro landing); only its call to `obligations.evaluate` goes. Moving its 250 lines into
   `commands/close.py` would be churn, not deletion.
3. `obligations.py` keeps its name and the PR-thread helpers the merge policy (`_ledger`,
   `_replies`, `_visibility`, `_owner_login`) and `pr act --reply` (`reply`) read. Those are
   (b): a merge with an unanswered review thread is refused.
4. `watch.py` keeps its name for the readers left in it; a rename touches 25 importers for no
   behaviour.
5. `transition` stays as a seven-line phase write (`build next` and 15 test files use it);
   `_check_transition` goes because the derived `next` never offers an out-of-order step and
   `pr raise --item` and `merge.check` still refuse.
6. `merge.poll` is (b): it trips auto-merge and reverts on a red base, and it records the
   outcomes the 5.6 escaped-defect metric reads. It moves to `next.run` (with the listing
   refresh, throttled by `pr.poll_seconds`) and to `report` (once a day, so measurement goes on
   on days with no PR).
7. `scanner.trace_sweep` moves to `dispatch receive` (before raise, where a finding matters)
   and `close`. The steward's sweep trigger goes; the close trigger stays.
8. `telemetry.step` moves to `report`; the constitution says aggregation runs only in CLI
   commands, and `report` runs once a day.
9. Session age bands and planner Stop turns in metrics, report and retro measured the session
   registry and the Stop hook; they go with them (process introspection, not 5.6 outcomes).
10. `status` keeps `--line`; its watch health, heartbeat rows and cached fallback go. Part 24
    decides the command's place in `--help`.
11. The records guard (`guards/protect_state.py`) stays except the snapshot name and the hint
    naming `wuwei state set`, `state transition` and `wuwei event`; `days/*/state.json` stays
    protected while legacy days are read (records floor, constitution VII).
12. Day directories are history: `init --upgrade` removes no file inside `days/`.
13. `adapters/watch_service.py` keeps `call` (unit removal), `probe` (doctor) and `post`
    (telemetry); `ping` goes.
14. The runtime adapters keep their ports: `build next`, `dispatch` and `steward` still call
    `dispatch`, `status`, `result` and `continue_job`; only the `runtime` command goes.
15. The pre-commit identity check and the pre-push fast-check evidence check go with
    `git-hook`: the builder's fast checks at HEAD are `build next`'s handoff rule (pass plan,
    "Process control kept"), and `pr raise` still checks every pushed commit's identity
    (`commit_push.push_check`).

## Deferred

- Part 24 (#848): `bin/wuwei --help` down to about 20 commands, `sweep classes`, the docs site
  and README rewrite (this part edits docs only where `tests/test_docs.py` forces it), the hero
  text naming the heartbeat and the overnight shepherd, obsolete workspace files.
- Part 25 (#849): the timing assertions this part does not already delete with their code.
