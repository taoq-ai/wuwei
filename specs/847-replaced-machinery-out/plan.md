# Implementation Plan: delete what the derived next replaced

**Branch**: `b9-cleanup` | **Date**: 2026-10-12 | **Spec**: [spec.md](spec.md)

Line numbers are at 71d3f06b (main plus batch 8). The batch 8 review fix round is made in
parallel; locate code by function name where it moves (see "Batch 8 fix round").

## Summary

Delete the background watch, the heartbeat, the headless shepherd, the session registry, the
obligations sweep and close gate, nine commands, the Stop guard, the PreCompact and Stop hooks,
the managed Git hooks and `state.py`'s cache, snapshot, recover, generic writer and phase check.
Move the four jobs the watch carried that stay (merge supervision and 5.6 outcomes, the trace
sweep, the telemetry week, the tracker log) to the commands that already run each day.

## Technical Context

Stdlib-only Python 3.11+, pytest dev-only. Net deletion: about 3,000 lines of code and about
900 collected tests. Three config tables or keys retire. Run only the touched test files; CI
runs the suite.

## Constitution Check

- I: nothing added.
- II: guards keep their exits; the Stop guard goes. A damaged log is DAMAGED (exit 2).
- III: one writer of records (`state._write_state` into the log); one reader (`_fold`).
- IV: red tests first for the moved jobs (merge poll from `next.run` and `report`, trace sweep
  from `receive` and `close`, telemetry from `report`), the log-only state, the anchor without
  hooks and the upgrade; pure deletions delete their tests with the code.
- V: deletion; two `# ponytail:` notes (the fold on the hook path, Assumption 1).
- VII: the records floor and every edge stay; the default-branch push edge (#839) replaces the
  managed pre-push hook.
- Constraints: the constitution's "The only long-running process is the watch" becomes "The
  plugin runs no long-running process"; version 2.4.0, dated amendment (the watch, the last
  one, goes with #789 part 23).

## Process control: what each removed unit was

| Unit | Kind | Where its job goes |
| --- | --- | --- |
| Watch loop: PR polling (`watch.poll`, `poll_prs`), wake marks | (a) a second PR source and a nudge to the planner | the cached listing `derive.refresh` (#844) |
| Watch sweep: obligations owed, staleness (`activity`), watch health | (a) | duties in `next` (#844); stuck seats from the seat ledger |
| Watch sweep: `merge.poll` (red base trip and revert, 5.6 outcomes) | (b) | `next.run` with the listing refresh, and `report` |
| Watch sweep: `scanner.trace_sweep` | (b) kept by the lead (S2) | `dispatch receive` and `close` |
| Watch sweep: `telemetry.step` | kept by the owner | `report` |
| Watch sweep: `tracker.log` | kept | `close` already runs it |
| Watch sweep: `steward.run(trigger='sweep')` | (a) a timed review mid-day | the close trigger stays |
| `merge.monitor`'s tracker `done` | (a) a second tracker path | the `tracker` duty (#842, #844) |
| Heartbeat (timed probes, status-line cache, page) | (a) health the planner had to read | doctor's hooks and day rows, on demand, no timings |
| Headless shepherd, overnight report, its schedule | (a) | the `shepherd` duty, a normal seat (#844) |
| Session registry: `touch` on every hook, claims, rotation, `wuwei sessions` | (a) | nowhere; the seat ledger (`seats`, `stop_seat`) stays |
| `obligations.evaluate` as close gate, `obligations.sweep` | (a) | `ping` and `shepherd` duties in `next` and `close` |
| PR-thread helpers (`_ledger`, `_replies`, `_visibility`, `reply`) | (b) a merge with an unanswered thread is refused | kept in `obligations.py` |
| `wuwei event`, `wuwei state get/set/transition/recover`, `STATE_PRODUCERS` | (a) the model hand-edits or repairs records | records are written by the workflow's commands only |
| `state.json` cache, `SNAPSHOT`, `recover` | (a) a second copy of the records | the log; a torn tail is skipped (F4) |
| `_check_transition` | (b) stopped a writer jumping phases | the derived `next` never offers an out-of-order step; `pr raise --item` and `merge.check` refuse (#844 table) |
| Records guard on `days/*/state.json`, `events.jsonl`, `traces.jsonl`, plan files, goals | (b) records floor | kept; only `state.snapshot.json` and the hint naming deleted commands go |
| Stop guard (`guards/stop.py`) | (a) held the planner's turn on close and PR actions | `close` refuses until duties land; `next` names the step |
| PreCompact (`watch.flush`, `session: compact`), Stop (`session.seen`, wake, rotation) | (a) | nowhere |
| `wuwei git-hook` pre-push: push to default branch, environment branch, force | (b) | PreToolUse edge `guards/edges.check_bash` (#839), unchanged |
| `wuwei git-hook` pre-push: fast checks at the pushed HEAD | (b) | `build next` holds the handoff until fast checks pass at HEAD (pass plan table) |
| `wuwei git-hook` pre-commit: commit identity | (b) | `pr raise` checks every pushed commit's identity (`commit_push.push_check`) |
| `wuwei fast-checks` command | (a) a second way to record checks | `build check <item>` (module `fast_checks.py` stays) |
| `wuwei runtime` command | (a) a hand path around `next` | `next` launches; the runtime ports stay |

No (b) check is lost.

## Batch 8 fix round (design against its end state)

- F4 (skip a torn line in the fold): kept and becomes the only damaged-log recovery; the hint
  names `bin/wuwei doctor`.
- F6, F7, F8 (legacy-branch rule, digest, log identity on `state.json`): exist only for the
  cache. Delete them with the cache; keep F6's rule as the legacy read ("a day whose log holds
  no patch line reads its `state.json`").
- F1, F2, F3, F5, F9, G1 to G9: untouched here; if the fix round adds tests to
  `tests/test_loop.py`, keep them.
- If the fix round has not landed when this part is built, build on 71d3f06b and rebase onto
  the fix round before the PR; the conflicts are in `state.py` (`_fold`, `_write_state`) and
  `tests/test_loop.py`.

## Files to delete (code 13, tests 12 plus payloads)

Code:

- `cli/wuwei/heartbeat.py`
- `cli/wuwei/commands/heartbeat.py`, `commands/watch.py`, `commands/shepherd.py`,
  `commands/sessions.py`, `commands/event.py`, `commands/state.py`, `commands/git_hook.py`,
  `commands/fast_checks.py`, `commands/runtime.py` (commands are discovered from
  `commands/*.py`; no registration edit)
- `cli/wuwei/guards/stop.py`
- `templates/wuwei-watch.plist`, `templates/wuwei-watch.service`

Tests (whole files; move the named survivors first):

- `tests/test_watch.py` (move to `tests/test_hooks.py` the SessionStart orientation and
  orphan-seat tests, to `tests/test_ziran.py` the `scanner.trace_sweep` tests, to
  `tests/test_plan.py` the plan-session reservation tests; `records` tests to
  `tests/test_state.py`)
- `tests/test_heartbeat.py` (the `status --line` tests without a timing assertion move to
  `tests/test_signal_status.py`; the cache-fallback tests go with the fallback)
- `tests/test_headless_shepherd.py`
- `tests/test_sessions.py` (move `test_owner_answer_reads_yes_no_or_none` to
  `tests/test_card_confirms.py`)
- `tests/test_obligations.py` (move the `reply` tests to `tests/test_pr_actions.py` and the
  `answered` tests to `tests/test_linear_loop.py`, where discovery is tested)
- `tests/test_quiet_sweeps.py` (keep nothing of the watch; any status-line case moves to
  `tests/test_signal_status.py`)
- `tests/test_stop.py` (move the `closing.check` cases to `tests/test_close_branches.py`)
- `tests/test_git_hook.py`
- `tests/test_runtime_cli.py`
- `tests/test_state_allowlist.py`
- `tests/payloads/PreCompact/`, `tests/payloads/Stop/` (and their rows in
  `tests/payloads/README.md`)

## Files to edit, code (40)

### Records

- `cli/wuwei/state.py`:
  - `_write_state` (295-335): drop the `reserved` parameter and branch (312-319; all 51
    callers pass `reserved=False`: drop the argument at each), the `state.json` and `SNAPSHOT`
    writes (330-334), the `legacy` second fold. The event with its patch is the write.
  - `_fold` (162-200): read the log alone; skip an unparsable last line (F4); when the log holds
    no patch and `state.json` exists, return that file (legacy, read-only). Drop `cache` and
    the `log_size` handling. `# ponytail:` note (Assumption 1).
  - `day_started` (203-210): a patch in the log, or a legacy `state.json`.
  - `read_state` (213-222): the error names `bin/wuwei doctor`, not `state recover`.
  - Delete `SNAPSHOT` (111), `_load` (114-120), `OWNER_FIELDS` and `STATE_PRODUCERS`
    (339-366), `_producer_error` (429-447), `_generic_allowed` (450-454), `_protected`
    (457-468), `write_state` (471-473), `_parts` (476-480), `get_state` (483-490), `set_state`
    (493-508), `recover` (613-644), `_check_transition` (62-71) and its calls in `_validate`
    and `_move`.
  - `PHASES` (26-37): keep the phase vocabulary `scanner.py:88` and `status.py:186` read; the
    resume-phase map stays only if `plan.park`/`resume` still read it (check `_validate`).
- `cli/wuwei/exits.py:8`: `DAMAGED` drops "(bin/wuwei state recover for state.json)".
- `cli/wuwei/memory.py:95,98`: the hint names `wuwei why`, not `wuwei state get`.
- `cli/wuwei/commands/why.py:8,172`: `EVENT_PRODUCERS` moves here from `commands/event.py`,
  trimmed to kinds a kept command produces (`tests/test_why.py:93` expects
  `phase implement by wuwei build next`).
- `cli/wuwei/obligations.py`: `FREE_KINDS` (from `commands/event.py:10`) becomes a local
  constant; delete `evaluate` (222-269), `sweep` (272-287), `_gate_recorded` (127-143) and
  `_not_applicable` (146-155) when only `evaluate` reads them; keep the PR-thread helpers.
- `cli/wuwei/closing.py:236-254` (`check`): drop the `obligations.evaluate` call; add
  `scanner.trace_sweep(root, config)` before `scanner_hold`.
- `cli/wuwei/signal.py:6,9,18,26`: drop the tiers of kinds no code emits (`state.set`,
  `state.transition`, `session.seen`, `session.rotated`, `watch: *`, `heartbeat: clock`,
  `session: compact`, `session: wake-seen`, `shepherd.*`).
- `cli/wuwei/telemetry.py:53,140-142`: `PROBES` stays as a constant for stored weeks;
  `hook_latency_ms` reads stored `heartbeat: clock` rows only (new weeks: unmeasured);
  `OWNER_KINDS` drops `state.recovered`.
- `cli/wuwei/metrics.py:155,168,180,690-724`: delete the `session_age` table and
  `planner_turns` from Stop rows (Assumption 9); `cli/wuwei/report.py:169,176` and
  `cli/wuwei/retro.py:107,123` drop their lines (`watch.sweep_seconds` setting, session age,
  `rotate_after` proposal).

### The watch, heartbeat, shepherd, sessions

- `cli/wuwei/watch.py`: keep 1-58 (`ERRORS`, `records`, `_rows`, `_not_json`, `_finite`,
  `days`), `saved`, `save` (101-111), `owned` (114-118), `previous` (249-256), `evidence`
  (274-291); delete the rest (`health`, `_SEEN`, `_day_rows`, `activity`, `sweep`, `carried`,
  `fingerprint`, `snapshot`, `facts`, `PASSING`, `ACTIONS`, `parts`, `poll`, `mark_wake`,
  `poll_prs`, `tick`, `serve`, `run`, `wake`, `flush`, `ACTIVITY_SECONDS`,
  `MAX_READ_FAILURES`). Module docstring: "Day record readers and PR evidence helpers."
- `cli/wuwei/shepherd.py`: delete 428-588; drop the unused top-level `json` import.
- `cli/wuwei/plan.py:262-265`: drop the overnight lines.
- `cli/wuwei/workspace.py:423-431`: drop `_DAY` and its read in `day_dir`.
- `cli/wuwei/sessions.py`: delete `ROLES` entries no caller passes (`shepherd`), `COUNTED`,
  `count`, `stale_seconds`, `touch`, `_due`, `rotation`, `rows`, `claim`, `claim_item`, and
  imports only they used. Keep the rest (spec FR-004).
- `cli/wuwei/brief.py:608-609`: drop the builder brief's claim.
- `cli/wuwei/workspace.py:769,774,792,818`: drop `claim_item` calls.
- `cli/wuwei/commands/hook.py:301,332-339`: drop `claimed`; `guard.would_refuse` loses its
  `item` field.
- `cli/wuwei/pr_actions.py:50-69`: delete `_watched` and its branch (only `watch.poll` wrote
  `watch.measured_at`); `observe` keeps writing `state['watch']`.
- `cli/wuwei/merge.py`: `monitor` (648-724) drops the tracker call (673-679); `poll`
  (726-) docstring: "Reconcile merge intents and supervise base checks; `next` and `report`
  run it."
- `cli/wuwei/commands/next.py` `run` (424-429): after `derive.refresh` runs, call
  `merge.poll(root)`; a nonzero exit prints its line to stderr and never changes `next`'s exit.
- `cli/wuwei/commands/report.py`: after the report is written, run `merge.poll(root)` and
  `telemetry.step(root, config)`; each failure prints one stderr line, never the exit.
- `cli/wuwei/dispatch.py` `receive` (995-): after the verdict is recorded, run
  `scanner.trace_sweep(root, config)`; its exit is not the receive's.
- `cli/wuwei/steward.py`: the `sweep` trigger stays callable only if `commands/steward.py`
  still offers it (part 24 deletes the command); no code calls it after the watch.
- `cli/wuwei/commands/status.py:29-36,62,87-125,146-173,180-189,248-274,363-365`: drop watch
  health, heartbeat rows and page, `scan`'s watch and heartbeat parts, the sessions count and
  `_line_or_cache` (compute the line every time).
- `cli/wuwei/commands/doctor.py`: drop the `heartbeat` import (15), `status.scan` beat use
  (467), watch rows (470-478), shepherd row (479-488), heartbeat and credentials-from-heartbeat
  rows (489-501), the session id row's `session.seen` read (520-530: read the env file the
  SessionStart export names, or drop the row), `TIMED` and `_probe_fix` (570-591), the
  `_service` fix and `FIXES['watch-install']` (675-703), the git hooks rows (332-348). Replace
  `heartbeat.measure` in `diagnose` (634) with two in-process probes kept in doctor: a
  PreToolUse payload the edges refuse (exit 2) and a Read payload they allow (exit 0), run
  through `wuwei hook` with `HEARTBEAT_SESSION` (rename to `PROBE_SESSION`), reporting exit
  codes only; the state probe writes to `days/<today>/events.jsonl` and expects the records
  guard's refusal. Day row: `state.read_state` succeeds; stuck seats from `brief.seats`.
- `adapters/watch_service.py`: delete `ping` (73-79); keep `call`, `probe`, `post`.

### Hooks and guards

- `hooks/hooks.json`: delete the PreCompact (59-72) and Stop (73-86) blocks.
- `cli/wuwei/guards/__init__.py:13,23-24,28`: `EVENTS` drops PreCompact and Stop; lifecycle
  registers SessionStart and SubagentStop; the `stop` module entry goes.
- `cli/wuwei/guards/lifecycle.py`: delete `pre_compact` (114-122), `stop` (125-141), `_seen`
  and its `sessions.touch` (37), the wake read (94) and the `_day_rows` clock read (84-88);
  `session_start` keeps the orientation, `sessions.export` and the orphan-seat scan
  (`watch.days`); `subagent_stop` drops `_seen`.
- `cli/wuwei/commands/hook.py:14-17,54,70,144-145,189-191,401-404`: `CONFIG_EVENTS` is
  `('PreToolUse',)`; drop the Stop and PreCompact branches.
- `cli/wuwei/guards/protect_state.py:19-20,83,101-105`: drop `state.snapshot.json` from
  `_STATE_MENTION` and `_protected_name`; `_hint` for day records says "records are written by
  the workflow's commands; run wuwei next for the step" (names no deleted command). Keep
  `state.json`, `events.jsonl`, `traces.jsonl`, `proposal.json`, `plan.md`, `goals.md`.

### Git hooks and the anchor

- `cli/wuwei/workspace.py:745-760` (`_anchor`): write `<git dir>/wuwei-workspace` (git dir
  from `vcs.repo_context(path)['path']`) and the worktree identity; no `install`. Docstring of
  `worktree_workspace` (306-307): "Read the anchor worktree creation writes."
- `cli/wuwei/commit_push.py`: delete `configured_identity` (41-46) and `fast_evidence`
  (162-181), which only `git-hook` called; keep `context`, `push_check`, `identity_check`,
  `unset_identity`, `data`, `_item`.
- `adapters/vcs/git.py:34,82,88,595-664`: delete `Skippable` (if only the chain raises it),
  `_chain_target`, `_write_chain`, `_CHAIN_SHIM`, `_CHAIN_ONLY`, `hooks_path`, `hooks_target`;
  add `unhook(repo)`: read the worktree-scoped `core.hooksPath`; when it is
  `<workspace>/.wuwei/git-hooks` or `<git dir>/wuwei-hooks`, unset it (`git config --worktree
  --unset core.hooksPath`) and remove `<git dir>/wuwei-hooks`; return `{git_dir, unset}`.
- `cli/wuwei/registry.py:56-57`: ports `hooks_path`, `hooks_target` become `unhook: ('repo',)`.
  `tests/fakes/vcs.py` follows.
- `cli/wuwei/commands/init.py`:
  - `_worktree_hooks` (138-151) becomes `_unhook(root, dry_run)`: for each worktree with a
    `.git` file, `vcs.unhook`, then rewrite the anchor; print `Upgraded worktree <name>: unset
    core.hooksPath` (or `Would ...`); remove `.wuwei/git-hooks/` when no worktree still points
    at it.
  - The unit remover (479-487, `commands.watch._remove`) moves into `init.py` as `_remove_unit`
    (with `workspace.watch_unit`, `unit_installed` and `watch_service.call`) and removes the
    `listen`, `watch` and `shepherd` units.
  - `RETIRED_FILES` gains `watch.lock`, `watch.stdout.log`, `watch.stderr.log`,
    `shepherd.lock`, `shepherd.stdout.log`, `shepherd.stderr.log` (workspace root of
    `.wuwei/`; extend the symlink check to the `.wuwei` directory itself).
- `cli/wuwei/commands/build.py:466,471,543`: strings name `wuwei build check <item>` instead of
  `wuwei fast-checks`.

### Config

- `cli/wuwei/workspace.py:81,116-121`: delete SCHEMA `worktree`, `watch`, `sessions`;
  `RETIRED` gains `'watch'`, `'sessions'`, `'worktree'`. Bump `CONFIG_CACHE_VERSION`.
- `templates/workspace/config.toml:14,45,160-170` and the `[worktree]` block: delete the
  blocks; line 14 names `wuwei build check`.
- `cli/wuwei/report.py:169`: no `watch.sweep_seconds` line.

## Files to edit, tests (about 45)

- `tests/conftest.py:22-29`: delete the autouse `quiet_heartbeat` fixture (first edit; every
  test imports through it).
- `tests/test_state.py`: delete the recover, snapshot, transition-check and event-command
  tests (about 45 cases: `test_recover_*`, `test_corrupt_state_names_recovery_*`,
  `test_hook_names_recovery_then_continues`, `test_all_transition_edges`,
  `test_pause_returns_only_to_previous_phase`, `test_set_and_writer_cannot_skip_phases`,
  `test_transition_cli_rejects_implement_to_done`, `test_retry_transition_*`,
  `test_delete_recreate_cannot_bypass_lifecycle`, `test_dedicated_event_kinds_reserved`,
  `test_invalid_event_input`); add the red tests of T002.
- `tests/test_loop.py`: delete `test_deleting_state_json_between_two_calls_changes_no_answer`,
  `test_deleting_state_json_between_any_two_next_calls_changes_no_answer` and the pair
  materialisation in `results`; `materialise` writes no `state.json`.
- `tests/test_hooks.py`: delete PreCompact, Stop-hook, heartbeat and `watch` cases
  (`test_heartbeat_refusals_are_not_recorded`, `test_no_hook_path_imports_heartbeat`,
  `test_heartbeat_latency`, `test_enforce_off_does_not_log_the_heartbeat`,
  `test_unit_installed_matches_the_unit_file`, `test_subagent_stop_skips_watch_and_memory`, the
  Stop rows of `test_workspace_hook_latency`); keep SessionStart and SubagentStop.
- `tests/test_doctor.py`: fixture 98-106 (no watch unit, no `heartbeat.measure` patch);
  `FIXES` pin (164-167) loses `watch-install`; delete `test_fix_installs_watch`,
  `test_day_shepherd_row`, `test_credentials_row_when_watch_and_doctor_disagree`; rewrite
  `test_day_rows` and `test_guards_rows` over the new probes (red first, T006).
- `tests/test_merge.py`: `test_watch_scheduler_runs_merge_poll` becomes the `next.run` and
  `report` cases (T004); `test_owner_merge_holds_on_every_path` drops its headless path.
- `tests/test_pr_ownership.py`, `tests/test_stop.py` survivors: `watch.poll` and `saved` cases
  go (6 and 14).
- `tests/test_telemetry.py`: the three `step` cases call it through `report` (T004).
- `tests/test_steward.py`: `test_sweep_and_close_trigger_steward` keeps the close trigger.
- `tests/test_integrity.py:279,292`: `test_every_sweep_measures_integrity` goes (SessionStart
  warns); `event.run` use goes.
- `tests/test_env_credentials.py`: `test_entry_paths`, `test_watch_command_loads_before_tick`
  drop the watch entry.
- `tests/test_adapters.py`: delete `watch_service` `ping` tests and
  `test_watch_probe_runs_calls_together_and_times_out`; keep `probe` and `post`.
- `tests/test_config_transition.py`: listen-unit removal through the moved remover; new
  retired keys and the worktree unhook (T008).
- `tests/test_dev_cycle.py:16-28`: `TIMING` loses the deleted tests.
- `tests/test_launch_contract.py:50-73`: the two `runtime` CLI tests go.
- `tests/test_worktree_command.py`, `tests/test_brief.py`, `tests/test_handback.py`,
  `tests/test_metrics.py`, `tests/test_report_retro.py`, `tests/test_config_writer.py:142`,
  `tests/test_workspace.py`, `tests/test_ziran.py`, `tests/test_traces_seats_only.py`,
  `tests/test_answers.py`: claims, `session.seen`, `rotate_after`, `sessions` keys go.
- `tests/test_vcs.py`, `tests/test_vcs_guard.py`, `tests/fakes/vcs.py`, `tests/test_commit_push.py`
  (drops `from wuwei.commands.git_hook import invoke`), `tests/test_edges.py:436`
  (`test_heartbeat_force_push_probe_is_refused` becomes the doctor probe row),
  `tests/test_parser_warns.py:96-101`, `tests/test_protect_state.py`
  (`test_state_snapshot_is_protected`, hint text), `tests/test_fast_checks.py` (CLI cases
  call `fast_checks.record` or `build check`), `tests/test_why.py:93`, `tests/test_reasons.py`
  (delete the LEFT row `('watch.py', 'install in a host terminal', 23)`),
  `tests/test_invariants.py:79` (re-measure the corpus floor after the deletion, with a
  comment naming part 23; lead call (b)), `tests/test_cli.py` (help list),
  `tests/test_signal_status.py`, `tests/test_e2e_day.py`, `tests/test_path_day.py`,
  `tests/test_headless_e2e.py` (no Stop events), `tests/test_next.py:282`,
  `tests/test_merge.py:501-505` (generic-event forging test goes with the command).
- About 28 files call `main(['event', ...])` or `main(['state', ...])` to assert a refusal:
  each such case goes with the command; a case that used it to append a `note` event calls
  `state.append_event`. Find them with `grep -rln "'event'\|\"event\"\|'state', '" tests`.

## Docs, charters, spec, scripts

- `docs/site/reference.md` command table (21, 22, 23, 25, 41, 43, 45, 46, 47, 53): delete the
  nine rows and the `sweep` row's `obligations`/`watch` subcommands (forced by
  `tests/test_docs.py:130-137`). The rest of the site is part 24's rewrite.
- `docs/site/configuration.md`: drop `[watch]`, `[sessions]`, `[worktree]` sections and their
  keys (forced by `test_every_template_config_key_is_documented` and
  `test_configuration_names_every_config_section`).
- `charters/builder.md:19`: delete "commits are the heartbeat read by the staleness sweep".
  Rebuild with `bin/wuwei agents build`.
- `.specify/memory/constitution.md`: the long-running-process line (Constraints), version
  2.4.0, Last Amended 2026-10-12.
- `docs/specs/2026-09-24-wuwei-design.md`: 3.3 workspace files; 4.1 hook table rows for
  PreCompact and Stop (186-187) and the PreToolUse `state.json` row wording (178); 4.2 Sweeps
  (189-196); 4.2.1 wake, overnight and Stop anchor (219-237); 4.5 pre-push hook (283); 9.1
  pre-commit and pre-push hooks and 0444 state files (1402-1403, 1451); the Stop guard on day
  close (1726); 5.13 telemetry week step (945, 1022, 1057-1059: the report runs it); 5.5 the
  steward's sweep trigger; dated note "(#789 part 23, 2026-10-12)".
- `scripts/headless_e2e.py:329,383,390`: the prompt drops `runtime dispatch` and the
  `state transition, state set or state recover` sentence.

## RETIRED (base has `workspace.RETIRED`)

Add `'watch'`, `'sessions'`, `'worktree'`.

## Handoff to part 24

- `sweep` keeps only `classes`; part 24 moves it.
- `status` keeps `--line` and its plain and `--json` forms; part 24 decides.
- `adapters/watch_service.py` keeps its name.
- `docs/site` prose, README, the hero files (`scripts/build-hero.py:23,66,208`,
  `docs/site/assets/hero-*.svg`) still name the heartbeat and the overnight shepherd.
