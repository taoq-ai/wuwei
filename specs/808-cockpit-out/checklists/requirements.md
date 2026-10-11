# Requirements checklist: delete the cockpit

**Purpose**: check the spec and plan before implement. **Feature**: [spec.md](../spec.md)

## Completeness

- [x] CHK001 Every unit removed is named with (a) or (b) and where its job lives now (plan table); no (b) unit.
- [x] CHK002 Every importer of the deleted modules is listed: `board` (conftest, test_dispatch,
  test_nudges_mode, test_board_mcp), `dashboard` (board, test_drafts, test_doctor, test_watch,
  test_dashboard), `brief_pack` (commands/brief, dashboard), `signal` command (test_signal_status).
- [x] CHK003 Every string the deleted units own is listed: state keys, event kinds, `SILENT`
  entries, the metric, the config keys, the manifest entry, help groups and command sets.
- [x] CHK004 Charters, skills, agents, hooks, CI workflows, scripts, templates and docs were
  searched; hits are listed in plan.md.
- [x] CHK005 Template keys removed match the schema keys removed (`brief.lead_minutes`,
  `brief.style`), and both are named for `RETIRED`.

## Clarity

- [x] CHK006 The new `brief` error text and the doctor row behaviour are written out.
- [x] CHK007 Each docs edit names its line and its replacement text.

## Consistency

- [x] CHK008 Telemetry, DORA, the classifier, the calendar port and the MCP registry gate are untouched.
- [x] CHK009 No test is loosened: each removed assertion covered deleted code; kept behaviour
  keeps a test (ICS and `say` cases kept; `next` ticket id covered at tests/test_next.py:524).
- [x] CHK010 Design spec passages are marked retired under the owner's #789 instruction.

## Dependencies

- [x] CHK011 Order with parts 1 to 4 is stated, with the edits to skip after a rebase.
- [x] CHK012 The tts and transcripts port removal is recorded under Deferred, to be filed as its own issue.
