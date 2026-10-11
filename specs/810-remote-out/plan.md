# Implementation Plan: delete the remote control plane, the listener and the inbox

**Branch**: `810-remote-out` | **Date**: 2026-10-11 | **Spec**: [spec.md](spec.md)

## Summary

Delete the M5 listener (`wuwei listen`), the inbox, the inbound port, the control plane, the
DM responder and `wuwei remote ack`, plus the two units only the listener reached: the
headless shepherd seat (`shepherd.autostart`) and the runtime `headless` function. The watch
takes back PR polling unconditionally. `init --upgrade` removes a leftover listener service
unit. Docs, the charter line, the design spec (section 15 marked retired) and the
constitution constraint follow.

Counts: 13 files deleted (8 code, 1 docs page, 4 test modules); 79 files edited
(30 code and template, 1 charter plus 9 rebuilt agents, 13 docs, 26 tests), of which 6
(GROUPS, WRITES, protect_state, nudges and two tests) are skipped if parts 3 and 4 removed
them first. Line
numbers are at main `221f1f2`; verify each against the rebased tree.

## Technical Context

Stdlib-only Python 3.11+, pytest for tests. No new module, event kind, state key or config
key. One new behaviour: `init --upgrade` removes a listener unit. One changed behaviour: the
watch polls PRs whenever due.

## Constitution Check

- I stdlib only: nothing imported.
- II three-state exits: unchanged; `init --upgrade` keeps its exits (a unit removal failure is
  a warning, as `commands/watch._remove` already does).
- III one behaviour, one function: PR polling stays in `watch.poll_prs`; the unit removal
  reuses `commands/watch._remove`.
- IV test first: tasks.md writes the failing test before each behaviour change; pure
  deletions delete their tests with the code.
- V ponytail: deletion; the only addition is the leftover-unit removal (about 8 lines).
- VII security: the remote guards (pin, TOTP, confirm window, memory floor) leave with the
  command channel they guarded; no surviving surface loses a guard. Seat-role refusals stay.
- Design spec: amended only under the owner's #789 instruction, every edit marked.
- Constraint "only long-running processes are the watch and the listener": amended to the
  watch only (constitution patch bump, dated).

## Units removed and why (rule of the pass)

| Unit | (a) or (b) | Where its job is now |
|---|---|---|
| `wuwei listen` loop, cursor, wake (`listen.py`, `commands/listen.py`) | (a) wakes the model about inbound process | none |
| Inbox (`inbox.py`, `.wuwei/inbox/*`) | (a) | none; files stay on disk until part 24 |
| Inbound port (`adapters/inbound/*`, `registry` `inbound`, `adapters.inbound`) | (a) | none |
| Control plane (`control_plane.py`: pending, parse, render, escalate, notify, poll_replies) | (a) | the planner's question card (Claude Code Remote Control push) |
| DM responder (`remote.py`: vocabulary, `handle`, `start`, `resume`, `stop`, `more`, `escalate_new`, `deny`, `tools`, `dm`) | (a) model turns started from chat | none |
| Remote guards (`remote.sender`, `code_step`, `confirmation`, `memory_floor`, `totp`) | security of the deleted channel | none needed: no inbound command channel exists |
| `wuwei remote ack`, `remote.refused` page, `remote.acknowledged` | (a) | none |
| Listener PR probe (`listen.prs`) and `watch.listening` | (b) PR state must stay fresh | `watch.tick` polls via `watch.poll_prs` every `pr.poll_seconds` |
| Listener DMs (`listen.notify`: pr.notified, negotiation.notified, decision.notified) | (a) | events stay in the log; `status` and the planner wake show PR changes |
| Headless shepherd (`shepherd.pending`, `shepherd.headless`, `HEADLESS`, `shepherd.autostart`) | (a) a model seat started outside `next` | `wuwei next` offers shepherd launches; #511 `shepherd.loop` unchanged |
| Runtime `claude.headless` | (a) | none |
| Phone answers (`decision.replied`, `status` `decision.answered`, SessionStart lines, `phone answers N`) | (a) | the owner answers the card; `wuwei decide` records it |
| DM-only two-way branch in `owner_outcome` | (a) | none |
| `listen` health (lifecycle, heartbeat clocks, status, doctor `listener` row, `listen-install` fix) | (a) health of a deleted process | watch health unchanged |
| `config check` control-plane section, TOTP, pin finding | (a) | none |
| `setup slack` pin, TOTP, inbound, listener install | (a) | token and app DM channel kept for outward chat |
| `sessions` role `remote` and `thread` | (a) | none |
| Interview `phone` question, `control_plane.content`, `owner.verbosity.dm` | (a) | none |

Kept and named: the `WUWEI_SEAT_ROLE == 'shepherd'` refusals in `merge.py:504`,
`outward.py:631` and `guards/pr.py:397` (b: a seat may not merge or send); they wait for
parts 17 and 23. `adapters/redactor` stays (profiles export uses it). `adapters/chat/slack.py`
`history` stays (chat `sent` uses it). `SLACK_OWNER_DM_CHANNEL` stays (chat `dm`, drafts,
outbound). `commands/watch.service` and `watch.serve` stay generic (shepherd uses them).

## RETIRED at rebase

The base has no `workspace.RETIRED` (#799 unmerged). After #799 merges, the lead adds:
`'listen'`, `'responder'`, `'control_plane'`, `'adapters.inbound'`, `'shepherd.autostart'`,
`'owner.verbosity.dm'`.

## Files to delete (13)

- `cli/wuwei/control_plane.py`
- `cli/wuwei/inbox.py`
- `cli/wuwei/listen.py`
- `cli/wuwei/remote.py`
- `cli/wuwei/commands/listen.py`
- `cli/wuwei/commands/remote.py`
- `adapters/inbound/none.py`, `adapters/inbound/slack.py` (the directory goes)
- `docs/site/remote.md`
- `tests/test_control_plane.py`, `tests/test_inbox.py`, `tests/test_remote.py`
- `tests/test_listen.py`, after moving its kept cases (below) into `tests/test_watch.py`

## Files to edit: code

### `cli/wuwei/workspace.py`
- `SURFACES` drops `"dm"` (38).
- `SCHEMA` drops `"listen"` and `"responder"` (154-155), `"autostart"` in `shepherd` (178),
  `"control_plane"` (257), `"inbound"` in `adapters` (267).

### `cli/wuwei/registry.py`
- `PARAMETERS` drops `'inbound'` (18).

### `cli/wuwei/telemetry.py`
- `ADAPTERS` drops `'inbound'` (43). `OWNER_KINDS` drops `'remote.acknowledged'` (47).
- `found['owner_actions']` drops `row['kind'].startswith('remote.') or` (204).
- The span branch drops `or kind.startswith('remote.')` (461).

### `cli/wuwei/watch.py`
- Delete `listening` (572-574); `tick` polls when `due('poll_at', ...)` alone (592).
- `mark_wake`: drop the `inbox` keyword, the inbox comparison and count (541-561); the
  "already covered" early return keeps `if pending and not prs and not summaries: return`.
- `wake`: drop the inbox count, its check and the `inbox to line` text (685-694); a marker with
  no PRs and no summaries returns `''` instead of raising.
- Comments: 85 ("SessionStart asks for watch health"), 564-565 docstring ("the watch's full PR
  read and merge reconcile").

### `cli/wuwei/shepherd.py`
- Delete `_STOP`, `_TRIAGE`, `HEADLESS`, `pending`, `headless` (427-500); drop imports left
  unused (`registry` if nothing else reads it).

### `adapters/runtime/claude.py`
- Delete `SESSION`, `TIMEOUT` and `headless` (64-108); drop `subprocess` and `env` imports if
  unused after.

### `cli/wuwei/guards/lifecycle.py`
- Clocks read only `watch` (87-89); delete the `listen` health block (96-99) and the
  phone-answer block (105-112, the `decision_routes` check and the `attention` call).

### `cli/wuwei/heartbeat.py`
- `PROBES` `clocks` text: "watch clock alive or off" (18). `_clocks`:
  `stamps = {'watch': []}` (92).

### `cli/wuwei/commands/status.py`
- `SKIP` (39-42) drops `'listen: clock'`, `'decision.replied'`, `'remote.acknowledged'`.
- `scan`: `clocks = {'watch': []}`, no `replied`, no `pin` (69); drop `'listen: clock'` (95),
  the `decision.replied` block (99-100), the `remote.acknowledged` block (122-125), the
  `remote.refused` pin block (128-133), `'remote.refused'` from the 159 tuple; the
  decision-routes loop (219-229) loses the `replied` branch (after part 4 the whole
  `decision.answered` row goes); return `rows, health['watch'], beat_health, loops` (259);
  docstring.
- `snapshot`: unpack four values (331); drop `result['answered']` (334) and the
  `listen = 'none'` lines (368-369).
- `_groups`: drop the `phone answers` entry (511) and `listen` from health (520).
- `surfaced` docstring and the `decision.answered` keep (286, 296) if part 4 has not
  removed `surfaced`.

### Callers of `status.scan` (four values now)
- `cli/wuwei/commands/doctor.py:632` and `cli/wuwei/commands/next.py:306`.

### `cli/wuwei/commands/doctor.py`
- Host `claude` row (249-255): delete the row (nothing needs the CLI on PATH).
- Service manager fix text (275): "the watch needs launchd (macOS) or systemd --user (Linux)".
- `_day` (632-647): unpack four values; the loop over `('watch', 'listener')` becomes the watch
  row alone.
- `FIXES` drops `'listen-install'` (984).

### `cli/wuwei/commands/config.py`
- Delete `PIN_MISSING` (13), the `Control plane:` block (121-130), the `('inbound', 'slack')`
  requirement (182), the pin finding and `from wuwei.remote import PIN` in `missing`
  (199, 211-213); docstring "credential variables and codex.command".

### `cli/wuwei/commands/setup.py`
- `connect`: keep token and DM channel; `settings = [(('adapters',), 'chat', 'slack')]`;
  delete the pin block, the `outbound.owner.slack.user` derivation, the TOTP block and the
  listener install (654-697); when `outbound.owner.slack.user` is empty print
  `Set your Slack user id: bin/wuwei config set outbound.owner.slack.user '"<U id>"'`.
  Docstring "Token, DM channel and the chat adapter; a value already set is kept."
- Delete `_first_dm` (700-717), `WAIT_SECONDS`/`POLL_SECONDS` (26-27), `DM_HINT` (30-31);
  `TOKEN_HINT` drops "(remote operation section 2)".
- `_setup` (556-560): the condition becomes `load_config(root)['adapters']['chat'] != 'slack'`
  (connect when chat is not yet slack).
- `register` help (44): "slack: connect the chat adapter: bot token and app DM channel".
- Drop imports left unused (`time`, `base64`, `secrets`).

### `cli/wuwei/commands/decision.py`
- `owner_outcome`: delete the `if where and ... != 'two-way'` branch (203-205); docstring
  "where is given by a caller that already holds the owner's confirmation". Same docstring
  in `undo` (264-265).

### `cli/wuwei/commands/outbound.py`
- Docstring 185-186: "never the WUWEI app DM" (drop "which the listener reads as owner
  input"); the check stays.

### `cli/wuwei/commands/event.py`
- Delete producer rows `inbox.redacted` (27), `decision.replied`, `decision.escalated` (32-33),
  `pr.notified` (34), `shepherd.dispatched`/`shepherd.finished` (35), the `remote.*` rows
  (38-39), `listen: clock`, `listen: wake` (65), `negotiation.notified`, `decision.notified`
  (86). `pr.changed` producer: `wuwei watch`. `decision.decided` and `decision.reversed`
  producers: `wuwei decision outcome` (59, 62).

### `cli/wuwei/state.py`
- Writer text: `decision_outcomes` drops "or wuwei listen (two-way DM answer)" (254);
  `watch`: `wuwei watch` (260); `sessions` drops "wuwei listen (remote sessions)" (271).

### `cli/wuwei/signal.py`
- `SILENT` drops `remote.acknowledged`, `decision.replied`, `listen: clock`, `listen: wake`,
  every `remote.*`, `decision.escalated`, `inbox.redacted`, `shepherd.dispatched`,
  `pr.notified`, `negotiation.notified`, `decision.notified` (6-27).
- Delete the `shepherd.finished` branch (52-53) and `'remote.refused'` from the page tuple (71).

### `cli/wuwei/sessions.py`
- `ROLES = ('adhoc', 'seat-host', 'shepherd')` (13); `record` and `touch` drop `thread`
  (68, 83-84, 98, 107); the row copy at 168 drops `'thread'`.

### `cli/wuwei/env.py`
- `CREDENTIALS` drops `'WUWEI_TOTP_SECRET'` (15).

### `cli/wuwei/interview.py`
- Delete the `phone` question (184-189); `RETIRED = ('posture', 'tier', 'learn', 'phone')` (363).

### `cli/wuwei/profiles.py`
- `PRIVATE` drops `'control_plane.owner'` (18); `DENIED` drops the `shepherd.autostart` rule (35).

### `cli/wuwei/cruise.py`
- Comment 89: "the window runs from the answer".

### `cli/wuwei/commands/init.py` (new behaviour)
- In `upgrade`, after the config migration: if
  `workspace.watch_unit(root, platform, name='listen')[1]` exists on darwin or linux, under
  `--dry-run` print `Would remove the listener service (no longer shipped)`, else call
  `commands.watch._remove(path, platform, registry.watch_service(), 'listen')` and print
  `Removed the listener service (no longer shipped)`.

### Owned by earlier parts (skip if already gone at rebase)
- `cli/wuwei/__main__.py:31` GROUPS drops `remote` and `listen` (part 3 deletes GROUPS).
- `cli/wuwei/commands/__init__.py:18,28` WRITES drops `listen install`, `listen uninstall`,
  `remote ack` (part 3 deletes WRITES).
- `cli/wuwei/guards/protect_state.py:73-82` the `listen uninstall` and `remote ack` owner
  actions (part 3); `('inbox',)` in the protected tail (387) goes here.
- `cli/wuwei/commands/nudges.py:20` `'listen: health'` (part 4 deletes the file).

### Other
- `adapters/redactor/builtin.py:1` docstring: "Built-in redaction of text: phone numbers,
  emails and secrets."
- `templates/workspace/config.toml`: delete `[control_plane]` (117-119); the
  `owner.verbosity` lines (66-67) drop "the DM" and `dm` from the surface list; delete
  `autostart` under `[shepherd]` (313).
- `charters/_common.md` checklist item 2: drop "or escalating through a control plane"; run
  `bin/wuwei agents build` (rewrites the 9 `agents/*.md`).

## Files to edit: docs

Rule: delete the sentence, row or section about the deleted unit; reword only where a kept
sentence would break.

- `README.md`: the remote operation bullet (31), the "or as a DM on your phone" clause (53),
  the `inbound` adapter row (96).
- `mkdocs.yml`: nav `Remote operation: remote.md` (73).
- `docs/site/index.md`: "the listener" in the Concepts line (10), the Remote operation link (18).
- `docs/site/concepts.md`: `listen uninstall` and `remote ack` in the owner list (212), "The
  listener sends the summary to your DM." (490), the `## Listener` section (524-532).
- `docs/site/daily.md`: 393, 418 (phone answers), 429 and 453 ("or reply `undo D-3` to the
  listener DM"), 435, 486 ("or as a DM from the listener ...").
- `docs/site/configuration.md`: `[control_plane]` in the table (13), `owner.verbosity.dm` (82),
  the listener clause of `pr.poll_seconds` (163), `shepherd.autostart` (175), `listen.*` and
  `responder.enabled` (184-186), `adapters.inbound` (250), "inbound" in `adapters.redactor`
  (251), `control_plane.*` (260-261), interview `phone` row (385), `shepherd.autostart` in the
  profile list (412), `## Running the listener` (642-716), the `Control plane:` paragraph of
  config check (733-735).
- `docs/site/reference.md`: rows 42 and 61, the listener sentence (130), `clocks` row (206),
  "and listen parts" (218), `listener` in the doctor list (241), the "(the listener with ...)"
  example (266), `listen-install` fix row (281), `remote` role (307), rows 452-453.
- `docs/site/adapters.md`: `inbound` row (16), "Inbound text passes through the redactor"
  clause (19), the listener clause on `SLACK_OWNER_DM_CHANNEL` (44), `inbound.slack` row (70),
  the `[control_plane]` section.
- `docs/site/agent.md`: "the listener can start it headless" (12), `listen uninstall` and
  `remote ack` in the owner list (59).
- `docs/site/security.md:95` "and, when built, an external control plane": delete the clause.
- `docs/site/integrity.md:54,72`: "external control plane" becomes "external supervisor".
- `.specify/memory/constitution.md`: Constraints line 67-68 "The only long-running process is
  the watch."; version 1.5.0 to 1.5.1 (or one patch above the rebased value), Last Amended
  2026-10-11.
- `docs/specs/2026-09-24-wuwei-design.md`: heading 2137 becomes
  `## 15. Post-v1 (M5): always-on responder and inbound messaging (retired by #789, owner, 2026-10-10)`
  with one line under it: "Retired: the listener, the inbox, the inbound port and the control
  plane were removed by #789; the text below is history." Mark lines 43, 160-161, 328, 1030,
  1073, 1261, 1917 and 1957 with "(retired by #789)" or drop the listener clause.

## Files to edit: tests

Delete a test together with the code it covers; never relax an assertion on kept code.

- `tests/test_listen.py`: before deleting, move into `tests/test_watch.py` (adapted to its
  fixture, no inbound config): `test_wake_marker_keeps_summaries_while_unseen` (173),
  `test_summary_only_mark_is_not_already_covered` (190, without the inbox mark: first mark a
  PR and consume it), `test_pr_only_marker_is_unchanged` (207),
  `test_session_start_reads_the_day_once` (1048, with `watch: clock`),
  `test_session_start_reports_a_broken_events_file` (1071), and the torn-line half of
  `test_session_start_decodes_a_day_without_routes_once` (602-616) as its own test.
- `tests/test_watch.py`: replace `test_watch_skips_pr_poll_while_the_listener_lives`
  (1384-) with `test_watch_polls_prs_even_with_a_listen_clock_line` (US2); delete the
  `name='listen'` health assertion (1425); add the legacy inbox-only wake test (US3).
- `tests/test_runtime.py`: delete `headless_case` and the six `test_claude_headless_*` (186-266).
- `tests/test_guard_mutation.py`: delete the `wuwei.remote` entries in `SPECIAL_TESTS` (61-62)
  and `required` (105), `remote_case` and the four remote probes (231-317).
- `tests/test_decision.py`: delete `test_owner_outcome_with_where_refuses_a_one_way_record`
  (732-745); drop `'decision.replied'` from the reserved-kind parametrize and its branch
  (524-533).
- `tests/test_signal_status.py`: drop the removed kinds from the classification tables
  (325, 349, 370-376); delete the phone-answer tests (518-555) and the `decision.answered`
  expectation (800-810); delete the `listen: health` case (831); `status --json` keys and
  status line expectations without `listen` and `phone answers` (920, 968, 1063-1072).
- `tests/test_doctor.py`: FIXES set without `listen-install` (191); delete the inbound
  `claude` case (253) and the `claude` host row assertions (277-280); day row names without
  `listener` (637-640).
- `tests/test_heartbeat.py`: `test_dead_listener_fails_clocks` (159-) deleted; the clocks value
  `watch off` where asserted; `'inbound'` out of `network` (486).
- `tests/test_setup.py`: `SLACK_NAMES` without TOTP (990); the slack fixture without the
  inbound port and service install (995-1030); rewrite the connect tests (1040-1145) to assert
  token, channel and `adapters.chat` only (US4, test first); delete the pin, TOTP and listener
  reinstall cases.
- `tests/test_env_credentials.py`: delete the `inbound` requirement case (283-284), the TOTP
  line of `test_owner_dm_channel_is_not_redacted` (734), the pin finding test (761-777) and
  `test_no_control_plane_section_without_an_inbound_adapter` (779).
- `tests/test_workspace.py`: defaults without `control_plane`, `listen`, `responder`,
  `autostart`, `inbound` (237, 254, 265, 283); delete the `inbound` case (1198-1199) and
  `test_shepherd_autostart_defaults_on` (1210-1215).
- `tests/test_interview.py`: replace `phone` with another workspace question id in the
  record, widget and answer cases (93, 325-371, 464-505, 604-631, 841-845); delete the
  `control_plane` placement cases (17, 34-40, 672) or move them to another key; add one case:
  a day file with `phone` loads (US3).
- `tests/test_calibrate.py`: delete the `shepherd.autostart` DENIED case (757) and its export
  check (1086, 1089); `SEEDED` and the dropped-keys assertion without `control_plane`
  (990, 1031-1033).
- `tests/test_report_retro.py`: cut the remote tail of `test_report_levels` (334-end of test).
- `tests/test_outward.py`: delete the `remote.CONFIRM` assertion (770, 780); drop
  `control_plane.py`, `remote.py`, `listen.py` from the scanned list (954).
- `tests/test_reasons.py`: drop the `control_plane.py` entry (28).
- `tests/test_reference_adapters.py`: delete the inbound slack and listener cases (405-498).
- `tests/test_adapters.py`: drop the `inbound` port row (18).
- `tests/test_sessions.py`: the two `role='remote', thread=...` calls (271, 307) use
  `role='shepherd'` without `thread`; drop thread assertions; add none.
- `tests/test_state_allowlist.py`: drop `('remote.acknowledged', 'wuwei remote ack')` (132).
- `tests/test_telemetry.py`: replace `remote.acknowledged` and `remote.started` sample events
  (70, 345) with kept owner kinds (`state.recovered`, `mcp.decided`).
- `tests/test_protect_state.py`: delete the `remote ack` case (637-642) if part 3 has not.
- `tests/test_quiet_sweeps.py`: drop `('bin/wuwei listen uninstall', 1)` (384) if part 3 has not.
- `tests/test_hooks.py`: `test_unit_installed_matches_the_unit_file` uses `name='shepherd'`.
- `tests/test_config_transition.py` (the `init --upgrade` tests): add the listener-unit removal and
  dry-run cases (US3, test first).
- `tests/test_docs.py`: delete `test_remote_runbook_matches_the_code` (629-),
  `test_pr_events_are_documented`'s remote half (1089-1091), the `remote.md` line of
  `test_owner_verbosity_and_voice_are_documented` (1103-1104), the remote line in
  `test_config_check_host_...` (800); drop `docs/site/remote.md` from the README link list
  (836), `'Listener'` from the concepts headings (863), the `phone answers` daily check (869),
  `'listen uninstall'` (500), and change `'[control_plane]' in adapters` (701) to
  `'[control_plane]' not in adapters`. Skip what part 1 already deleted.
- `tests/conftest.py:21`: comment "A developer's owner DM channel must never reach a test".

## Risks

- Parallel parts collide on `status.py`, `doctor.py`, `signal.py`, `telemetry.py`,
  `test_signal_status.py` and `test_docs.py`; rebase after parts 1 to 6 and drop edits to code
  already gone.
- An owner with the listener installed: covered by the `init --upgrade` unit removal; until
  they run it, launchd or systemd restarts a failing `bin/wuwei listen`.
- `wuwei setup slack` no longer derives `outbound.owner.slack.user`; owner-only sends to the
  owner's own DM need the owner file. The setup output names the step.
- The negotiation-loop and PR-change DMs stop. The events stay and the planner wake still
  shows PR changes at the next session turn.
