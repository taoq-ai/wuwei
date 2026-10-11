# Implementation Plan: delete the MCP registry gate; scanner findings stay for the security gate

**Branch**: `b7-leftovers` | **Date**: 2026-10-11 | **Spec**: [spec.md](spec.md)

Line numbers are at d60253b8, the batch base (main plus part 15). Part 16 (#838, outward
allowlist) and part 17 (#839, exact-argv edges) land before this batch. Edits that depend on
them are marked **[after 16]** or **[after 17]**; locate code by function name in the files
they touch. After part 16:

- `drafts.py`, `commands/drafts.py` and `commands/outbound.py` are gone, so the MCP gate is
  the last caller of `decision.owner_confirm`, `sessions.caller`, `sessions.gate_topics` and
  `integrity._host_confirm`;
- `decision.route_owner` is gone; `guards/answers.py` has no Draft branch;
- `tests/test_reasons.py` LEFT has no part 16 rows.

After part 17: `guards/integrity.py` has no PreToolUse check, `guards/edges.py` exists, and
`agent_launch.check_mcp` is handed to this part.

## Summary

Delete `wuwei mcp`, the registry, the launch gate and every reader of them. Keep the ZIRAN
paths the security gate reads (S2 traces, S4 audit). With the MCP cards gone, finish part 14's
handoff: the D-n record library in `decision.py`, the D-n branch of `record_gate`,
`owner_confirm`, `sessions.caller`, `sessions.gate_topics` and `integrity._host_confirm` go,
with their LEFT rows.

## Technical Context

Stdlib-only Python 3.11+, pytest dev-only. Net deletion: about 1,100 lines of code and 2,000 of
tests. Four config keys retire. Run only the touched test files; CI runs the suite.

## Constitution Check

- I: nothing added.
- II: no guard changes exit semantics; one guard (`check_mcp`) goes.
- III: one Owner step recorder stays (`record_gate`); one scanner path per job (`scanner.rows`,
  `scanner.trace_sweep`).
- IV: red tests first for the new assertions (no `_host_confirm`, no `D-n` topic recorded, no
  `mcp` row); pure deletions delete their tests with the code.
- V: deletion.
- VII: the security sentinel keeps S4 on `agent_surface`; plugin integrity (SessionStart
  warning) is unchanged. No guard on a publishing edge changes.
- Design spec ownership: part of the owner-approved #789 pass.

## Process control: what each removed unit was

| Unit | Kind | Where its job goes |
| --- | --- | --- |
| `wuwei mcp check` (morning ritual, `next` `mcp` row, `plan propose` check and sweep line) | (a) the planner runs a process step and reads its findings | nowhere |
| `wuwei mcp decide`, the D-n MCP cards, `owner_confirm`, the host-terminal y/N | (a) the owner reasons about a record and answers outside the session | nowhere |
| Launch gate (`agent_launch.check_mcp`, runtime `mcp.launch`) on `scanner.mcp.block` | (a) for the process; the risk is the owner's when attaching a server | nowhere; S4 still scans an `agent_surface` change at the security gate |
| `MCP unmeasured:` brief header | (a) | nowhere |
| doctor `mcp gate`, `mcp reports`, per-server rows and the `mcp-reports` fix | (a) | nowhere |
| doctor `answered cards` row (`_unrecorded`, `_owner_on_file`) | (a) no record command is left to forget | nowhere |
| `record_gate` D-n branch, `gate_asked` on the planner row, `sessions.caller`, `sessions.gate_topics` | (a) | nowhere; the Owner step branch (#831) is unchanged |
| `scanner.rows`, `scanner.merge`, `scanner.trace_sweep`, `ziran.audit/gate/traces` | (b) kept: scanner findings at the security gate and on seat sessions | unchanged |

No (b) check is lost.

## Files to delete (3, plus 1 test file)

- `cli/wuwei/mcp.py`
- `cli/wuwei/commands/mcp.py` (commands are discovered from `commands/*.py`; no registration
  edit)
- `tests/test_mcp.py` (the gate tests and the ZIRAN `mcp` adapter tests 32-174, 560, 969)

## Files to edit, code (24)

### Adapters

- `adapters/scanner/ziran.py`: delete `mcp` (78-151), `_rollback` (154-157, only `mcp` uses
  it) and `_mcp_report` (160-174); drop the `hashlib`, `os` and `shutil` imports if no other
  reader is left (`tempfile` stays for `traces`).
- `adapters/scanner/none.py:18-19`: delete `mcp`.
- `adapters/runtime/claude.py:11-14, 40-43` and `adapters/runtime/codex.py:34-37, 155-158`:
  delete the `mcp.launch` preflight in `dispatch` and `continue_job`.

### CLI

- `cli/wuwei/registry.py:32`: drop `'mcp': ('servers',)` from the scanner port.
- `cli/wuwei/workspace.py`:
  - SCHEMA `scanner.mcp` (55-59): keep only `plugins_file`;
  - `RETIRED` gains `'scanner.mcp.project_file'`, `'scanner.mcp.user_file'`,
    `'scanner.mcp.timeout_seconds'`, `'scanner.mcp.block'`;
  - bump `CONFIG_CACHE_VERSION` if the schema change needs it (the test pins it).
- `cli/wuwei/plan.py:265-272` (`propose`): delete the `mcp.check`/`mcp.cached` block, the
  refusal and `data['sweep']['mcp']`.
- `cli/wuwei/brief.py:465-468`: delete the `MCP unmeasured:` header.
- `cli/wuwei/guards/agent_launch.py:30-40, 456` **[after 17]**: delete `check_mcp` and its
  `Guard`; `MODULES['agent_launch']` keeps `PreToolUse: Agent` for `check`.
- `cli/wuwei/commands/next.py`:
  - `THEN['mcp']` (51) and the morning `mcp` row (181-183) go;
  - the gate resolve's `widget += mcp.widget(root)` (348-350) goes;
  - `ENFORCE[True]` (20): drop "and MCP findings below the floor".
- `cli/wuwei/commands/doctor.py`:
  - `DOCS['gates']` (23) points at the anchor that stays (configuration.md section on
    scanners, or `security.md`);
  - `_hooks` (168, 176): the default plugins file is
    `workspace.SCHEMA['scanner']['mcp']['plugins_file'][1]`, not `mcp.DEFAULTS`;
  - `_gates` (451-482): keep the config check row (453-457), delete the `mcp gate`,
    `mcp reports` and per-server rows;
  - `_unrecorded`, `_owner_on_file` (675-695) and the `answered cards` row (~628-633)
    **[after 16: the draft half is already gone]** go;
  - `_reports_preview`, `_reports` (825-835), the FIXES row `'mcp-reports'` (846) and the
    `mcp decide` word in the comment (840) go.
- `cli/wuwei/commands/status.py:96-98, 153-160`: delete the `mcp.checked` clearing and the
  `mcp.finding` attention line.
- `cli/wuwei/commands/init.py:131, 151-156`: delete `_register_mcp`; `_finish` returns what it
  returned before the MCP call (0 on success).
- `cli/wuwei/commands/event.py:30-31`: delete the `mcp.*` producer rows. An old event stays
  readable.
- `cli/wuwei/signal.py:16, 52-55`: delete `'mcp.decided'` from `SILENT` and the `mcp.finding`,
  `mcp.checked` tiers.
- `cli/wuwei/state.py:242`: delete `STATE_PRODUCERS['mcp']` (`tests/test_state_allowlist.py`
  pins the table).
- `cli/wuwei/commands/config.py:103-107`: delete the `scanner.mcp.block` lines.
- `cli/wuwei/guards/protect_state.py:108-110`: delete the `ziran` hint branch (the LEFT row
  text); the `('ziran',)` protected tail (73) stays, so old registry files stay records and the
  write falls to the generic hint until part 24 removes the files.
- `cli/wuwei/integrity.py`:
  - `registered` (72-73): the default comes from the schema, not `mcp.DEFAULTS`;
  - delete `HOST_TERMINAL` and `_host_confirm` (372-393) **[after 16]**; `reconfirm` keeps its
    `confirm` parameter (its tests pass a callable) and the Owner step path.
- `cli/wuwei/decision.py` **[after 16]**: keep `widget`, `gate`, `naming`, `answered` and the
  imports they need (`re`, `Path`, `workspace`, `verdict.active_text`); delete the rest
  (`FIELDS`, `DECISION_ID`, `ENGINEERING`, `LENSES`, `OPTION_COLUMNS`, `OPTIONAL`, `STATUS_QUO`,
  `CLASSES`, `NO_RECOMMENDATION`, `table`, `number`, `options`, `_scored`, `evaluate`,
  `_explained`, `first`, `lens_lines`, `card_hash`, `record_widget`, `option_id`, `today_path`,
  `set_outcome`, `owner_confirm`, `no_card`, `decided_record`, `owner_record`, `write`).
  Docstring: "Card helpers for the morning and close gates, and readers of past days' D-n
  records."
- `cli/wuwei/guards/answers.py` **[after 16]**: `record_gate` keeps the Owner step branch and
  returns after it; delete the `DECISION_ID`/`today_path` import, the planner-session check and
  the `gate_asked` write. Docstring drops the D-n records.
- `cli/wuwei/sessions.py` **[after 16]**: delete `caller` (30-35) and `gate_topics` (38-46).
  `current`, `card_topic`, `owner_card`, `owner_topic`, `owner_answer` and `needs_owner` stay.
- `cli/wuwei/telemetry.py:36, 49`: `AREAS` and `OWNER_KINDS` are stored-week vocabularies
  (`tests/test_telemetry.py:128` pins `AREAS`); keep both unchanged (Assumption 3).

## Files to edit, tests (about 24)

- `tests/conftest.py:1, 7`: drop `from wuwei import mcp` and its docstring line; keep the
  `isolated_mcp_home` fixture (it clears environment variables).
- `tests/test_agent_launch.py`: delete `test_mcp_gate_is_its_own_guard_record` (589),
  `test_mcp_gate_off_without_scanner` (610), `test_hook_denies_launch_on_the_mcp_gate` (621).
- `tests/test_brief.py`: delete `test_mcp_unmeasured_in_brief_header` (492).
- `tests/test_doctor.py`: the `ws` fixture (71) drops `record(root)` (102) and the `record`
  helper (126-131) and `DIGEST` (29); `test_fix_allow_list_is_pinned` (177) drops
  `'mcp-reports'`; `test_gates_rows` (487) drops the `mcp gate` assert; delete
  `test_gates_without_scanner` (502), `test_gates_mcp_servers` (517),
  `test_answered_cards_row` (543), `test_unapproved_server_is_ok` (751), `legacy_reports`
  (1013), `test_mcp_reports_migration` (1028) and `test_mcp_reports_migration_bound_to_preview`
  (1039); `test_trial_failures_then_clean` (724) and `test_fix_applies_only_the_allow_list`
  (869) drop their `mcp` rows.
- `tests/test_next.py`: `test_morning_path` (126) has no `mcp` row (red first: assert the row
  after `pr-flow` is `lead`); `test_a_once_row_is_done_when_its_command_ran_not_when_returned`
  (701) uses the `pr-flow` row instead of `mcp`.
- `tests/test_path_day.py:139` and `tests/fakes/day.py` if it answers `mcp check`: drop the
  call.
- `tests/test_metrics.py:374-383`: the seeded `next.action` uses `pr-flow`.
- `tests/test_protect_state.py:846-856`: the `.wuwei/ziran/...` write expects the generic state
  hint, not `wuwei mcp decide`.
- `tests/test_quiet_sweeps.py`: delete `test_warnings_clear_pr_action_and_mcp_finding` (109).
- `tests/test_reasons.py`:
  - the `fresh` fixture (232) stops patching `init._register_mcp`;
  - delete the LEFT rows naming 18 (`decision.py`, `mcp.py`, `commands/doctor.py`,
    `guards/protect_state.py`, both `integrity.py`);
  - red first: the `_host_confirm` scan (349-351) becomes `assert not {rel for rel, source in
    _sources() if '_host_confirm' in source or '/dev/tty' in source}`.
- `tests/test_signal_status.py:333`: drop the three `mcp.*` kinds from `expected`.
- `tests/test_workspace.py`: delete `test_init_without_scanner_exits_0` (79); the defaults at
  220-221 hold only `plugins_file`; drop the `scanner.mcp` rows of
  `test_unknown_key_without_known_line` (386-387).
- `tests/test_config_transition.py`: `WARNING` (25) and
  `test_unknown_key_warns_with_the_nearest_key` (54) use another nested typo
  (`scanner.severity_treshold`); add the four retired keys to
  `test_upgrade_removes_and_reports_retired_keys` (SC-003).
- `tests/test_guard_mutation.py:16-17, 151-154`: delete the `check_mcp` probe row and branch.
- `tests/test_telemetry.py`: unchanged (stored rows); run it.
- `tests/test_adapters.py:102`: delete the `('scanner', 'mcp', ...)` CALLS row.
- `tests/test_env_credentials.py:230, 396, 719`: stop patching `init._register_mcp`.
- `tests/test_integrity.py` **[after 16]**: delete `test_host_confirm_asks_yes_or_no` (552) and
  `test_host_confirmation_without_a_terminal_names_the_owner_action` (883); check
  `test_checkout_legacy_confirmation_needs_new_host_confirmation` (727) does not call
  `_host_confirm`.
- `tests/test_sessions.py`: delete `test_caller_reads_the_planner_from_state` (416).
- `tests/test_answers.py`: delete `test_record_gate_notes_asked_decisions` (45); red first: an
  AskUserQuestion with header `D-1` records no `gate.asked`.
- `tests/test_decision.py` **[after 16]**: delete every case of the deleted functions; keep
  (or move to `tests/test_plan.py`) the `widget` and `naming`/`answered` cases. If nothing is
  left, delete the file.
- String fixtures that only quote `$W mcp check` as a command shape
  (`tests/test_protect_state.py:721`, `tests/test_shell.py`, `tests/test_parser_warns.py`):
  re-text to `$W next` only where part 17 left them and a test reads the command list.

## Files to edit, governance and docs (14, plus the generated agents if a charter changes)

- `templates/workspace/config.toml:127-137`: `[scanner.mcp]` keeps `plugins_file` and its
  comment ("Installed plugin registry v2, read to find installed plugins").
- `skills/wuwei-retro/SKILL.md:8, 10`: the example command becomes `wuwei next`; the widget
  sentence names `wuwei doctor --fix --widget` only.
- `docs/specs/2026-09-24-wuwei-design.md`:
  - 5.8 (708-709): drop "and the MCP registry cards keep their records until ...";
  - 5.10 (870): the plugins file key stays `scanner.mcp.plugins_file` (no edit unless the
    sentence names the gate);
  - 5.13 (917): `mcp.decided` stays only as a past-day kind;
  - 7 (1422-1431): S3 becomes "S3. MCP audit and drift: retired (owner, 2026-10-11, #789)";
    1436 says "S2 and S4";
  - 8 (1474): scanner port drops `mcp(servers)`;
  - 9.1 (1557-1558): drop "the MCP launch gate" from the still-blocks list;
  - 13 (1648) and 14 Q2 (1660-1661): drop S3.
- `docs/site/reference.md`: the `bin/wuwei mcp` Commands row (34), the host-terminal table row
  (410), 94, 209, 253, 261, 380 and 382.
- `docs/site/configuration.md`: 13 (`[scanner.mcp]` row keeps `plugins_file`), 72, 190 and
  the "MCP registry checks (S3)" section (361-466) reduced to the `plugins_file` sentence.
- `docs/site/security.md`: 5, 9, 42, 51, 62, 66-68 (one copy of the paragraph, without
  `mcp check`), 79.
- `docs/site/concepts.md`: 163, 186.
- `docs/site/recovery.md`: 24-31 and 112-116 go.
- `docs/site/integrity.md:9-10`, `docs/site/adapters.md:18`.
- `README.md`: 34; 259-260 (the protocol credit names what WUWEI still reads, or goes).
- `scripts/headless_e2e.py:307, 393`: drop "Run mcp check,".
- Charters: none name the gate (the `agent_surface` "MCP config" flag stays).

## RETIRED

`workspace.RETIRED` gains `scanner.mcp.project_file`, `scanner.mcp.user_file`,
`scanner.mcp.timeout_seconds`, `scanner.mcp.block` (the base has #799's `RETIRED`).

## Risks

- **Order.** Deleting `_host_confirm`, `owner_confirm` and the D-n library before part 16 would
  break `drafts.py` and `commands/outbound.py`. The batch base already holds part 16; the
  builder confirms with `grep -rn "_host_confirm\|owner_confirm\|gate_topics" cli` before
  deleting.
- **`next` once-rows.** `test_a_once_row_is_done...` used `mcp` as its example once-row; it
  must keep testing the rule on `pr-flow`, not lose it.
- **Old files.** Registry files and `.wuwei/ziran/` stay on disk and stay write-protected.
- **Telemetry.** `AREAS` keeps `'mcp'` for stored weeks; no live guard reports that area.

## Handoff

- Part 24: `init --upgrade` removes the obsolete registry files and `.wuwei/ziran/`, then the
  `('ziran',)` protected tail; it may rename `scanner.mcp.plugins_file`.
- Part 20: `tracker._entries` reads `decision.decided` events and `decision.naming`; after this
  part no producer writes `decision.decided`, so part 20 drops that branch.
