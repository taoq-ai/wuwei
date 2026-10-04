# Tasks: read-only MCP tools by any word, unknown tools follow the posture, Slack writes take the draft path

**Input**: `specs/469-mcp-reads/` (spec.md, plan.md, research.md)

Test first: run each test task with the command given and see it fail for the expected
reason before its implementation task starts. Run from the repository root with the
interpreter your task names. No absolute local paths, emojis or em-dashes in any file.

## Phase 1: US1, reads pass whatever their word order

- [X] T001 Test, `tests/test_outward.py`: add `test_name_words`, a table over
  `wuwei.guards.outward.tool_kind` (plan Tests; spec Edge Cases): `conversations_history`,
  `channels_list`, `conversations_search_messages`, `slack_get_channel_history`,
  `getConfluencePage` and `mcp__gmail__get_message` read; `conversations_add_message`,
  `chat_postMessage`, `sendEmail`, `push_files`, `mark_all_notifications_read` write;
  `frobnicate`, `slack_readwrite`, `resolve-library-id` unknown (all as `mcp__<server>__`
  names). Run `python -m pytest -q tests/test_outward.py -k name_words` (fails: no
  `tool_kind`).
- [X] T002 Implement `WRITES`, `LEADING`, `READS` and `tool_kind` in
  `cli/wuwei/guards/outward.py` (plan Design 1). Rerun T001; pass.
- [X] T003 Test, `tests/test_outward.py`: add `RECORDED` (research.md lists) and
  `test_recorded_server_tools` (plan Tests), and update the intended rows of
  `test_service_prefixed_mcp_reads` (`mcp__x__slack_read_thread`,
  `mcp__slack__slack_readwrite`, `mcp__x__readwrite` to 0). Run `python -m pytest -q
  tests/test_outward.py -k "recorded or service_prefixed"` (fails: noun-first reads such as
  `conversations_history` get 2 with the bare hint).
- [X] T004 Implement the first unmatched branch of `_check` in
  `cli/wuwei/guards/outward.py` with `tool_kind` (plan Design 2). Rerun T003; the read rows
  pass, the write and unknown rows still fail until Phase 2 and 3.
- [X] T005 Test, `tests/test_hooks.py`: add the `mcp-read` case to
  `test_hook_imports_no_unused_stdlib` (plan Tests). Run `python -m pytest -q
  tests/test_hooks.py -k no_unused_stdlib` on the T004 tree; it must pass. Then confirm it
  is a real check: undo the T004 edit by hand, rerun, see it fail on the return code, then
  redo the edit.

## Phase 2: US2, writes take the draft path and name the channel

- [X] T006 Test, `tests/test_outward.py`: add `test_unmatched_write_names_the_line` and
  `test_invalid_mcp_name` (plan Tests), and update `test_real_mcp_write_names` (rows
  `mcp__unknown__target_lookup` 0 and `mcp__unknown__anything` 0, the code-2 assertion on
  `config set outward.tool_patterns` plus the tool name). Run `python -m pytest -q
  tests/test_outward.py -k "unmatched_write or invalid_mcp or real_mcp_write"` (fails: the
  bare hint names no line; `anything` still 2).
- [X] T007 Implement `_unmatched` in `cli/wuwei/guards/outward.py` (plan Design 3) and call
  it from the second unmatched branch of `_check`. Rerun T006; pass except
  `mcp__slack__edit_message` until T009.
- [X] T008 Test, `tests/test_outward.py`: change `mcp__slack__edit_message` in
  `test_real_mcp_write_names` to 1 and add the `conversations_add_message` and
  `slack_add_reaction` draft rows to `RECORDED` if not already there. Run `python -m pytest
  -q tests/test_outward.py -k "real_mcp_write or recorded"` (fails: both get 2 with the
  config line, not the draft).
- [X] T009 Implement the Slack default in `cli/wuwei/workspace.py` (plan Design 5). Rerun
  T008; pass.
- [X] T010 Test, `tests/test_outward.py`: add `test_why_shows_channel_and_draft` and change
  the `test_send_or_draft` assertion to `a draft for the owner to send` (plan Tests). Run
  `python -m pytest -q tests/test_outward.py -k "why_shows or send_or_draft"` (fails: the
  rule is the bare draft text without the channel).
- [X] T011 Implement the channel in the draft refusal in `_check`,
  `cli/wuwei/guards/outward.py` (plan Design 4). Rerun T010; pass.

## Phase 3: US3, unknown tools follow the posture

- [X] T012 Test, `tests/test_outward.py`: add `test_unknown_tool_recorded_once` and
  `test_unknown_tool_outside_workspace` (plan Tests; spec US3 scenarios 1 to 5). Run
  `python -m pytest -q tests/test_outward.py -k unknown_tool` (fails if T007 left out the
  posture branch; if T007 already wrote it in full, revert that branch to `return CLEAN,
  ''`, see the event and strict assertions fail, then restore it in T013).
- [X] T013 Implement the posture branch of `_unmatched` in `cli/wuwei/guards/outward.py`
  (plan Design 3, from `if policy is outward.check_tier`). Rerun T012; pass.

## Phase 4: acceptance

- [X] T014 Test, `tests/test_outward.py`: add `test_probe_tools`, the seven probes plus
  `mcp__acme__frobnicate` through `commands.hook.run` under observe, guarded and strict
  (plan Tests; spec US1 scenarios 1 and 2, US2 scenario 1, US3 scenarios 1 and 3). Run
  `python -m pytest -q tests/test_outward.py -k probe_tools`; it must pass on the T013 tree.
  Confirm it bites: set the Slack default back to main's string, see the
  `conversations_add_message` cases fail, restore.

## Phase 5: polish

- [X] T015 Docs: `docs/site/security.md` paragraph and `docs/site/configuration.md:383`
  row (plan Design 6).
- [X] T016 Run `python -m pytest -q tests/test_outward.py tests/test_hooks.py
  tests/test_reasons.py tests/test_guard_mutation.py tests/test_profiles.py
  tests/test_outbound.py tests/test_canary.py tests/test_why.py`, then the full suite
  `python -m pytest -q`. All pass. Grep the changed files for em-dashes, emojis and
  absolute local paths and remove any.
