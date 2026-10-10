# Feature Specification: under autonomous mode nudges are off by default and a nudge is only ever a pointer to a runnable next action

**Feature Branch**: `742-nudges-off`
**Created**: 2026-10-10
**Status**: Draft
**Input**: GitHub issue #742 (owner, 2026-10-10): 255 nudges nobody reads on one study day.
The owner's bar is that the framework guides the model seamlessly and that hooks and gates
exist to prevent issues, not to create them. Deliver `nudges.mode = off|next|all`, `off` the
default under `autonomy.mode = autonomous` and `next` under supervised; `next` shows a nudge
only when it names a runnable command the loop would otherwise miss; the status line counts
nudges only when the mode is on; the interview's Autonomous answer sets `off`; `init
--upgrade` tells a workspace without the key what it now gets.

## Root cause (read on main at d3b7066, reproduced read-only)

Reproduction: the owner's study workspace, day 2026-10-10, read with `status.attention` and
`signal.classify` from this worktree (nothing written). 9702 events; 393 classify as `nudge`;
`attention` returns 357 open rows at 23:00, 356 of them nudges and 1 page. By source:
`watch: read-failed` 173, `merge.unmeasured` 66, `draft.created` 53, `retro.gap` 37,
`decision.rejected` 7, `tracker.call` 7, `spec.warned` 6, `negotiation.loop` 2, one each of
`config.newer_template`, `calibration.drift`, `steward.due`, `decision.pending` and
`session.planner_stale`. The day before: 84 rows, 83 nudges. The status line showed the count
all day. Not one row names a command the loop (`wuwei next`) did not already offer.

Three facts on main make this happen:

1. `signal.classify` (`cli/wuwei/signal.py:101`) returns `nudge` for every kind it does not
   list. Diagnostics the watch and the merge reconcile write on each failed read
   (`watch: read-failed`, `cli/wuwei/watch.py:470` and `:489`; `merge.unmeasured`,
   `cli/wuwei/merge.py:719`) and records such as `retro.gap`, `spec.warned` and
   `decision.rejected` fall through to that line. This is the design's rule (5.9: an event the
   classifier cannot read is a nudge) and it stays.
2. `status.scan` keys every such event by its line number (`cli/wuwei/commands/status.py:163`,
   `key = (kind, number)`), so each event line is its own open row for the rest of the day.
3. Every owner surface shows every row, with no setting between the classification and the
   owner: `snapshot` counts them (`status.py:278`) and `_groups` always renders `nudges N`
   (`status.py:381`); `wuwei nudges` lists `attention` unfiltered
   (`cli/wuwei/commands/nudges.py:46`); the board's Attention table lists it
   (`cli/wuwei/commands/board.py:161`); doctor counts it (`cli/wuwei/commands/doctor.py:618`).
   The config schema (`cli/wuwei/workspace.py:154`) has `autonomy.mode` but no nudge setting,
   and the interview's Autonomous answer (`cli/wuwei/interview.py:118`) sets five keys, none
   about nudges.

The fix is a filter at the surfaces, not a change to classification or to what producers
write: the events are records that `wuwei next`, the report, metrics and doctor read.

## Clarifications

### Session 2026-10-10

Answered with the recommendation (AGENTS.md: no clarifying questions).

- Q: What does "no nudge events are written" mean, given a nudge is a classification and not
  an event kind? A: No nudge reaches any owner or model surface: the status line, `status
  --json`, `wuwei nudges`, the board's Attention table and doctor's count. Producers keep
  writing their events unchanged; `events.jsonl` is a record, and `next`, `report`, metrics and
  doctor read kinds such as `steward.due` and `spec.warned`.
- Q: Where does the mode apply? A: One helper in `status.py`, `surfaced`, called by the four
  surfaces above. `status.scan` and `status.attention` stay the raw classification: session
  start's phone-answer lines (`cli/wuwei/guards/lifecycle.py:109`), `next.step`'s health
  check and doctor's page rows read them unchanged.
- Q: What is the default? A: The schema default is `""`, which follows `autonomy.mode`: `off`
  under `autonomous`, `next` under `supervised` (the pattern of `merge.default_tier = ""`
  following the posture). An explicit `off`, `next` or `all` wins.
- Q: What if the day has no readable `config.toml`? A: `all`. An absent setting file never
  hides attention (fail toward showing); an invalid config already makes status unmeasured.
- Q: Do pages change? A: No. Every mode shows every page and the line keeps `pages N`.
- Q: Which nudges does `next` show? A: Exactly three subjects, one row each, kept or derived
  so the row exists while the subject holds and is gone when it changes:
  - a card answered but unrecorded: the existing `decision.answered` row (one per decision
    id; its reason names `wuwei decide D-n <option>`);
  - a ready fix round: an item in phase `fix` with nothing in flight for it
    (`state.in_flight`: no running seat, no running fast check), source `round.ready`, reason
    `<item> fix round is ready: run wuwei build next <item>`; gone once the round starts;
  - a merged PR with a pending close: the morning gate approved, every approved item merged,
    parked or escalated, at least one merged, nothing in flight and the close not requested,
    source `close.ready`, reason `<n> merged and nothing left to build: run wuwei close`.
  Nothing else: never observe-mode information (`guard.would_refuse`, `traces.unmatched`),
  never a diagnostic (`watch: read-failed`, `merge.unmeasured`), never a reminder of something
  the loop already asks (`decision.pending`, `steward.due`).
- Q: What does the status line show under `off`? A: No nudge token: `pages N`, then the
  posture and pace as today. `status --json` keeps `nudges` as an integer (0 under `off`, so
  the SwiftBar plugin's contract holds) and adds `nudges_mode`.
- Q: How does the owner see everything when they want to? A: `wuwei nudges --all` lists every
  open cause as today, whatever the mode. Doctor's nudge row names the mode and points to
  `--all`; its traces row points to `wuwei nudges --all`.
- Q: What does `init --upgrade` do for a workspace without the key? A: It writes nothing (the
  loader applies the `""` default) and prints one notice, as it does for unanswered setup
  questions (`cli/wuwei/commands/init.py:440`): `nudges.mode unset, so nudges follow
  autonomy.mode: <mode>; set nudges.mode = "next" or "all" in config.toml to see more`. It
  prints under `--dry-run` too and counts as no change.
- Q: The interview? A: The Autonomous answer sets `nudges.mode` to `off` and Supervised to
  `next` through the `""` default, which follows the `autonomy.mode` the answer writes. The
  answer does not write `nudges.mode`: a question counts as answered by config only when every
  key it writes is present, so a sixth key would ask the autonomy question again on every
  configured workspace without it (`tests/test_interview.py`
  `test_every_autonomy_key_set_answers_the_autonomy_question`), and a written `off` would stay
  after the owner moves to supervised by hand. Changed during implementation.

## User Scenarios and Testing

### User Story 1 - An autonomous day shows no nudges (Priority: P1)

**Acceptance Scenarios**:

1. **Given** `autonomy.mode = autonomous` (the default) and no `nudges.mode`, and a day whose
   events classify as nudges (`watch: read-failed`, `merge.unmeasured`, `draft.created`) plus
   one page, **When** `status --line`, `status --json` and `wuwei nudges` run, **Then** the
   line has `pages 1` and no `nudges` token, `--json` has `nudges` 0 and `nudges_mode` `off`,
   and `wuwei nudges` (text and `--json`) lists only the page.
2. **Given** the same day, **When** `wuwei nudges --all --json` runs, **Then** it lists every
   row `status.attention` returns.
3. **Given** the same day, **Then** the board's Attention table lists only the page, and
   doctor's nudge row names `nudges.mode off` and `wuwei nudges --all`.

### User Story 2 - `next` points at a runnable action, once per subject (Priority: P1)

**Acceptance Scenarios**:

1. **Given** `nudges.mode = next`, the gate approved and an approved item in phase `fix` with
   nothing in flight, **When** status and nudges run (twice), **Then** exactly one nudge,
   source `round.ready`, naming `wuwei build next <item>`; the line shows `nudges 1`.
2. **Given** the same, **When** a builder seat for the item is running, **Then** no nudge.
3. **Given** `nudges.mode = next` and a decision answered from the phone but not recorded,
   **Then** one `decision.answered` nudge naming `wuwei decide`.
4. **Given** `nudges.mode = next`, every approved item merged or parked with one merged,
   nothing running and no close requested, **Then** one `close.ready` nudge naming
   `wuwei close`; once `close_requested` is set, none.
5. **Given** `nudges.mode = next` and events `guard.would_refuse` (posture guarded),
   `watch: read-failed`, `steward.due` and a pending (unanswered) decision, **Then** no nudge.

### User Story 3 - The mode is set by the setup answer and explained by upgrade (Priority: P2)

**Acceptance Scenarios**:

1. **Given** `autonomy.mode = supervised` and no `nudges.mode`, **Then** the effective mode is
   `next`; **given** `nudges.mode = all`, **Then** the status line, `--json` count and nudge
   list match main's output for the same day.
2. **Given** the interview, **When** the owner answers Autonomous, **Then** the effective nudge
   mode is `off`; Supervised gives `next`; neither answer writes `nudges.mode`.
3. **Given** a workspace whose `config.toml` has no `nudges.mode`, **When** `init --upgrade`
   (or `--upgrade --dry-run`) runs, **Then** it prints the notice naming the effective mode and
   writes no `nudges` key; with the key set, no notice.
4. **Given** `nudges.mode = "sometimes"`, **Then** config load refuses it as an invalid value.

### Edge Cases

- A day with no `config.toml` keeps today's surfaces (`all`).
- No `state.json` yet: `wuwei nudges` prints its empty-day line as today, in every mode.
- An item in `fix` whose fast check is running (a `checks` row in `state.in_flight`) is a
  running round: no `round.ready`.
- `pages N` and doctor's page rows are identical in every mode.

## Requirements

- **FR-001**: `workspace.SCHEMA` gains `nudges.mode` (`""`, `off`, `next`, `all`; default
  `""`); `workspace.nudge_mode(config)` returns the effective mode (`""` follows
  `autonomy.mode`: `off` when autonomous, `next` when supervised).
- **FR-002**: `status.surfaced(directory, rows, data=None, config=None)` returns
  `(mode, rows)`: every non-nudge row always; under `all` every row as given; under `next` the
  `decision.answered` rows plus the derived `round.ready` and `close.ready` rows; under `off`
  no nudge row. No `config.toml` means `all`.
- **FR-003**: `status.snapshot` counts `nudges` from `surfaced` and carries `nudges_mode`;
  `_groups` omits the `nudges N` token when `nudges_mode` is `off`.
- **FR-004**: `wuwei nudges` lists `surfaced` rows (text and `--json`); `--all` lists every
  `attention` row as today.
- **FR-005**: The board's Attention table lists `surfaced` rows; doctor's nudge row reports the
  surfaced count and the mode and points to `wuwei nudges --all`; its traces row points to
  `wuwei nudges --all`.
- **FR-006**: The interview's Autonomous answer gives the effective mode `off` and Supervised
  `next`, through the `""` default; the answer's effects do not name `nudges.mode`.
- **FR-007**: `init --upgrade` prints the nudges notice when `nudges.mode` is absent, writes
  nothing for it and counts no change.
- **FR-008**: The template carries a commented `# [nudges]` block; `docs/site/configuration.md`
  documents `nudges.mode` and the autonomy answer's new key; `docs/site/reference.md`'s status
  line paragraph says the nudge token follows `nudges.mode`.

## Success Criteria

- **SC-001**: For the reproduction day's event mix under the default (autonomous) config, the
  status line carries no nudge count and `wuwei nudges` lists only pages.
- **SC-002**: Under `next`, each of the three subjects yields exactly one nudge while it holds
  and none after it changes; no other source yields a nudge.
- **SC-003**: `nudges.mode = all` gives main's status line, `--json` count and nudge list.
- **SC-004**: The full suite passes; `status --line` adds no file read (the config and state
  it already loads are reused), so its 200 ms budget holds.

## Assumptions

- No `_pipeline/notes/742-full.md` exists; the issue, the code on main and the read-only
  reproduction above are the inputs.
- "No nudge events are written" is read as no nudge reaching a surface (see Clarifications);
  producers and `events.jsonl` are unchanged because other commands read those records.
- "A merged PR with a pending close" is read as the day close `wuwei next` offers once every
  approved item is terminal (the close row of `cli/wuwei/commands/next.py`). A per-item tracker
  close is not a nudge subject; `tracker.strict_close` already holds the close.
- "A ready round" is a fix round: phase `fix`, nothing in flight for the item. The delta review
  is started by `dispatch next` inside the same round and is not a separate subject.
- The DM push of `pr.changed` and `negotiation.loop` (`listen.notify`) is governed by
  `outbound.owner_channel` and `owner.verbosity.nudges`, not by `nudges.mode`; unchanged here.
- `heartbeat.py` is named in the issue's references but needs no change: its probes write
  `heartbeat: clock` (silent) and its failure path is a page.
- Design spec 5.9 (amended only by its owner) gains a sentence on `nudges.mode` at the owner's
  next amendment; this feature does not edit the design spec. The change is not a guard or a
  decision rule, so no 9.2 invariant row is owed.
- Tests whose subject is the raw classification and that read it through `wuwei nudges`,
  `snapshot` or the status line under a default (autonomous) config switch to `--all`,
  `status.attention` or `nudges.mode = "all"` in their config; their assertions do not weaken.

## Deferred

- Teaching `signal.classify` the diagnostic kinds (`watch: read-failed`, `merge.unmeasured`)
  so `all` is quieter too: a classification change for the owner's 5.9 amendment, not needed
  for the default to be quiet.
