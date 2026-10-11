# Implementation Plan: delete the docs system

**Branch**: `b7-leftovers` | **Date**: 2026-10-11 | **Spec**: [spec.md](spec.md)

Line numbers are at d60253b8. Part 16 (#838) lands before this batch **[after 16]**: it deletes
`drafts.py` (and its `docs.record` call), `commands/outbound.py`, and `outward.classify` with
its `docs.auto` branch, and trims `docs.py`'s draft branches. Part 18 (#840) runs first on this
branch: `commands/doctor.py` and `commands/next.py` lines shifted; locate code by function name.

## Summary

Delete the docs obligation, its quality-gate wall, the page writer, the day page publisher, the
docs adapters and port, and the `[docs]` config. Move the one helper another module imports
(`docs._sections`, used by `specmode.governed`) first.

## Technical Context

Stdlib-only Python 3.11+, pytest dev-only. Net deletion: about 900 lines of code and adapters,
1,000 of tests. Run only the touched test files.

## Constitution Check

- I: nothing added. II: no guard changes. III: one less writer. IV: red tests first for the
  receive and lint changes. V: deletion. VII: the quality gate keeps its findings; the security
  floor (credential scrubbing) stays.

## Process control: what each removed unit was

| Unit | Kind | Where its job goes |
| --- | --- | --- |
| Docs obligation (`required`, `unmet`, `shown`, `command`, `assign`, `plan set docs=`, `why` `docs`, `next` `docs` row) | (a) the planner and seats reason about a docs value | nowhere |
| Quality receive refusal and the lint's `DOCS_MISSING` | (a) a wall at the quality gate over a process value | nowhere; the sentinel reviews docs changes as code (`DOC` class) |
| Quality charter step 7, builder `Docs:` line and charter sentence | (a) | nowhere |
| Page writer, publisher, close lines, report section | (a) | nowhere |
| `adapters/docs/`, the `docs` port, `adapters.docs`, doctor `docs` row, config credential rows | (a) | nowhere |

No (b) check is lost: none of these is in the "process control kept" table.

## Files to delete (2 modules, 1 adapter directory, 2 test files, 1 fixture)

- `cli/wuwei/docs.py`, `cli/wuwei/commands/docs.py`
- `adapters/docs/` (`_lines.py`, `confluence.py`, `markdown.py`, `none.py`, `notion.py`)
- `tests/test_docs_system.py`, `tests/test_docs_port.py`, `tests/fixtures/docs/recordings.json`

## Files to edit, code (21)

- `cli/wuwei/specmode.py:347`: `governed` imports `_sections` from `wuwei.docs`; move the
  helper (docs.py:320-322) into `specmode.py` first.
- `cli/wuwei/registry.py:62`: drop the `docs` port.
- `cli/wuwei/workspace.py`: SCHEMA `docs` (102-107); the `adapters.docs` mirror (730); the
  `docs.system` special case in adapter validation (773-776); the `docs.auto` comment (182);
  `RETIRED` gains `'docs'`, `'adapters.docs'`; bump `CONFIG_CACHE_VERSION` (642).
- `cli/wuwei/plan.py:78`: drop `'docs'` from the candidate empty-means-absent keys.
- `cli/wuwei/closing.py:266-267`: drop `docs.close(root)`.
- `cli/wuwei/dispatch.py:506-508` (`docs.exempt`) and `986-992` (the quality receive refusal).
- `cli/wuwei/brief.py:29-30` (the LIVE line drops "docs") and `560-563` (`Docs:` line).
- `cli/wuwei/report.py:150-153`: the `## Docs` section.
- `cli/wuwei/commands/report.py:20-21`, `cli/wuwei/commands/retro.py:16-17`: no publish; `run`
  returns its own code.
- `cli/wuwei/commands/plan.py:47-52, 90-92, 98-101`: `plan set <item> docs=` goes (help, branch,
  error text).
- `cli/wuwei/commands/why.py:29, 100-113`: the `docs` key and help word.
- `cli/wuwei/commands/next.py:231-237`: the `docs` row; an item at the gate gets `verdicts`.
- `cli/wuwei/commands/doctor.py:485-513, 769`: `_docs` and its call.
- `cli/wuwei/commands/config.py:159-160`: the docs credential requirement rows.
- `cli/wuwei/commands/event.py:82-83`: the `docs.*` producer rows.
- `cli/wuwei/state.py:350`: the `docs` item-field producer.
- `cli/wuwei/signal.py:29`: `docs.set`, `docs.written`, `docs.exempt` leave `SILENT`.
- `cli/wuwei/verdict.py`: `DOCS_MISSING` (135-139), the `docs` parameter and its refusal in
  `lint` (159-162, 211-213), `recorded_docs` (275-286) and its use in `lint_file` (321).
- `cli/wuwei/outward.py` **[after 16]**: any comment still naming `docs.auto`.
- `cli/wuwei/commands/shepherd.py`: help text, if part 16 left "docs" in it.
- Kept: `env.py` credential names, `telemetry.ADAPTERS['docs']`, the MCP `docs` channel.

## Files to edit, tests (about 16)

- `tests/test_adapters.py:103-104`: the docs CALLS rows.
- `tests/test_brief.py`: delete `docs_brief` (551), `test_quality_brief_copies_no_docs_value`
  (565), `test_builder_brief_has_the_docs_rule` (627), `test_no_docs_line` (632); port
  `test_builder_and_gate_briefs_name_the_live_read` (573) and
  `test_builder_and_gate_briefs_quote_the_approval` (592) to a plain brief helper; keep the
  ticket and spec half of `test_issue_acceptance_docs_recorded_after_the_brief` (751), renamed.
- `tests/test_dispatch.py`: delete the docs helpers and tests (1480-1538); red first:
  `test_quality_pass_needs_no_docs_value` with a former `[docs] system = "notion"`.
- `tests/test_doctor.py:1093-1128`: the docs row tests.
- `tests/test_next.py:469`: `test_docs_row` becomes "an item at the gate gets `verdicts`".
- `tests/test_why.py`: `live_item` (404) and the three `why --json` tests (421, 438, 444) drop
  the docs assertions; the redaction case moves to another field.
- `tests/test_verdict.py:768-790`: the docs lint cases go; red first: a finding "docs value
  missing" lints clean.
- `tests/test_state.py:783`: `test_docs_events_and_field_are_reserved`.
- `tests/test_signal_status.py:375-376`: drop the `docs.*` kinds.
- `tests/test_workspace.py`: 236, 274 (defaults), `test_docs_config` (460).
- `tests/test_config_set.py:274`: use another list key than `docs.publish`.
- `tests/test_env_credentials.py`: delete the docs params of
  `test_config_reports_missing_and_set` (285-286) and `test_docs_credentials` (755); keep
  `VARIABLES`.
- `tests/test_plan.py:983-985`: the candidate `docs` field.
- `tests/test_config_transition.py`: `[docs]` and `adapters.docs` in the retired-keys fixture.
- `tests/test_outward.py` **[after 16]**: any case left that drafts a docs port write goes; the
  MCP docs channel cases stay.
- `tests/test_agents.py`: green after `bin/wuwei agents build`.

## Files to edit, governance and docs (12, plus generated agents)

- `charters/sentinel-quality.md` (1.2.0 to 1.3.0): delete step 7, renumber.
- `charters/builder.md` (1.3.0 to 1.4.0): delete line 35.
- `bin/wuwei agents build` regenerates `agents/sentinel-quality.md`, `agents/builder.md`.
- `templates/workspace/config.toml:49-56`: the commented `[docs]` block.
- `docs/specs/2026-09-24-wuwei-design.md`: 5.12 heading gains "(retired: owner, 2026-10-11,
  #789)" and its body (1226-1337) becomes one line naming what stays (the `DOC` class, the goal
  gate for a docs-only diff); 4.1 row 177 drops "or docs (5.12)"; 8 row 1471 marked retired.
- `docs/site/reference.md`: 18-20, 43, 80, 400.
- `docs/site/configuration.md`: 19, 241-253, 273 (another example key), 322.
- `docs/site/concepts.md`: 118-126, 204.
- `docs/site/daily.md:252-256`; `docs/site/adapters.md:71-73`.
- `README.md:89`: the `docs` port row.

## RETIRED

`workspace.RETIRED` gains `docs` and `adapters.docs`.

## Risks

- `specmode.governed` breaks if `docs.py` goes before `_sections` moves (T001 first).
- `CONFIG_CACHE_VERSION` must bump, or a cached parse keeps the `docs` table for a run.
- Charter edits need `agents build`; never hand-edit `agents/*.md`.

## Handoff

- Part 24 rewrites the site; this part leaves no docs-system text there.
