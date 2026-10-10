# Implementation Plan: the interview reads the config before asking

**Branch**: `639-interview-reads-config` | **Date**: 2026-10-10 | **Spec**: [spec.md](spec.md)

## Summary

`interview.unanswered` is the one count every caller reads (#530). Make it parse the raw
`config.toml` once and drop a (row, repo) pair when the config answers that row. No caller
changes, no new module, no signature change.

## Technical Context

Python 3.11+ stdlib (`tomllib`, already imported by `calibrate`, which `interview` imports).
pytest dev-only. No new config key, state key, event or port.

## Constitution Check

- I stdlib: `tomllib` only.
- II exits: a config read or parse error propagates as `OSError` or `ValueError`
  (`tomllib.TOMLDecodeError` is a `ValueError`); `doctor` and `init --upgrade` already show it
  as unmeasured and `calibrate --questions` as exit 2.
- III one behaviour one function: the decision lives in one helper next to `unanswered`.
- IV test first: tasks.md orders each test before its code.
- V simplicity: reuse `_path`, `_setting`, `calibrate._table`, `configtext.declared`,
  `workspace._default`; no caching, no new parameter.
- VII security: not a guard or decision rule; nothing is written, no grant (spec
  Assumptions). No 9.2 row.

## Design

All changes in `cli/wuwei/interview.py`.

1. New helper beside `unanswered`:

   ```python
   def _configured(row, repo, present):
       """#639: the raw config answers a row when it sets every config key the row's choices
       write and one differs from its default (the template writes defaults explicitly)."""
   ```

   - keys = `{name for _, _, result in row['choices'] for name in result if _setting(name)}`
   - for each name: `path, key = _path(name, repo, present)`;
     `table = calibrate._table(present, path)`; a missing table or key returns False.
   - differs = `node is None or table[key] != workspace._default(node)` with
     `node = configtext.declared((*path, key))`, the same expression as `calibrate.kept`.
   - return `any(differs)`; an empty key set returns False (`any([])`), which covers the
     charter, voice and allowlist rows.

   `_path` works on the parsed raw dict unchanged: it reads `config['repos']` names, and the
   raw `[[repos]]` tables carry `name`. Every key the table writes is schema-declared
   (checked on `main`), so `node is None` is only the defensive branch `kept` already has.

2. `unanswered(root, repos)`:

   ```python
   done = _recorded(root)
   present = tomllib.loads((root / '.wuwei/config.toml').read_text(encoding='utf-8'))
   return [... if (row['id'], repo) not in done and not _configured(row, repo, present)]
   ```

   Import `tomllib` and `configtext` at the top of `interview.py` (both already loaded
   through `calibrate`). Update the docstring: answered by a day's answer or by the config.

## What must not change

- `_recorded`, `record`, `load`, `ask`, `parse`, `_selected`: asking by id ignores the
  config (`widgets(root, repos, ids)` with ids, `calibrate --interview merge`).
- The callers `commands/init.py`, `commands/doctor.py`, `commands/calibrate.py`.
- The QUESTIONS table and `templates/workspace/config.toml`.
- Existing tests `test_unanswered_is_the_one_count`,
  `test_widgets_come_from_the_table_and_pass_the_question_guard`,
  `test_upgrade_counts_the_unanswered_setup_questions`,
  `test_workspace_interview_counts_the_unanswered` and
  `test_questions_with_ids_reprint_answered_rows` keep passing without edits (their configs
  set no non-default interview key).

## Deliberate shortcuts

- `init --upgrade --dry-run` reads the config on disk, not the migrated text (spec
  Assumptions). Add a `raw` parameter only if a migration ever starts changing interview keys
  beyond `guards.mode`.
