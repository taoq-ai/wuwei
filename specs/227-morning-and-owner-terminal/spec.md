# Feature Specification: The morning before the first plan, owner actions on a terminal, and operator records

**Feature Branch**: `227-morning-and-owner-terminal`

**Created**: 2026-09-30

**Status**: Ready

**Input**: GitHub issue #227, "fix(cli): the morning before the first plan, owner actions on a terminal, and operator records". Design spec sections 3.4 (three-state exits), 5.4 (when the user is asked), 5.7 (goals, discovery and prioritisation) and 5.9 (cockpit, signals and briefings). Depends on #171, #209, #211. Evidence: the v0.6.0 operator dry run of 2026-09-30 (a full day completed).

## Root causes (reproduced read-only from the v0.6.0 dry-run workspace and its step log)

The morning checks were also re-run on `main` against a scratch copy of the dry-run workspace (the first three day events plus a `state.json` holding only `planner_session_id`): `obligations.evaluate` printed `obligations UNREADABLE: no recorded PR state for today` and returned exit 2, and with `state.json` removed `status --line` printed `WUWEI ? unmeasured` and exited 2 (`day state is missing`). `integrity._host_confirm` without a controlling terminal raised `OSError: [Errno 6] Device not configured: '/dev/tty'`.

| Dry-run step | What the operator saw | Root cause |
|---|---|---|
| `statusline` before `plan session` | exit 2, `WUWEI ? unmeasured`, stderr `day state is missing` | `cli/wuwei/commands/status.py:27-28` (`scan`) and `:123-124` (`snapshot`) raise `FileNotFoundError` when `state.json` is absent, although `state.read_state` (`cli/wuwei/state.py:113-124`) already returns fresh defaults for an absent file and fails closed only when a snapshot shows the state was lost. `run` (`:174-183`) turns that into exit 2. |
| `sweep-watch-am`, `sweep-obl-am` (no PR yet) | exit 2, `obligations UNREADABLE: no recorded PR state for today`, `unreadable: 1` | `cli/wuwei/obligations.py:175-193` (`_check_empty_day`) accepts a state write as proof only from event kinds starting with `state.` (line 184). Before `plan approve` every state write has another kind (`plan.session`, `watch: observation`, `discovery.intake`, `brief written`), each carrying `prs_seen: false` from `state._write_state` (`cli/wuwei/state.py:226`), so the check never passes. On a day with no state write at all, `evaluate` (`obligations.py:210-211`) raises `day state missing` first. |
| `nudges-am` after the sweeps | one nudge `{"source": "watch: sweep", "reason": "watch: sweep"}` | The `sweep obligations` event (`obligations.py:268`) carries only `reply_owed`, `visibility_owed`, `unreadable` and `integrity_owed`. `status.scan` (`status.py:81-88`) itemises a sweep event only when all seven count fields are present, so this event falls through to `classify` and the row reason defaults to the kind (`status.py:101-102`). |
| `dec-outcome-owner2`, `recover-notty` | exit 2, `wuwei decision: [Errno 6] Device not configured: '/dev/tty'`, and the same for `wuwei state` | `cli/wuwei/integrity.py:195-203` (`_host_confirm`) opens `/dev/tty` unguarded; the `OSError` reaches `__main__._main` (`cli/wuwei/__main__.py:69-71`). Callers: `commands/decision.py:87`, `commands/state.py:33`, `integrity.py:210` (`reconfirm`), `mcp.py:255`. A `/dev/tty` that opens but is not a terminal returns False, which reads as "declined" (exit 1). |
| `report`, `report-end` | `## Process metrics` is a Python dict repr (`{'fix_rounds_per_item': ...}`) | `cli/wuwei/report.py:70` writes `str(measured)`. |
| `check1` | `build check DIVIDE-1` exit 1 with no output | `cli/wuwei/commands/build.py:29-35` prints only a park reason; the failing checks' output is stored in the `continue` action's `feedback` (`build.py:350`) and never shown. |
| `report` metrics | `verdict_lint_rejections: 6`, three of them for one bad delta verdict | `cli/wuwei/metrics.py:428` counts every `verdict.rejected` event. One bad file is linted by `wuwei verdict lint`, the SubagentStop hook and `wuwei dispatch receive`, and each records an event (`cli/wuwei/verdict.py:146-162`, `record_rejection`), so one rejection counts three times. |
| `nudges-end` after `state recover` | nudge reason is the old parse error (`... state.json: Unterminated string ...; run wuwei state recover in a host terminal`) | `cli/wuwei/state.py:418` writes the pre-recovery error as the `state.recovered` event's `reason`, and `status.scan` shows the payload `reason`. |
| `sweep-watch-dead` | `discovery.follow_up_threads: measured: 2`, two candidates | `cli/wuwei/discovery.py:146-150` makes every unresolved thread a candidate, including the two the owner had already answered. `obligations._replies` (`obligations.py:103-110`) already treats a thread as answered when its latest human comment is the owner's. |
| `sessionstart-dead` | SessionStart context carries full draft records (text, inputs, final text) | `cli/wuwei/memory.py:84-97` (`session_payload`) dumps the whole day state, including `drafts`. |
| `rank` | `rank .wuwei/days/<date>/lead.json` exit 2 `candidates must be a list` | `cli/wuwei/commands/rank.py:39-40` passes the parsed JSON straight to `rank.rank`, which needs a list (`cli/wuwei/rank.py:40-41`); `plan template` output, the lead JSON and `proposal.json` are objects with a `candidates` list. `skills/wuwei-plan/SKILL.md:13` says only "Propose ranks with `wuwei rank`". |
| `pr-raise` | arguments found only through `--help` | `cli/wuwei/commands/pr.py:14-19` defines them; `docs/site/reference.md` never mentions `pr raise`. |

## User Scenarios & Testing

### User Story 1 - The morning before the first plan is quiet and truthful (Priority: P1)

Before `plan approve` the owner opens a session, glances at the status line, and the watch runs its sweeps. Nothing is owed, so nothing says unreadable.

**Independent Test**: a workspace on a fresh day; run `status --line`, `sweep watch`, `sweep obligations` and `nudges`.

**Acceptance Scenarios**:

1. **Given** a fresh day before `plan approve`, **When** `wuwei status --line` runs, **Then** it exits 0 and the line contains `no plan yet`.
2. **Given** a fresh day before `plan approve` with no state written yet, **When** `wuwei sweep watch` and then `wuwei sweep obligations` run, **Then** both exit 0 and their `watch: sweep` events carry `unreadable` 0 and `owed` 0.
3. **Given** a fresh day where only non-`state.` state writes exist (`plan session`, an earlier sweep), **When** both sweeps run, **Then** both exit 0 with nothing owed, and `wuwei nudges` prints `[]`.
4. **Given** `state.json` is missing while `state.snapshot.json` exists, **Then** `status --line` still exits 2 with `WUWEI ? unmeasured` and the obligations sweep still counts one unreadable (state loss handling unchanged).
5. **Given** an empty PR set while today's events show a PR was seen, **Then** the obligations sweep still exits 2 (contradiction check unchanged).

### User Story 2 - Owner actions without a terminal say so (Priority: P1)

The owner, or a script, runs a command that must ask the owner to type a digest from a place with no terminal.

**Acceptance Scenarios**:

1. **Given** no controlling terminal, **When** `wuwei decision outcome D-1 defer` runs for a routed decision, **Then** it exits 2 and stderr is one line, `wuwei decision: this is an owner action: run it in a host terminal`, with no errno text.
2. **Given** no controlling terminal, **When** `wuwei state recover` runs on a corrupt state, **Then** it exits 2 with the same sentence and nothing is restored.
3. **Given** no controlling terminal, **When** `wuwei integrity reconfirm` runs on a changed install, **Then** it exits 2 with the same sentence, not exit 1 "declined".
4. **Given** a real terminal, **Then** the confirmation prompt works as before (the existing pty test stays green).
5. `docs/site/concepts.md` and `docs/site/reference.md` list the host-terminal-only commands.

### User Story 3 - Operator records read correctly (Priority: P2)

**Acceptance Scenarios**:

1. **Given** a day with state, **When** `wuwei report` runs, **Then** the line after `## Process metrics` parses as JSON and equals the `wuwei metrics` output.
2. **Given** a build awaiting checks whose fast check fails with output, **When** `wuwei build check ITEM` runs, **Then** it exits 1 and prints the failing check's output (the same feedback the builder receives).
3. **Given** one bad verdict file in one round linted by `verdict lint`, the SubagentStop hook and `dispatch receive`, **Then** `verdict_lint_rejections` is 1. **Given** the seat then rewrites that file with different bad content, **Then** it is 2.
4. **Given** `state recover` restored a corrupt state, **Then** the `state.recovered` nudge reason is `state recovered from snapshot <digest>` and does not contain the old parse error.
5. **Given** an owned PR with two unresolved review threads, one whose latest human comment is the owner's and one awaiting the owner, **When** discovery runs, **Then** only the unanswered thread is a `follow_up_threads` candidate.
6. **Given** today's state holds drafts, **When** SessionStart builds its context, **Then** the state text lists each draft id with its destination only; no draft text or inputs appear.

### User Story 4 - The documented rank input ranks (Priority: P2)

**Acceptance Scenarios**:

1. **Given** `plan template | plan propose -`, **When** `wuwei rank .wuwei/days/<date>/proposal.json` runs, **Then** it exits 0 and prints the ranked candidates.
2. **Given** `plan template | rank -`, **Then** it exits 0. A candidate list (`rank template | rank -`) still works.
3. **Given** a JSON object without a `candidates` list, **Then** `rank` exits 2 with `candidates must be a list`.
4. `docs/site/reference.md` documents the `rank` input and the `pr raise` arguments; `skills/wuwei-plan/SKILL.md` names the file to rank.

### Edge Cases

- A `note` event (the only kind `wuwei event` lets a seat write) carrying `prs_seen: false` does not count as a recorded state write.
- `state.json` present but `events.jsonl` missing or corrupt stays unreadable (existing `test_empty_pr_set_requires_readable_history`).
- A `/dev/tty` that opens but is not a terminal gives the same one-sentence exit 2 as a missing one.
- With no single owner login configured, answered cannot be decided, so every unresolved thread stays a candidate (today's behaviour).
- A rejection of a file that cannot be read has no content digest; such rejections dedupe per file name.

## Requirements

### Functional Requirements

- **FR-001**: `status` MUST read an absent `state.json` through `state.read_state` (fresh defaults; fail closed when a snapshot exists) instead of refusing, in both `scan` and `snapshot`. `status --line` MUST start with `WUWEI no plan yet` while `gate_approved` is false and still show pages, nudges and watch health.
- **FR-002**: The obligations empty-day check MUST accept `prs_seen` from any event kind except the free `note` kind, MUST NOT require a recorded state write when `state.json` does not exist, and MUST treat a missing `events.jsonl` as empty only when `state.json` does not exist either. `evaluate` MUST NOT refuse an absent `state.json` that `read_state` accepts.
- **FR-003**: `status.scan` MUST itemise a `watch: sweep` event whose count fields are absent by treating each absent count as 0, so a well-formed sweep event never yields the bare reason `watch: sweep`.
- **FR-004**: `integrity._host_confirm` MUST raise `OSError('this is an owner action: run it in a host terminal')` when `/dev/tty` cannot be opened or is not a terminal. Callers keep their existing error paths.
- **FR-005**: `report` MUST write the process metrics as JSON, serialised the same way as `wuwei metrics`.
- **FR-006**: `build check` MUST print the `continue` action's feedback to stderr when it exits 1 with a `continue` action.
- **FR-007**: `verdict.record_rejection` MUST add the rejected file's SHA-256 (null when unreadable) to the `verdict.rejected` payload, and `verdict_lint_rejections` MUST count distinct `(file, sha256)` pairs.
- **FR-008**: The `state.recovered` event MUST carry `reason: state recovered from snapshot <first 12 hex>` and keep the pre-recovery error under `error`.
- **FR-009**: Discovery MUST skip an unresolved review thread whose latest human comment is by the owner login, through one shared `obligations.answered(thread, me)` that `_replies` also uses.
- **FR-010**: `memory.session_payload` MUST replace `drafts` in the state text with a mapping of draft id to destination.
- **FR-011**: `wuwei rank FILE` MUST rank `data['candidates']` when the input is a JSON object.
- **FR-012**: Docs: `concepts.md` and `reference.md` name the host-terminal-only commands; `reference.md` documents `status --line` before the plan, the `rank` input and the `pr raise` arguments; the plan skill names the file to rank.

### Key Entities

- `verdict.rejected` event payload: `file`, `reasons`, new `sha256` (hex or null).
- `state.recovered` event payload: `snapshot`, `reason` (now the recovery message), new `error` (the pre-recovery reason).
- `status --json` snapshot: new boolean `gate_approved`.

## Success Criteria

- **SC-001**: On a fresh day, `status --line`, `sweep watch`, `sweep obligations` and `nudges` report nothing owed with exit 0.
- **SC-002**: No owner action that asks for a typed confirmation prints an errno; each prints one sentence naming the host terminal and exits 2.
- **SC-003**: `verdict_lint_rejections` equals the number of distinct bad verdict file versions.
- **SC-004**: The documented `rank` input exits 0.
- **SC-005**: The full suite passes; no guard refuses less than before.

## Assumptions

- "No plan yet" means the morning gate is not approved (`gate_approved` false), not merely that `state.json` is absent: a sweep or `plan session` writes state before the plan. The line keeps pages, nudges and watch health so a page before the plan is never hidden.
- A missing `state.json` with no snapshot is a fresh day, not lost state. Losing the state, its snapshot and the events together is owner-level tampering outside the cooperative threat model (spec 9.1).
- `drafts approve` asks nothing on a terminal, and `--edit` runs `$EDITOR`, which may be a GUI editor, so no terminal check is added to it; the issue's point is met by listing it as host-terminal only in the docs. `mcp decide` shares `_host_confirm` and gets the same exception, but its `_failure` message (exception type only) is left unchanged as out of scope.
- A verdict "round" is one version of the file's content: the same bad content linted several times counts once. A seat that rewrites byte-identical bad content in a later round is also counted once.
- Itemising the obligations sweep event means an `integrity_owed` from `sweep obligations` now shows as an integrity page, matching `sweep watch`.
- The build-check output is the existing builder feedback text, not a new format, so the builder prompt and the stuck-loop signature are unchanged.
- `status --json` gains a `gate_approved` key; its readers (SwiftBar template, cockpit) read keys by name.
