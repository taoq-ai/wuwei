# Feature Specification: Operator records and owner-action consistency after the fourth dry run

**Feature Branch**: `247-records-after-dryrun4`

**Created**: 2026-09-30

**Status**: Ready

**Input**: GitHub issue #247, "fix(cli): operator records and owner-action consistency after the fourth dry run". Design spec sections 3.4 (three-state exits), 5.4 (when the user is asked), 5.7 (goals, discovery and prioritisation) and 5.9 (cockpit, signals and briefings); follows #209, #227 and #233. Depends on none. Evidence: the fourth operator dry run on the v0.6.1 asset (2026-09-30 afternoon), a full day completed with no CLI workaround.

## Root causes (reproduced read-only)

Reproduced on `main` (v0.6.1 plus #242) against a scratch copy of the dry-run workspace and from its step log. `bin/wuwei nudges` on the copy prints a `steward.due` nudge although `events.jsonl` has the `steward.due` event (line 116) followed by a `steward.run` event (line 118); `state get items.DIVIDE-1.status` prints `"queued"` with phase `"merged"`; the day holds two close steward briefs, and only the second one was ever launched as a seat. Prepending `repos = []` to the copy's `config.toml` makes `hook PreToolUse` for `ls` refuse with `integrity unmeasured: <absolute path>/.wuwei/config.toml: Cannot mutate immutable namespace ('repos',) (at line 195, column 8)`.

| Dry-run step | What the operator saw | Root cause |
|---|---|---|
| `nudges-after-steward`, `nudges-after-sweep2`, `status-end` | `steward.due` nudge and `nudges 1` after `steward run --trigger tool-calls` ran, all the way to the end of the day | `cli/wuwei/commands/status.py:26-128` (`scan`) keys the `steward.due` row by event line number (`:97-98`) and never drops it. `steward.run` is in `signal.SILENT` (`cli/wuwei/signal.py:20`), so `scan` skips it at `:67-68` before anything can clear the due row. `steward.due` itself is a nudge (`signal.py:79-81`). `nudges` (`commands/nudges.py:17`) and the status line read the same `scan`. |
| `ack-probe` | `steward ack steward.due` exit 1 `unknown steward note`; the id is documented nowhere | `cli/wuwei/commands/steward.py:13-14` registers `ack` and `id` without help. Note ids are `<item>-fix-3` (`cli/wuwei/steward.py:26`), named only by the `dispatch next` refusal `steward note <id> requires planner acknowledgement` (`cli/wuwei/dispatch.py:62`). `docs/site/reference.md` never mentions `steward ack`. |
| `retro1`, `retro2` (Cycle table) | `\| DIVIDE-1 \| merged \| queued \| 1 \|` | `state._move` (`cli/wuwei/state.py:367-372`), the one function every phase move to `merged` goes through (`state.transition` at `:375-383` and the PR observer at `cli/wuwei/pr_actions.py:222`), changes only `phase`. Item `status` keeps the `queued` default from `ITEM_DEFAULTS` (`state.py:43`). `retro.compile` prints both (`cli/wuwei/retro.py:95`). `tests/test_report_retro.py:36` already expects `\| A \| merged \| done \|`. |
| `close-early`, then `steward-run` | two close steward briefs (`steward-5f77...`, `steward-e0fc...`); the first, printed by `close`, was never launched | `wuwei close` runs the close review when today has none (`cli/wuwei/commands/close.py:23-25`). `skills/wuwei-retro/SKILL.md:10` then tells the operator to run `wuwei steward run --trigger close` "if today's close review has not run", which the operator cannot tell, and `steward.run` (`cli/wuwei/steward.py:106-140`) writes a new brief on every call with no close check. |
| `cfgcheck`, `integrity-after-cfg` | `integrity unmeasured: <absolute path>/.wuwei/config.toml: Cannot mutate immutable namespace ...` on every tool call | `workspace.load_config` wraps every config error as `f"{path}: {exc}"` with the absolute path (`cli/wuwei/workspace.py:429-430`). The error surfaces through `workspace.scope` (`workspace.py:229`) inside `guard_scope`, and the integrity guard, the one PreToolUse guard that runs on every call, prefixes it with `integrity unmeasured:` (`cli/wuwei/guards/integrity.py:14-15`, and `:27-28` for SessionStart), so the owner reads it as an integrity failure. |
| `report` | `- Review rework: {'mean_per_pr': 0, ...}; baseline: unmeasured` | `cli/wuwei/report.py:34-37` interpolates metric values with an f-string; a dict value prints as a Python repr. |
| `check1`, `next3` | `python3 -m pytest -q: {'test_ids': [...], 'error': '...'}` in stderr and in the builder's `feedback` | `cli/wuwei/commands/build.py:360` formats each failure as `f'{name}: {data}'`, a Python repr of the check result data. |
| `drafts-approve-notty` | `drafts approve` without a terminal sent the draft, exit 0 | `drafts.approve` (`cli/wuwei/drafts.py:113-172`) never asks for confirmation, while `decision outcome` (`cli/wuwei/commands/decision.py:79-81`), `state recover` (`cli/wuwei/commands/state.py:33`), `integrity reconfirm` and `mcp decide` confirm through `integrity._host_confirm` (`cli/wuwei/integrity.py:200-215`), which raises `OSError('this is an owner action: run it in a host terminal')` without a terminal. `docs/site/reference.md:179` says approve asks for no digest. |
| `init`, `p2-init`, `p2-git-status` | a bare `{"statusLine": ...}` line with no word on where it goes; in a project that is a Git repository, `git status` shows `?? .claude/` and `?? .wuwei/` | `cli/wuwei/commands/init.py:84-85` (and `:227-228` for `--upgrade`) prints only the JSON; nothing mentions `.gitignore`. |

## User Scenarios & Testing

### User Story 1 - A steward run clears the steward nudge, and ack ids are documented (Priority: P1)

After 50 tool calls the status line shows a `steward.due` nudge. The planner runs `wuwei steward run --trigger tool-calls` as its charter says. The nudge goes away. When the planner does need `steward ack`, the help and the reference page say which id to pass.

**Independent Test**: a day with a `steward.due` event, then a `steward.run` event; read `nudges` and `status --json`.

**Acceptance Scenarios**:

1. **Given** a `steward.due` event followed by a `steward.run` event (any trigger) today, **When** `wuwei nudges` and `wuwei status --line` run, **Then** neither lists the `steward.due` nudge (`nudges` has no row with source `steward.due`, the line no longer counts it).
2. **Given** a `steward.run` event followed by a later `steward.due` event, **Then** the `steward.due` nudge is listed (a due after the run is still owed).
3. **When** `wuwei steward ack --help` runs, **Then** the output names the note id form `<item>-fix-3`, where it comes from (the `steward note <id> requires planner acknowledgement` refusal), and that a `steward.due` nudge takes no ack but clears when `steward run` records a run.
4. `docs/site/reference.md` says the same for `steward ack`.

### User Story 2 - A merged item reads as done (Priority: P1)

**Acceptance Scenarios**:

1. **Given** an item moved to phase `merged` (through `state transition` or the PR observer), **When** `wuwei state get items.<item>.status` runs, **Then** it prints `"done"`.
2. **Given** that item, **When** `wuwei retro` compiles, **Then** its Cycle row is `| <item> | merged | done | <fix rounds> |`.
3. Items in every other phase keep the status they have today.

### User Story 3 - One close steward review per day (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a day with state and no close steward review, **When** `wuwei close` runs, **Then** exactly one steward brief exists, one `steward.run` event with trigger `close` is recorded, and `close` prints its `steward_launch`.
2. **Given** that day, **When** `wuwei steward run --trigger close` runs, **Then** it exits 0, writes no brief, dispatches nothing, records no event, and prints `steward: close review already ran today (brief <path of the first brief>)`. A repeated `wuwei close` behaves the same way: still exactly one close steward brief.
3. `skills/wuwei-retro/SKILL.md` no longer asks the operator to run `wuwei steward run --trigger close`; it says `wuwei close` runs the close steward review once and prints the `steward_launch` to launch.
4. `--trigger sweep` and `--trigger tool-calls` runs are unchanged: each still writes a brief.

### User Story 4 - A config.toml error names config.toml (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a TOML syntax error in `.wuwei/config.toml` (for example `repos = []` before a `[[repos]]` table), **When** `workspace.load_config` reads it, **Then** the error message starts with `config.toml:` followed by the parser's message with its line and column, and contains no absolute path.
2. **Given** that config, **When** `wuwei hook PreToolUse` runs for `ls` inside the workspace, **Then** it refuses (exit 2) and the reason starts with `config.toml:`, not `integrity unmeasured:`.
3. **Given** that config, **When** SessionStart runs, **Then** the integrity guard's message also starts with `config.toml:`.
4. A schema error (unknown key, wrong type) is reported the same way, `config.toml: <error>`.

### User Story 5 - Records print JSON, not Python reprs (Priority: P2)

**Acceptance Scenarios**:

1. **Given** a measured `review_rework` (a mapping), **When** `wuwei report` runs, **Then** the `Review rework:` value parses as JSON and the report contains no `{'`. Scalar values (`unmeasured`, `0.2`, `32 minutes`) print as today.
2. **Given** a failing fast check with `{'test_ids': [...], 'error': '...'}` data, **When** `wuwei build check <item>` exits 1, **Then** the printed feedback and the `continue` action's `feedback` are `<command>: <JSON>`, where the JSON parses back to the check data.

### User Story 6 - Draft approval is an owner action with a typed digest (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a pending draft and no terminal, **When** `wuwei drafts approve <id>` runs, **Then** it exits 2, stderr contains `this is an owner action: run it in a host terminal`, nothing is sent, and the draft stays `pending`.
2. **Given** a pending draft and a terminal where the owner types the shown digest, **Then** the draft is sent once, as today.
3. **Given** the owner types anything else, **Then** it exits 1 with `drafts: owner confirmation declined`, nothing is sent, and the draft stays `pending`.
4. **Given** `--edit`, **Then** the digest covers the final (edited) text, which the prompt shows with the destination.
5. `docs/site/reference.md` lists `drafts approve` as asking for a digest; `drafts drop` still does not.

### User Story 7 - init says where its output goes (Priority: P3)

**Acceptance Scenarios**:

1. **When** `wuwei init` runs, **Then** the line after the `statusLine` JSON says to put it under the `statusLine` key of `.claude/settings.json` (this project) or `~/.claude/settings.json` (every project). The JSON stays on its own line, the second line of output. `init --upgrade` prints the same hint after its JSON.
2. **Given** a project directory that is itself a Git repository (has `.git`), **When** `wuwei init` runs there, **Then** it prints a line saying to add these to the project's `.gitignore`, followed by the two lines `.wuwei/` and `.claude/`.
3. **Given** a project directory without `.git`, **Then** no `.gitignore` lines are printed.

### Edge Cases

- `steward.due` and `steward.run` events from a previous day are both ignored (scan reads only today's events), as today.
- `steward run --trigger close` on a day whose only close run failed to launch: a failed launch records no `steward.run` event (`steward.py:133-135` removes the brief and re-raises), so the next close run proceeds.
- `wuwei event` refuses `steward.run` from seats (`cli/wuwei/commands/event.py:49`), so a seat cannot forge a close run to suppress the review.
- `drafts approve` where the lint refuses: it returns the lint finding before asking for a digest, as today.
- A draft that changes between confirmation and claim: the existing claim check (`drafts.py:146-148`) refuses it.
- A config error while the day's `state.json` is also unreadable: each surface still exits 2 with a reason.

## Requirements

### Functional Requirements

- **FR-001**: `status.scan` MUST drop every open `steward.due` row when it reads a later `steward.run` event, in the same single pass.
- **FR-002**: `steward ack --help` and `docs/site/reference.md` MUST name the steward note id form and its source, and say that `steward.due` clears on a recorded `steward run`.
- **FR-003**: Moving an item to phase `merged` MUST set its status to `done`, in `state._move`.
- **FR-004**: `steward.run` with trigger `close` MUST be a no-op that prints `steward: close review already ran today (brief <path>)` and exits 0 when today already has a `steward.run` event with trigger `close`. `wuwei close` MUST rely on that check instead of its own.
- **FR-005**: `skills/wuwei-retro/SKILL.md` MUST say that `wuwei close` runs the close steward review and MUST NOT ask for a second run.
- **FR-006**: `workspace.load_config` MUST report every config error as `config.toml: <error>`. The integrity guard (PreToolUse and SessionStart) MUST pass a `workspace.ConfigError` message through unprefixed.
- **FR-007**: `report` MUST print mapping metric values in the Outcome section as JSON; `build check` feedback MUST print each failure's data as JSON.
- **FR-008**: `drafts.approve` MUST ask the owner to type a digest of the draft id and the final text through `integrity._host_confirm` before claiming the draft. Without a terminal it MUST return exit 2 with the owner-action sentence and change nothing.
- **FR-009**: `init` MUST print where the `statusLine` JSON goes, and, when the project directory has `.git`, the two `.gitignore` lines `.wuwei/` and `.claude/`.

### Key Entities

- No new state key, event kind, config key or adapter operation. The `steward.run`, `steward.due` and `draft.*` events are unchanged.

## Success Criteria

- **SC-001**: Replaying the dry-run day, `nudges` has no `steward.due` row at the end of the day.
- **SC-002**: A day that runs `close` before the retro, then the retro skill, has exactly one close steward brief.
- **SC-003**: Every owner action that sends or records something on the owner's behalf with a digest (`decision outcome`, `state recover`, `integrity reconfirm`, `mcp decide`, `drafts approve`) exits 2 with the same sentence without a terminal.
- **SC-004**: No operator-facing record from `report` or `build check` contains a Python repr.
- **SC-005**: The full suite passes and no guard refuses less than before.

## Assumptions

- Any recorded `steward.run` clears `steward.due`, whatever its trigger: `steward.maybe_run_for_tool_calls` (`steward.py:143-156`) already counts the next due from the last run of any trigger.
- "Consistent with the phase" is met by `merged` setting `done`. The other statuses keep today's meaning (`queued` means no seat holds the item, `blocked` is set with a park); `raised` stays `queued`. No migration: an item merged earlier today with `queued` keeps it.
- "The same close" is the same day, the scope `close.py` already uses. The no-op names the first brief so the operator can find it; it does not re-dispatch or re-print a launch.
- The config message is `config.toml:` without the `.wuwei/` directory, as the issue's acceptance states. Other guards that could not run (commit/push, deploy, PR) keep naming themselves before the same `config.toml:` message; only the integrity guard, which runs on every call, passes it through. CLI commands keep their `wuwei <command>:` prefix. `commands/config.py` (in flight in #243) and the `init --upgrade` TOML pre-check are unchanged.
- The retro skill keeps the order the headless e2e already uses: `wuwei close` before the retro (it refuses for the missing retro but runs and prints the close steward launch), then the retro, then `close` again.
- `drafts drop` sends nothing and keeps no digest, as the issue asks only for approve. The digest covers the draft id and the final text, so an edit changes what the owner confirms. The prompt shows the destination and the final text on the owner's terminal, which is not a log.
- `init` does not write `statusLine` into any settings file: `tests/test_signal_status.py:182` fixes that owner settings are never written. "Is itself a Git repository" means the project directory has `.git`; a project nested inside another repository gets no hint.
- Report metric values that are mappings print as sorted-key JSON; scalars print unchanged so existing baseline text stays readable. Build feedback uses `json.dumps` on the check data; the stuck-loop signature (`build.py:65-71`) reads the data, not the text, so it is unchanged.
- In-flight issues #238, #239, #240 and #243 own the `docs/site` daily path page, `tests/test_e2e_day.py`, `scripts/headless_e2e.py`, `cli/wuwei/guards/__init__.py` and `cli/wuwei/commands/config.py`; this feature does not touch them. New tests live in a new file so they do not collide with in-flight test edits.
