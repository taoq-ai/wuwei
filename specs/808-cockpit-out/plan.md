# Implementation Plan: delete the cockpit (board, dashboard, menu bar, brief packs)

**Branch**: `808-cockpit-out` | **Date**: 2026-10-11 | **Spec**: [spec.md](spec.md)

**Input**: `specs/808-cockpit-out/spec.md`. Line numbers are at main `221f1f2`; recheck after the
rebase onto parts 1 to 4.

## Summary

Delete four command modules (`board`, `dashboard`, `signal`, and the brief-pack half of
`brief`), the `brief_pack` module, the plugin's `mcpServers` entry, the dashboard and SwiftBar
templates, `init --menu-bar`, two config keys, two state keys, two event kinds and one metric,
with the tests that cover only them. Keep the classifier, the calendar port and telemetry.
Reword the docs, charters, skill and design spec so none mentions the cockpit.

## Technical Context

**Language/Version**: Python 3.11+, stdlib only at runtime.
**Primary Dependencies**: none added.
**Storage**: day `state.json` and `events.jsonl` (no format change; old keys and kinds are left
unread).
**Testing**: pytest (dev only); run only the touched test files; CI is the gate.
**Target Platform**: the WUWEI Claude Code plugin CLI.
**Project Type**: CLI plus plugin manifest.
**Performance Goals**: none; fewer modules on the `--help --all` path.
**Constraints**: no emojis, no em-dashes, no absolute local paths, no client or people's names.
**Scale/Scope**: 14 files deleted, 1 test file renamed and trimmed, about 45 files edited
(9 of them `agents/*.md`, rebuilt).

## Constitution Check

- I stdlib only: deletion only. Pass.
- II three-state exits: `brief` keeps exit 2 for a malformed call; no exit changes. Pass.
- III one behaviour, one function: `signal.classify` stays the one classifier; the deleted
  `signal classify` command was a second entry to it. Pass.
- IV test first: the behaviour changes (`brief` forms, `doctor` own-server rows, schema
  defaults, plugin manifest) get their test edited first and seen failing; pure deletions delete
  their tests with the code. Pass.
- V ponytail: deletion; no replacement surface. Pass.
- VII security: the dashboard's Host-header check and the pack's symlink refusals protect only
  the deleted servers and files; nothing they guarded remains. The MCP registry gate is
  untouched. Pass.
- Workflow, invariant rule: no guard or decision rule changes; no invariant row. Pass.
- Design spec amended only by its owner: #789 is the owner's instruction; passages are marked
  retired "(owner, 2026-10-11, #789)". Pass.

## Units removed and why (rule of the pass)

| Unit | (a) or (b) | Where its job is now |
|---|---|---|
| `wuwei board` MCP server, `wuwei_board` tool, `ui://wuwei/board.html`, `mcpServers.cockpit` | (a) a view the planner is told to show and read for status | `wuwei next`, `wuwei status --line` |
| `wuwei dashboard` loopback server, `cockpit_snapshot`, `board_snapshot`, `templates/dashboard.html` | (a) owner view | `next`, `status`, `report`, `drafts`, `decision show` |
| SwiftBar plugin, `init --menu-bar` | (a) owner view of `status --json` | `status --line` |
| brief packs, defend drill, `brief_packs`, `brief_drill`, `brief_drill_score`, `brief.lead_minutes`, `brief.style` | (a) owner briefing, no loop step reads it | `report` |
| `wuwei signal classify` | (a) plumbing entry nobody calls | `signal.classify`, read in-process by `status` |
| doctor `mcp <name>` rows for WUWEI's own servers | (a) informational, dead with no own server | none |
| skill sentence "show the board once at the start of the day" | (a) makes the model reason about a process view | none |

No (b) unit found: none of these stops a seat without a brief, a gate on the wrong head, a
verdict missing rows, a fix round past budget, a PR raised outside WUWEI or a merge outside
policy. The `cockpit_snapshot` call to `decision.lint_clarification` raised on a malformed C-
record only inside the view; `decision lint` and `decision.lint` keep that check.

## Files to delete (14)

- `cli/wuwei/commands/board.py`
- `cli/wuwei/commands/dashboard.py`
- `cli/wuwei/commands/signal.py`
- `cli/wuwei/brief_pack.py`
- `templates/dashboard.html`
- `templates/swiftbar/wuwei.1m.sh` (and the empty directory)
- `tests/fixtures/swiftbar/clean.json`, `invalid.json`, `nudge.json`, `page.json`,
  `unmeasured.json` (5; `nudge.json` may already be gone after #801)
- `tests/test_board_mcp.py`, `tests/test_dashboard.py`, `tests/test_swiftbar.py`

Rename and trim (1): `git mv tests/test_brief_pack.py tests/test_calendar_tts.py`. Keep only the
cases that cover kept adapters: `test_say_accepts_rate_keyword` (113), `test_ics_parser_and_secret_redaction`
(146), `test_ics_rejects_error_body` (211), `test_ics_tzid_uses_local_zone` (223). Replace the
`root` fixture with a minimal one (empty `.wuwei/config.toml`, `WUWEI_WORKSPACE`, `WUWEI_NOW`);
delete `CONFIG`, `day`, `daily`, `section` and every pack, answer and drill case. Module
docstring: "Calendar ICS and speech adapter contract tests." `tests/fixtures/calendar/meeting.ics`
stays.

## Files to edit: code and manifest

- `.claude-plugin/plugin.json`: delete the `mcpServers` object (24-34) and the comma before it.
- `cli/wuwei/commands/brief.py`: drop `brief_pack` from the import (6), the `--meeting` argument
  (13), the `pack` and `answer` branches (26-31); the message (33) becomes
  `'expected ROLE ITEM NAME'`.
- `cli/wuwei/commands/init.py`: delete the `--menu-bar` argument (35) and the `menu_bar` branch
  (46-57); line 43 tests only `upgrade`. `shlex` stays (173 uses it).
- `cli/wuwei/commands/setup.py:484`: drop `menu_bar=False` from the `SimpleNamespace`.
- `cli/wuwei/commands/doctor.py`: in the gates section (528-535), the `scanner == 'none'` branch
  returns `rows` with no own-server rows (delete the manifest read and the list comprehension);
  drop imports left unused (check `integrity`, `json`). Docstring at 933: "the Outcome line for
  readers of the record" in place of "for the board".
- `cli/wuwei/commands/event.py:80`: delete the `brief.pack` and `brief.answer` entries.
- `cli/wuwei/commands/why.py:83`: docstring ends "never reaches stdout." (drop "or the board").
- `cli/wuwei/state.py:265`: delete the `brief_packs` and `brief_drill` entries.
- `cli/wuwei/signal.py:9`: delete `'brief.pack', 'brief.answer'` from `SILENT`.
- `cli/wuwei/metrics.py:851-852`: delete the `brief_drill_score` line pair.
- `cli/wuwei/workspace.py`: `SCHEMA['brief']` (123-125) drops `lead_minutes` and `style`; the
  comment at 642 reads "so doctor and why stay read-only". If `RETIRED` exists (after #799),
  add `'brief.lead_minutes'` and `'brief.style'`.
- `templates/workspace/config.toml` (166-172): `[brief]` keeps `remote`, `prior_branch_pattern`,
  `full_path_patterns`; delete `lead_minutes` and the `[brief.style]` table.
- Only if part 3 (#800) has not removed them: `cli/wuwei/__main__.py` GROUPS (32, 36) drops
  `dashboard`, `board`, `signal`; `cli/wuwei/commands/__init__.py` drops `'board'` from
  `READ_ONLY` and `'dashboard'`, `'signal classify'` from `WRITES`.

Not edited: `cli/wuwei/signal.py` beyond line 9, `cli/wuwei/commands/status.py`,
`cli/wuwei/mcp.py`, `cli/wuwei/telemetry.py`, `cli/wuwei/commands/{telemetry,dora}.py`,
`cli/wuwei/registry.py`, `adapters/` (tts, transcripts and calendar stay).

## Files to edit: tests

Behaviour tests changed first (see them fail, then change the code):

- `tests/test_workspace.py:271`: the expected `brief` defaults drop `lead_minutes` and `style`.
- `tests/test_doctor.py:557-568` (`test_gates_without_scanner`): delete the manifest rewrite
  (560-562) and the `mcp cockpit` assertion (566-567); the comment (558) ends "the gate is off"; add `assert not [r for r in rows if
  r['section'] == 'gates' and r['name'].startswith('mcp ') and r['name'] != 'mcp gate']`
  (the own-server rows are gone). Keep the gate-ok and no-`mcp docs` assertions.
- `tests/test_signal_status.py`: delete `test_signal_cli_reads_event_from_stdin` (111-115);
  drop `'brief.pack'` and `'brief.answer'` from the expected tier table (335).
- One new case, in `tests/test_cli.py` (or the nearest CLI test): `main(['brief', 'pack'])`
  returns 2 and stderr names `expected ROLE ITEM NAME`; `main(['dashboard'])`, `main(['board'])`
  and `main(['signal', 'classify'])` raise `SystemExit` with code 2; and
  `'mcpServers' not in json.loads(plugin.json)`.

Deletions with the code they cover:

- `tests/conftest.py:8`: delete the `board` import (the `mcp` import stays).
- `tests/test_dispatch.py:1633, 1653-1654`: delete the `board` import and the board row
  assertion; the ticket id on the owner surface is covered by `tests/test_next.py:524`.
- `tests/test_drafts.py:378-389`: delete `test_cockpit_lists_pending_drafts_read_only`; in
  `test_malformed_drafts_fail_closed` (392-401) delete the `cockpit_snapshot` import and its
  `pytest.raises` block; the `drafts` exit 2 and `metrics.collect` raise stay.
- `tests/test_doctor.py:1026, 1043`: delete the `cockpit_snapshot` import and assertion; the
  per-record `decision.answered` and `Outcome:` assertions above it cover the supersede.
- `tests/test_watch.py:904, 927`: delete the `cockpit_snapshot` import and assertion;
  `steward.decision_queue` (928-929) covers the queued record.
- `tests/test_integrity.py:460`: `'cli/wuwei/commands/board.py'` becomes
  `'cli/wuwei/commands/next.py'` (a sample packaged command file).
- `tests/test_operator_records.py:62-65`: delete the `brief pack` block; line 70 checks
  `(report, line)`.
- `tests/test_mcp.py:775`: comment reads "WUWEI's signed plugin.json declares no project
  .mcp.json, so neither the install nor a managed checkout carries one for S3 to measure."
  No other change.
- `tests/test_docs.py`, only where part 1 left them: drop
  `'docs/site/concepts.md#cockpit-and-board'` (836) and `'Cockpit and board'` (865) from their
  tuples; drop `'MCP Apps'` from the credits tuple (1186-1187); `('record', 'wuwei_board')`
  (1305) becomes `('record',)`.
- Only if part 3 has not removed them: `tests/test_cli.py:325` drops `'signal', 'board'` from
  the set; `tests/test_cli_known_command.py:55` drops the `(['board'], True)` row.
- Only if part 4 has not deleted the file: `tests/test_nudges_mode.py:170-185`, delete
  `test_board_and_doctor_follow_the_mode`'s board half (172 import, 174-177), keeping the doctor
  assertions.

## Files to edit: charters, skills, agents

- `charters/planner.md:24`: "answer the owner from `wuwei next` and `wuwei status --line`".
- `charters/_common-authoring.md:17`: "(decision records, PR bodies, drafts, retro summaries
  and digests)".
- `skills/wuwei-plan/SKILL.md:8`: delete the sentence "When the `wuwei_board` tool is
  available, show the board once at the start of the day; nothing depends on it."
- `agents/*.md` (9): never by hand; run `bin/wuwei agents build`.

## Files to edit: docs

- `README.md`: delete the cockpit bullet (32); delete the MCP Apps acknowledgement (270-271);
  the Model Context Protocol entry (268-269) reads "the server configuration format the MCP
  registry gate reads".
- `NOTICE`: delete the MCP Apps block (51-55); Model Context Protocol "Used:" line reads "the
  server configuration format the MCP registry gate reads (cli/wuwei/mcp.py)."
- `docs/site/concepts.md`: delete `## Cockpit and board` (542-547); 268 "the retro's Tickets
  seats filed section lists who filed it" (drop the board's table).
- `docs/site/daily.md`: delete the `wuwei_board` paragraph (535-538); 270 delete "The board
  shows the item as `PR-12 (adopted)`."; 374 "`wuwei next` and the loop DM show the ticket id".
- `docs/site/reference.md`: delete the `board` (12), `dashboard` (20) and `signal` (70) rows;
  148 delete "The cockpit displays pending drafts ... no POST actions."; 428 delete the
  `wuwei_board` sentence.
- `docs/site/configuration.md`: 13 drop `` `[brief.style]` ``; 247 tts row "Speech output port.
  No command calls it since #789 part 5."; 249 transcripts row "Meeting transcript port. No
  command calls it since #789 part 5."; delete rows 253-255; delete the brief pack paragraph
  (263-269); 492 end the sentence at "shows the gate ok."; 496-501 replace the own-server
  sentences with "WUWEI declares no MCP server of its own." and keep "A `.mcp.json` added to
  the install, one in a workspace or repo, and any other plugin's servers are discovered and
  checked like any other."; 616 drop "the cockpit,".
- `docs/site/integrity.md:9-10`: "That includes `.claude-plugin/plugin.json`, which declares
  no MCP server; `bin/wuwei mcp check` measures attached servers only." (keeps the `mcp check`
  phrase a test reads).
- `docs/site/index.md:10`: drop "and the board" ("... the listener and the heartbeat").
- `docs/site/recovery.md:116`: "the finding stays open until".
- `docs/site/agent.md:56`: only if the guide block is still there, regenerate it between the
  markers from `guide.text()`.
- `docs/specs/2026-09-24-wuwei-design.md`: 92 drop ", dashboard.html"; 239-240 "`wuwei next`
  shows one row per owned PR ..."; 5.9 heading adds "(cockpit, menu bar and briefings retired:
  owner, 2026-10-11, #789)"; 1039 "classified once by `signal.classify`"; the Cockpit (1066-1069)
  and Menu bar (1070-1072) bullets and the Briefings block (1076-1092) are replaced by one
  line "Cockpit, menu bar and briefings: retired (owner, 2026-10-11, #789)."; 1074 drop "plus
  the briefing pack and"; 1520 drop ", and the board lists the day's created tickets per item";
  1591 and 1714 "`wuwei next`" in place of "The board,"/"The board and"; 1920 and 1922 tts and
  transcripts rows add "(no caller since #789 part 5)"; delete the `menu_bar` row (1923); 1955
  drop "in the cockpit or".

Not edited: `CHANGELOG.md`, `specs/*` (history), `.specify/memory/constitution.md`.

## RETIRED at rebase

The base (`221f1f2`) has no `workspace.RETIRED`. After #799 merges, add to it:

- `'brief.lead_minutes'`
- `'brief.style'`

## Verification

- `grep -rnE "wuwei_board|cockpit|dashboard|swiftbar|SwiftBar|menu.bar|brief_pack|brief pack|briefing pack|defend drill|brief_drill|signal classify|ui://" cli adapters hooks charters skills agents templates docs/site README.md NOTICE .claude-plugin`
  returns nothing (the only allowed `board` hits are the tracker's GitHub Projects `board`).
- `grep -rn "board" docs/site charters skills agents | grep -v "tracker.board\|Projects"`
  returns nothing.
- `bin/wuwei agents check` is clean after `agents build`.
- Run every touched test file (tasks.md T014) with `python -m pytest -q`. No full suite
  locally; CI is the gate.

## Risks for the builder

- Rebase onto parts 1 to 4 first. Parts 3 and 4 delete or rewrite GROUPS, READ_ONLY/WRITES,
  `test_cli_known_command.py`, `test_nudges_mode.py`, the guide block and docs pins; part 4
  edits board, dashboard and SwiftBar files that this part deletes (resolve by deleting).
- `test_brief_pack.py` holds the only ICS parser tests; keep them in the renamed file.
- Do not touch telemetry: `telemetry.ADAPTERS` must keep `tts` and `transcripts`.
- `tests/test_mcp.py` names a fixture server `cockpit`; it tests third party servers and stays.
