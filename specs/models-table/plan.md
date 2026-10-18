# Implementation plan: models-table

**Spec**: `specs/models-table/spec.md`
**Item**: models-table, tier full, goal G-3

## Technical context

- `hook.session_start` injects `_way.md`, `_common.md` and `planner.md` into the owner's session;
  the planner is the seat that launches the others, so the table lives in `planner.md`.
- `tests/test_charters.py` holds charters and skills to 35 words per sentence and an average under
  20, and `planner.md` rules 1 to 10 under "Running the work" stay numbered in order, so the new
  section goes after "What goes to the owner".
- `wuwei agents build` writes `agents/`; `setup.vendor('.')` copies charters, agents and skills to
  `.claude/`; `tests/test_setup.py` holds both from drifting.
- Runtime budget: 3,000 lines; this change adds none.

## Design

1. `planner.md` "Model and effort": a two-column table (seat, model and effort) and seven numbered
   rules: the call and brief lines, the ladder, diversity, the Haiku floor, effort, precedence, and
   the owner's override with a one-line Codex pointer. The Codex table and the precedence cases
   live on the models page, so the session text stays short.
2. `models.md`: inputs, reasons per row, ladder and diversity, effort, how Claude Code applies it,
   Codex, the steward's loop, and dated sources. Nav and concepts index entries.
3. `team.md`, `codex.md`, `design.md` section 3: replace the `MODELS` sentences with a link to the
   table.
4. `steward.md` rule 6 gains the seat, model and effort reading; `wuwei-watch` gains the option.
5. Tests in `tests/test_charters.py` for each acceptance scenario.

## Verification

- Red first on the new tests, then the text, then `bin/wuwei agents build`, `setup.vendor('.')`
  and the full suite.
- Every fact in the charter and page re-read from the source pages, saved under the builder's
  scratch folder on 2026-10-18.

## Constitution check

Stdlib only, no runtime line, no new door, no config key, test first, no emoji, no em dash.
