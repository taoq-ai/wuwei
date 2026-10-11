# Implementation Plan: delete nudges; warnings stay in the event log

**Branch**: `801-nudges-out` | **Date**: 2026-10-11 | **Spec**: [spec.md](spec.md)

## Summary

Delete the nudge list and everything that reads, filters, ages or counts it; keep every event
and the one view (`status.scan`) the remaining counts read. The classifier tier `nudge` is
renamed `warn`, so no module writes a nudge while the trace-gap, untraced-subagent,
phone-answer and changed-PR counts keep working. Four files go (one command module, two test
modules, one fixture); 60 change (18 code, 3 templates, 30 tests and fixtures, 9 docs pages),
plus up to 4 more if part 3 has not yet removed them. Almost every change deletes lines.

Line numbers are at main `bfbf6a3`; verify each against the rebased tree (parts 1 to 3 merge
first and move some of them).

## Technical Context

Stdlib-only Python 3.11+, pytest for tests. No new module, event kind, state key or config key.
`status --line` does less work (one config read and three state-derived blocks go from `scan`).

## Constitution Check

- I stdlib only: nothing imported.
- II exits: no exit changes. The one strictness edge, the `pr_actions` episode tier check,
  keeps refusing unknown tiers and accepts the legacy `nudge` so today's state is not refused
  after an upgrade (data-loss guard, not loosening).
- III one behaviour, one function: `scan` stays the one view; doctor and status keep reading it.
- IV test first: `tasks.md` changes each behaviour test before its code; pure deletions delete
  their tests with the code and rerun the touched files.
- V ponytail: deletion plus a word rename; no replacement surface.
- VII and the design-spec rule: no guard or decision rule changes. #789 is the owner's
  instruction, so the design spec is amended to match: 5.9 and every passage that used the
  `nudge` tier, each marked "(owner, 2026-10-10, #789)" (spec, Assumptions).

## Units removed and why (rule of the pass)

| Unit | (a) or (b) | Where its job is now |
|---|---|---|
| `wuwei nudges` command (`commands/nudges.py`, `ACTIONS`, `line`) | (a) a list the model reads to choose work | pages: status line `pages N`, one doctor `fail` row each with its reason |
| `nudges.mode`, `status.surfaced`, `workspace.nudge_mode`, `SCHEMA['nudges']['mode']` | (a) | none needed |
| `round.ready`, `close.ready` rows (mode `next`) | (a) duplicated the loop | `wuwei next` (an item in phase `fix` gets its build action; close rows in `next.py`) |
| `status._tidy`, `nudges.ttl_hours`, `nudges.max_open`, `nudges.dropped` | (a) list hygiene | none needed |
| `nudges N` status token, `status --json` `nudges`/`nudges_mode` | (a) | none |
| doctor `nudges` row | (a) | none |
| `decision.pending` row in `scan` | (a) | `wuwei next` decision row; `status --json` `decisions` |
| `decision.cruise` row in `scan` | (a) | `wuwei decision show D-n --widget` (cruise itself goes in part 9) |
| `session.planner_stale` row in `scan` | (b) stale planner | already in the heartbeat `planner` probe (pages via `heartbeat: clock`) and the doctor `planner` row |
| `guards.shadow` row in `scan` | (a) | doctor `posture` warn row, same text |
| `owner.verbosity.nudges` surface | (a) | listener uses `owner.verbosity.dm` |
| `init --upgrade` `nudges.mode unset` notice | (a) | none |
| `nudge` classifier tier | renamed `warn` | still in the event log; read only by counts |

No (b) unit loses its check: the stale-planner check already lives in the heartbeat and doctor.

## Files to delete (4)

- `cli/wuwei/commands/nudges.py`
- `tests/test_nudges_mode.py` (every case covers `nudges.mode`, `surfaced`, the command or the
  autonomy-to-mode mapping, all deleted)
- `tests/test_nudge_hygiene.py`, after moving its four `scan` cases (below) into
  `tests/test_signal_status.py`; the rest cover `_tidy`, the command, the config keys or the
  docs row, all deleted
- `tests/fixtures/swiftbar/nudge.json`

## Files to edit: code

### `cli/wuwei/signal.py`

- Every `'nudge'` literal becomes `'warn'` (19 at lines 38 to 101, the final return
  included); the `pr.action` branch reads
  `tier if tier in ('silent', 'warn', 'page') else 'warn'`.
- Docstrings: module "Pure attention classification"; `classify` "malformed events demand a
  warning".

### `cli/wuwei/commands/status.py`

- Delete `SHADOW_NUDGE` (moves to doctor).
- `attention` docstring: "Current page and warning causes from the day's event stream."
- `scan`: drop the `config` keyword and its load (lines 249-257, the `guards.shadow` block);
  `watch: sweep` field levels `'nudge'` become `'warn'` (137-143); `watch: health` code 2 is
  `'warn'` (200); the decision-routes loop (220-229) keeps only the `decision.answered` row,
  written as `{'tier': 'warn', 'source': 'decision.answered', 'lane': 'Decisions', 'reason': ...}`
  when `replied.get(identifier)` has an option, and no `decision.pending` row; delete the
  `decision.cruise` loop (230-237) and the `session.planner_stale` block (238-248); the final
  sort drops the `decision.cruise` term and keeps `pr.changed` first. Remove imports that become
  unused (`date`).
- Delete `_tidy` (262-281) and `surfaced` (284-309).
- `snapshot`: `result` loses `'nudges': 0`; drop `result['nudges_mode'], shown = surfaced(...)`
  and `result['nudges'] = ...`; call `scan(directory, classified_state)` without `config`.
  `config` is still loaded for `posture`, `restart`, cruise and checks.
- `_groups`: `attention = [f'pages {data["pages"]}']`.

### `cli/wuwei/commands/nudges.py`: deleted (above).

### `cli/wuwei/workspace.py`

- `SURFACES = ("decisions", "digest", "dm", "report")` (38).
- Delete `SCHEMA["nudges"]` (159-160).
- Delete `nudge_mode` (441-443).

### `cli/wuwei/commands/init.py`

- Delete the `nudges.mode unset` notice (451-453); `loaded` and the interview count stay.

### `cli/wuwei/commands/doctor.py`

- `_calibration`: replace `from wuwei.commands.status import SHADOW_NUDGE` (439) with a
  module constant `SHADOW` holding the same text; use it at 480.
- `_day`: page row fix `'wuwei nudges'` becomes `'wuwei next'` (647); delete the `surfaced`
  call and the `nudges` row (648-651); `traces` fix becomes
  `'read the traces.gap events in today\'s .wuwei/days/<date>/events.jsonl, then run wuwei doctor'`
  (654).

### `cli/wuwei/pr_actions.py`

- Overdue tier `'nudge'` becomes `'warn'` (217).
- Episode check (176): `episode.get('tier', 'silent') not in ('silent', 'warn', 'page', 'nudge')`
  with a comment `# nudge: an episode written before #801`.

### `cli/wuwei/integrity.py`

- `workspace_check` non-page severity `'nudge'` becomes `'warn'` (400).

### `cli/wuwei/listen.py`

- `workspace.verbosity(config, 'nudges')` becomes `workspace.verbosity(config, 'dm')` (48).

### `cli/wuwei/commands/board.py`

- Tool description: "pending decisions, pages, the status line" (19).
- Attention table rows: `[... for r in status.attention(directory) if r['tier'] == 'page']`
  (162-163).

### `cli/wuwei/commands/dashboard.py`

- No code change (it passes `status_snapshot` and the classifier tiers through).

### Messages naming `bin/wuwei nudges`

- `commands/decision.py:144`: `f'No {args.id} today; bin/wuwei status --json lists open decisions.'`
- `commands/why.py:294`: `...; run bin/wuwei status --json for open decisions`
- `control_plane.py:88`: `...; run bin/wuwei status --json for the open decisions`
- `obligations.py:315`: `'no human obligation with that surface and ID; reread the PR on the code host for the comment id, then retry'`
- `obligations.py:363`: `'thread is resolved, missing or already answered; reread the PR threads on the code host, then retry'`

### Comments and help text

- `heartbeat.py:118`: "the none adapter would append a warning per call".
- `watch.py:557`: "...reads the rest in events.jsonl".
- `guards/traces.py:9`: "...defers the advisory steward.due event until a call fits".
- `budget_classes.py:94`: "...a fast burn writes one cruise.burn event a day".
- `commands/steward.py:15`: "a steward.due event is not a note".

### Only if part 3 has not removed them

- `commands/__init__.py`: drop `'nudges'` from WRITES (both rows, 19 and 24).
- `__main__.py`: drop `nudges` from the Daily group (28).
- `guide.py:82-84`: "a `negotiation.loop` event is a report"; "each digest and report".

### Templates

- `templates/workspace/config.toml`: line 66 "how much decisions, the digest, the DM and the
  report say to you"; line 67 "Per surface: decisions, digest, dm or report"; line 238 "the
  digest and day report"; delete the `# [nudges]` block (278-281); line 295
  "burn rate that writes a cruise.burn event"; line 340 "Days in observe before wuwei doctor
  asks you to switch to guarded".
- `templates/swiftbar/wuwei.1m.sh`: read `pages` only; validate it; `color = "red" if pages
  else "green"`; print `Pages: {pages}`.
- `templates/dashboard.html:178`: `${status.pages ?? "unmeasured"} page(s)`.

## Files to edit: tests

Edit each with the code it covers; convert `main(['nudges', '--json'])` reads to
`status.attention(workspace.day_dir(root))` (the raw view, as `--all` gave) and drop any
`[nudges] mode = "all"` config line.

- `tests/test_signal_status.py`: `NUDGE` table and `test_nudge_triggers` become `WARN` /
  `test_warn_triggers` with `'warn'`; every expected `'nudge'` tier (escalation, tracker,
  emitted-kinds table, drafts, negotiation loop, `decision.waited`, telemetry) becomes `'warn'`;
  status line expectations drop ` · nudges N` (`pages 0 · nudges 0` becomes `pages 0`); the
  status json key set drops `nudges`; delete `test_routed_decision_nudges_until_answered`,
  `test_issue_acceptance_nudges_print_lines`, `test_nudge_line_actions`, `row_of`,
  `test_nudge_page_and_nudge_stay_apart`; `test_issue_acceptance_a_phone_answer_shows_on_the_host`
  and `..._four_phone_answers_...` read `status.attention` and keep the `decision.answered`
  rows with tier `warn` (no `decision.pending` row); `test_status_json_shows_recorded_tiers`
  reads tiers from `attention`; `test_pr_changed_nudge_is_first_...` is renamed
  `test_pr_changed_is_first_...` and drops `'nudges 2' in line`; `test_issue_acceptance_adapter_none_is_silent`
  asserts the attention rows are empty instead of `nudges 0`. Add the four moved cases:
  `test_repeats_fold_into_one_row_per_subject`, `test_a_later_silent_event_clears_its_subject`,
  `test_unreadable_lists_and_pages`, `test_counts_that_read_rows_sum_count` (with their
  `at`, `day` (renamed so it does not clash), `read_failed`, `tracker` helpers, config text `''`).
- `tests/test_quiet_sweeps.py`: drop the `[nudges]` config; `test_nudges_show_current_conditions`
  becomes `test_attention_shows_current_conditions` without the `snapshot()['nudges']` line;
  the pr.action fixture tier `'nudge'` becomes `'warn'`; `test_three_sweep_obligations_make_three_nudges`
  asserts `len(attention(day)) == 3` (renamed `..._three_warnings`); the no-day-state case
  asserts `attention` raises no error and is empty, or is deleted if it only covered the
  command; status full expectations `pages N · nudges 0` become `pages N`;
  `test_future_clock_nudges_unmeasured_watch` expects tier `'warn'`.
- `tests/test_sessions.py`: drop the `[nudges]` config; delete `nudges()` helper and
  `test_stale_planner_nudge_names_take_over`; the case at 283-288 compares `attention` rows.
- `tests/test_shadow.py`: `test_status_shows_posture_and_nudges_once` becomes
  `test_status_shows_posture` (parameters without `nudged`; assert there is no `guards.shadow`
  row); drop the `[nudges]` config.
- `tests/test_posture.py`: tier `'nudge'` becomes `'warn'`; rename
  `test_warnings_outside_observe_nudge_once_per_guard` to `..._warn_once_per_guard`.
- `tests/test_traces_seats_only.py`, `tests/test_mcp.py`, `tests/test_integrity.py`,
  `tests/test_listen.py:521`: `'nudge'` becomes `'warn'`.
- `tests/test_pr_ownership.py`: parametrize `'nudge'` becomes `'warn'`; `signals.count('warn')`.
- `tests/test_pr_actions.py`: `test_pr_act_decision_is_routed_and_nudges` becomes
  `test_pr_act_decision_is_routed`; drop the `[nudges]` config, `pending()`, and the status-line
  assertion (they covered the deleted `decision.pending` row).
- `tests/test_cruise.py`: delete `test_nudges_list_an_open_undo_window_first`.
- `tests/test_budget_classes.py`: `test_a_fast_burn_writes_one_nudge_a_day` becomes
  `test_a_fast_burn_writes_one_event_a_day`: assert one `cruise.burn` event in today's
  `events.jsonl` whose reason starts `defer burns its error budget`, instead of the `nudges` line.
- `tests/test_listen.py`: 501 reads `attention`; rename `..._wake_and_nudges_in_one_tick` to
  `..._wake_in_one_tick`; `test_full_nudges_name_the_changed_fields` becomes
  `test_full_dm_names_the_changed_fields` with `[owner.verbosity]\ndm = "full"`.
- `tests/test_remote.py:887`, `tests/test_watch.py:610`, `tests/test_operator_records.py`
  (21 config, 60 line `pages 0 · nudges 0` becomes `pages 0`, 67),
  `tests/test_records_after_dryrun4.py` (rename to `test_steward_run_clears_earlier_due_warning`;
  read `attention`; drop the `status --json` `nudges` assertion): read `attention`.
- `tests/test_e2e_day.py:68-71`: read the `watch: health` page from
  `status.attention(day.directory)` instead of `nudges --json`; the asserts stay.
- `tests/test_doctor.py`: day row names drop `'nudges'` (638); `page['fix'] == W('next')`; drop
  the `nudges` row assertion (674-675).
- `tests/test_workspace.py`: drop `config.pop('nudges')` (215) and the `nudges` key from the
  verbosity dicts (223, 412); delete `test_upgrade_names_the_nudge_mode_it_applies` (848-860);
  drop `'nudges.mode unset'` from the two prefix filters (1321, 1338).
- `tests/test_reasons.py`: `PERSON_MODULES` drops `'commands/nudges.py'`; 265 expects the new
  decision show message.
- `tests/test_why.py:371`: expects the new message.
- `tests/test_board_mcp.py:102-104`: the Attention row count is
  `len([r for r in status.attention(day) if r['tier'] == 'page']) + 1`.
- `tests/test_dashboard.py`: status fixture `{'pages': 1}`; assert `'1 page(s)'` and no `nudges`.
- `tests/test_swiftbar.py`: drop the `nudge.json` row and the `Nudges:` assertion;
  `tests/fixtures/swiftbar/{clean,page,invalid}.json` drop `"nudges"` (invalid keeps its
  string `pages`).
- `tests/test_hooks.py:374`, `tests/test_outward.py:1230`: comment wording only.
- `tests/test_docs.py`: if the glossary tuple still exists, drop `('Nudge', r'nudges?')` with
  the concepts.md entry.

## Files to edit: docs (issue acceptance)

Rule: a nudge sentence about a deleted surface is deleted; one about an event that still fires
says "a warning in the event log" (or names the event kind); `bin/wuwei nudges` becomes
`bin/wuwei doctor` where it listed pages, otherwise the sentence goes; `pages 0 · nudges 0`
becomes `pages 0`.

- `docs/site/reference.md`: delete the `bin/wuwei nudges` command row (51, forced by
  `test_reference_lists_every_cli_command`); 114, 181, 184, 188, 241, 308, 408.
- `docs/site/configuration.md`: 17 (`[nudges]` out of the section table), 47, 48, 50, 81
  (delete the `owner.verbosity.nudges` row), 164, 182, 189, 196-198 (delete), 210, 371, 379,
  445, 559, 616-640 (the nudges listing paragraph goes; pages are listed by doctor), 713, 715.
- `docs/site/concepts.md`: delete the `### Nudge` glossary entry (77-80); 303, 422, 441, 451, 489.
- `docs/site/daily.md`: 192, 297, 390, 404, 435, 449, 463-464, 537.
- `docs/site/remote.md`: 225, 270, 385.
- `docs/site/security.md`: 78, 79.
- `docs/site/agent.md`: 72 ("each digest and report"); 26 only if the guide block is still there.
- `docs/site/integrity.md:38`, `docs/site/recovery.md:29`.

Also edited: `docs/specs/2026-09-24-wuwei-design.md` (5.9 tier renamed `warn` with an amendment
note; lines that used the tier), under the owner's #789 instruction. Not edited: `CHANGELOG.md`
and `specs/*` (history).

## Verification

- `grep -rn nudge cli/wuwei` shows only the `pr_actions.py` legacy read;
  `grep -rli nudge charters skills docs/site README.md templates hooks agents` is empty.
- Run every touched test file (list in tasks.md T020) with `python -m pytest -q`. No full
  suite locally; CI is the gate.

## Risks for the builder

- Rebase onto parts 1 to 3 first; several lines above move or vanish (`guide.py`, GROUPS,
  READ_ONLY/WRITES, the docs glossary test, the agent guide block).
- If part 5 or 7 merged first, skip the board, dashboard, SwiftBar, listener and control-plane
  edits (their files are gone).
- `test_signal_status.py` carries most of the churn; change expectations only where the code
  changed (tier word, dropped token, deleted rows), never relax an unrelated assertion.
- The `pr_actions` legacy `nudge` acceptance is the one intended remaining mention; do not
  drop it.
