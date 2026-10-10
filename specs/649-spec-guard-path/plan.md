# Implementation Plan: a scratch analysis.md is an ordinary write for WUWEI, and the builder knows why Claude Code refuses it

**Branch**: `649-spec-guard-path` | **Spec**: `specs/649-spec-guard-path/spec.md`

## Summary

The refusal the owner saw is Claude Code's built-in subagent report-file check (by basename,
in any directory), not a WUWEI guard. WUWEI's spec guard already decides by path. The change is
one regression test that pins the path-only decision, one charter sentence (and its generated
agent) that names the real cause, one docs sentence, and one charter test anchor. No runtime
code changes.

## Technical Context

Python 3.11+ stdlib only (constitution I). pytest dev-only. No new module, function, config
key, event kind or command. Tests run in process through `wuwei.commands.hook.run` with the
existing `tests/test_spec_mode.py` fixtures (`ws`, `item`, `write`, `hook`, `kinds`,
`FIXTURES`).

## Constitution Check

- I stdlib: nothing imported.
- II exits: unchanged; the test asserts exit 0 and the existing exit 2 refusal path.
- III one behaviour one function: the decision stays in `guards/spec.py check_edit` with
  `specmode.own` and `specmode.check`; one test pins it.
- IV test first: the regression test is green against the unchanged guard by design. Its red
  run is shown by a temporary name match in `check_edit` (spec Assumptions), reverted before
  the green run. The charter anchor test runs red before the charter edit.
- V simplicity: no hook for a write Claude Code already refuses in the tool; text changes only.
- VII security: no guard narrowed or widened.

## Design

### What must not change

- `cli/wuwei/guards/spec.py` (`_item`, `_target`, `check_edit`, `check_record`, `check_stop`).
- `cli/wuwei/specmode.py`: `OWN`, `own`, `check`, `STEPS` (the `analyze` row at lines 28 and
  29 keeps its text; `tests/test_spec_mode.py` asserts `bin/wuwei spec analysis a` in the
  brief line).
- `cli/wuwei/commands/spec.py` and `docs/site/reference.md` (the `spec` row is accurate).

### tests/test_spec_mode.py

One new test after `test_pre_tool_use_refuses_source_edits_until_the_spec`, named
`test_spec_guard_decides_by_path_not_by_file_name` (#649), reusing the `ws` and `item`
fixtures and the `write`, `hook`, `kinds` helpers:

1. Outside every worktree: for tool in `Write`, `Edit`, `hook('PreToolUse', write(ws,
   tmp_path / 'scratch/analysis.md', tool))` returns code 0 with `out.err == ''` and
   `out.out == ''`; afterwards `kinds(ws)` and `kinds(ws, 'hook.')` are empty.
2. Inside the worktree before the steps: `item / 'scratch/analysis.md'` and
   `item / 'scratch/notes.txt'` both return code 2 with the same stderr (the refusal does not
   depend on the name), and the stderr names `specify first`.
3. `item / 'specs/001-a/analysis.md'` (create `specs/001-a` first) returns 0 with no output.
4. With the steps through `tasks` present but `analysis.md` absent (copy
   `FIXTURES / 'speckit/specs'`, then unlink `specs/001-a/analysis.md`, as the `unanalysed`
   fixture does), a Write of `item / 'src/app.py'` returns 2 and its stderr names
   `bin/wuwei spec analysis a` (US2.1: the strict refusal at the `analyze` step carries the
   pointer).
5. With the full fixture present, `item / 'scratch/analysis.md'` returns 0.

Red evidence: add `if Path(path).name == 'analysis.md': return 1, 'x'` at the top of
`check_edit` after `_target`, run the test, see step 1 fail on code 2, remove the line.

### tests/test_charters.py

Extend the existing `test_amended_role_rules` style with one assertion block (a new small
test `test_builder_names_claude_codes_report_file_check`): `texts["builder.md"]` contains
`wuwei spec analysis <item>` and `in any directory`. Red before the charter edit (the second
anchor is missing).

### charters/builder.md

Replace the sentence "A subagent cannot write spec-kit's `analysis.md`: pipe the analyze
report to `wuwei spec analysis <item>`, which writes it, then commit it." with:

"Claude Code refuses a subagent's Write of a Markdown file named like a report (`analysis.md`,
`report.md`, `summary.md`, `findings.md`) in any directory; that check is Claude Code's, not a
WUWEI hook. Give a scratch file another name, such as `<item>-analysis.md`, and pipe spec-kit's
analyze report to `wuwei spec analysis <item>`, which writes it, then commit it."

Bump the frontmatter `version: 1.2.0` to `1.2.1` (init and doctor compare charter override
versions). Regenerate with `bin/wuwei agents build`; `tests/test_agents.py`
(`test_checked_in_agents_match_charters_and_allowlist`) checks the drift. Check the new text
against the `BLOCKING` lint in `tests/test_charters.py` (it uses no "with Bash" or "wait for"
phrasing).

### docs/site/configuration.md

Line 119 becomes: "A Claude Code subagent cannot write `analysis.md` itself: Claude Code
refuses a subagent's Write of a Markdown file named like a report, in any directory. A builder
seat saves the analyze report with `bin/wuwei spec analysis <item> < report` and gives a
scratch file another name."

## Tests

- `python -m pytest -q tests/test_spec_mode.py tests/test_charters.py tests/test_agents.py
  tests/test_docs.py`, then the full suite.
