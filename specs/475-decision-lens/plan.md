# Implementation Plan: decision titles, rationale, consequence, reasoning and lenses

**Branch**: `475-decision-lens` | **Spec**: `specs/475-decision-lens/spec.md` |
**Data model**: `specs/475-decision-lens/data-model.md`

## Summary

Extend the one decision record and its one evaluator in `cli/wuwei/decision.py`: the
Options table gains `Title | Rationale | Consequence` (title replaces the description
column), three fields are parsed (`Class:`, `Reasoning:`, `Lenses:`), and `evaluate` gets an
optional `lenses` argument that turns on the new-record checks. Writers and askers pass it;
history readers do not, so earlier records keep counting. One `options(fields)` helper reads
both table shapes and replaces the six copies of `table(fields['Options'], ['Option',
'Description'], 'Options')`. The widget, `present`, the record command and the label
resolution change in `decision.py`; the rest is config, generators, charters and docs.

## Technical Context

Python 3.11+, stdlib only (`re`). No new module, no new command, no new dependency. Config
grows one wildcard table. Tests in `tests/`, pytest only.

## Constitution Check

- I stdlib: yes.
- II exits: unchanged; a refusal is exit 1 with the field named; unreadable config in the
  lint stays exit 2 through `lint_file`'s existing handler.
- III one behaviour, one function: the record checks stay in `decision.evaluate`; the Options
  read is one helper; lenses are one constant plus one function; the card is
  `record_widget`; label resolution is one function used by both owner writers.
- IV test first: every behaviour has a failing test before code (tasks.md).
- V ponytail: extend the existing table, parser, widget and presenter; reuse `table()`,
  `widget()`, `workspace.verbosity`, the wildcard config schema and the existing config
  check loop. No second record type, no lens classes, no per-class lens config, no
  character budget, no `Raised-by:` field.
- VII security: titles are pasted into a double-quoted shell command, so `"`, backtick, `$`
  and backslash are refused; the owner-action guard (`protect_state.py:229-232`) is
  unchanged and still sees the D-n word.

## Design

### 1. `cli/wuwei/decision.py`: classes, lenses, parsed fields

- `CLASSES`: insert `'design': (0, 3), 'boundary': (0, 3), 'refactor': (0, 3)` after
  `'dependency-bump'`.
- New constants next to `CLASSES`:
  `ENGINEERING = ('design', 'boundary', 'refactor', 'dependency-bump')`,
  `LENSES = {'SOLID': ..., 'twelve-factor': ..., 'YAGNI': ..., 'ponytail': ...}` (questions
  in data-model.md), `OPTION_COLUMNS = ['Option', 'Title', 'Rationale', 'Consequence']`,
  `OPTIONAL = ('Class', 'Reasoning', 'Lenses')`.
- `def lens_table(config)`: `{name: q for name, q in {**LENSES,
  **config['decisions']['lenses']}.items() if q}`.
- `evaluate`: build the field regex from `FIELDS + OPTIONAL`; `missing` stays over `FIELDS`
  only. Add `Class` and `Reasoning` to the one-line loop when present. A present `Class` not
  in `CLASSES` raises `Class: expected one of <classes>; ...`. This is what fixes current
  behaviour 2 (a `Class:` line no longer joins the Question).

### 2. `decision.py`: `options(fields)` and the Do nothing rule

```python
def options(fields):
    """Options rows; column 2 is the title (#475) or, in an earlier record, the description."""
    header = next((line for line in fields['Options'].splitlines() if line.strip()), '')
    legacy = [c.strip() for c in header.strip().strip('|').split('|')] == ['Option', 'Description']
    return table(fields['Options'], ['Option', 'Description'] if legacy else OPTION_COLUMNS, 'Options')
```

`_scored` calls `options(fields)`; the id and Do nothing or Defer checks read `row[0]` and
`row[1]` as today. Replace the other five copies with `decision.options(fields)`:
`record_widget`, `commands/decision.py` `owner_outcome` (line 105),
`control_plane.py` `options` (line 49, keep the function as a one-line wrapper or inline it),
`interview.py:602` and `consolidation.py:266` (both become
`{row[0]: row[1] for row in decision.options(fields)}`, since `dict()` needs pairs).

### 3. `decision.py`: the new-record check inside `evaluate`

Signature `evaluate(text, lenses=None)`; docstring says `lenses` (the effective lens table)
turns on the #475 new-record checks and history readers leave it `None`. After the existing
checks, when `lenses is not None`:

1. `Class` present, else `missing fields: Class; ...` (same wording as the missing loop).
2. Options rows have 4 columns, else `Options: expected columns Option, Title, Rationale,
   Consequence; ...` (`table()` already refuses empty cells and duplicate ids).
3. Each title: at most 40 characters, no `"`, backtick, `$` or backslash; titles unique by
   `casefold()`. Message starts `Options: title <title> ...`.
4. `Reasoning` present (`missing fields: Reasoning; ...`); one line (from section 1).
5. If `fields['Class'] in ENGINEERING and lenses`: `rows = table(fields.get('Lenses', ''),
   ['Lens', *ids], 'Lenses')` (refuses a missing table, a missing or extra cell, an empty
   cell, a duplicate row); then `missing = [n for n in lenses if n not in names]` raises
   `Lenses: missing <names>; add one line per option for each ...`, and an extra name raises
   `Lenses: unknown lens <name>; the configured lenses are <names>`.

Every message ends with the existing `bin/wuwei decision template shows a valid one` hint
style so `tests/test_reasons.py` stays green.

Callers that pass lenses:

- `lint(text, lenses=LENSES)`: `evaluate(text, lenses)`.
- `lint_file(path, *, root=None, ...)`: resolve the workspace once (the same
  `find_workspace(Path(path).parent)` try that `record_rejection` does, then pass `root`
  on), `lenses = lens_table(workspace.load_config(root)) if root else LENSES`, call
  `check(text, lenses)` for decisions. Clarifications unchanged.
- `write(text, root)`: `evaluate(text, lens_table(workspace.load_config(root)))`.
- `commands/decision.py` `show` with `--widget`: `evaluate(text, lens_table(config))`.
- `mcp.widget`: `evaluate(..., decision.LENSES)`.
- `scanner.py:119`: `decision.evaluate(body, decision.LENSES)`.

Every other `evaluate(text)` call stays as is (history and routing readers).

### 4. `decision.py`: lens lines, card, presenter, record command, labels

- `def lens_lines(fields)`: `{}` unless `fields.get('Class') in ENGINEERING and
  fields.get('Lenses')`; else for each option id the list `f'{row[0]}: {row[1 + index]}'`
  over `table(fields['Lenses'], ['Lens', *ids], 'Lenses')`.
- `def first(text)`: `re.split(r'(?<=[.!?])\s+', text.strip(), maxsplit=1)[0]`.
- `RECORD = 'wuwei decide {id} "<label>"'`.
- `record_widget(identifier, fields, record=RECORD, level='brief')`: rows from `options()`,
  recommended first, `[:4]` as today. Label `title + ' (Recommended)'` for the first, else
  `title`. Description `'\n'.join(parts)` where `parts = [rationale, consequence,
  *lens_lines(fields).get(option, [])]`, each through `first` when `level == 'brief'`.
  Question `f'{identifier}: {fields["Question"]} {first(fields["Reasoning"])}'`. Still
  built through `widget()`. Called only after a new-record `evaluate`, so rows have 4
  columns.
- `present(identifier, fields, level)`: iterate rows (not `(option, text)` pairs, which
  break on 4 columns). Option line `f'{id}: {title} (score N[, fails a must])'` plus
  `f'. {consequence}'` when the row has 4 columns. At `standard` add, per option with 4
  columns, `f'  Rationale: {rationale}'` and `f'  {lens line}'` for each lens line. The
  `Recommended: ...` line gets `f' {fields["Reasoning"]}'` when present. A legacy record
  prints exactly as today.
- `def option_id(fields, label)`: strip a trailing ` (Recommended)`, return the one row
  whose id or title (casefold) equals it, else the label unchanged (so the caller's
  existing "not in the record" refusal fires).

### 5. Owner writers resolve the label

- `commands/decision.py` `owner_outcome`: after `evaluate`, `args.option =
  option_id(fields, args.option)` before the membership check, so `decide` and `decision
  outcome` both accept a title.
- `mcp.py`: `RECORD = 'wuwei mcp decide {id} "<label>"'`; in `decide` (around line 674)
  `option = decision.option_id(fields, option)` before `if option not in scores`; in
  `widget` match the proceed option with `decision.option_id(fields, option['label']) ==
  'proceed'` and pass `level=workspace.verbosity(workspace.load_config(root), 'decisions')`.

### 6. `commands/decision.py`

- `show --widget`: load config once; `record_widget(args.id, fields,
  level=workspace.verbosity(config, 'decisions'))`.
- `template`: build the text from the effective lenses (`lens_table` of the workspace config
  when `workspace.find_workspace()` succeeds, else `LENSES`): `Class: design`, the
  four-column Options (`A` "Make the scoped change", `B` "Defer"), an HTML comment
  `<!-- Lenses: one line per option for each. <name>: <question> ... -->`, a `Lenses:`
  table with one row per lens (cells `Replace with one line for A` style), the existing
  Musts and Wants, `Reasoning:` after `Recommendation:`. With no lenses configured the
  comment and table are left out. It must lint clean (`OK: A (80)`).

### 7. CLI-written records (FR-011)

Each gets `Class:`, the four-column Options and `Reasoning:`; titles at most 40
characters; the Do nothing or Defer option's title starts with `Do nothing` or `Defer`.
None is an engineering class, so none needs `Lenses:`.

| File | Class | Titles |
|---|---|---|
| `scanner.py` `_trace_response` | `other` | Investigate the session / Defer investigation |
| `plan.py` day close | `defer` for carry, `park` for park | Carry to tomorrow or Park the item / Do nothing, keep working |
| `pr_actions.py` scope thread | `other` | Make the scope change / Defer to the owner |
| `mcp.py` registry findings | `other` | Defer launches / Proceed with findings |
| `mcp.py` `_proceed_unmeasured` | `other` | Defer launches / Proceed unmeasured |
| `commands/build.py` `_park` | `park` | Defer and investigate / Retry the build |
| `retro.py` hard rule | `other` | Propose the rule / Defer the rule change |
| `remote.py` `DENIAL` | `other` | Resume without the tool / Do nothing, leave idle |

Rationale, Consequence and Reasoning are one short fixed sentence each, written from the
existing Musts, Wants and Pre-mortem of that record. `retro.py` has a local variable named
`decision`; it gets no self-check, its test lints the written file instead.

### 8. Config: `cli/wuwei/workspace.py`

- `SCHEMA['decisions']`: add `"lenses": {"*": (str, "")}`.
- In the config checks, next to the cruise-levels loop (line 644): each lens name must match
  `[A-Za-z][A-Za-z0-9_-]*`, else `ConfigError('decisions.lenses.<name>: use letters, digits,
  dash or underscore, starting with a letter; the owner fixes it with bin/wuwei config set
  in a host terminal')`.
- `CONFIG_CACHE_VERSION = 6` (the schema changed).

### 9. Telemetry: `cli/wuwei/telemetry.py`

`CLASSES` gains `'design', 'boundary', 'refactor'` (the pin test
`tests/test_telemetry.py:132` compares it with `decision.CLASSES`). `SCHEMA` stays 1.

### 10. Charters, agents, skill, docs, design spec

- `charters/_common.md` Decisions and procedure item 1: list `Class:` (a 5.8.1 class), the
  `Option | Title | Rationale | Consequence` table, `Reasoning:` under the recommendation,
  and `Lenses:` for an engineering class (`design`, `boundary`, `refactor`,
  `dependency-bump`), one line per option per configured lens; `wuwei decision template`
  prints them.
- `charters/lead.md`, `charters/sentinel-arch.md`, `charters/builder.md`: one line each: a
  decision about how to build (architecture, interface or data shape that outlives the item:
  `design`; a module, service or ownership boundary: `boundary`; restructuring without a
  behaviour change: `refactor`; a manifest or lockfile: `dependency-bump`) is an engineering
  class and its lens lines are mandatory. Then `bin/wuwei agents build` and `bin/wuwei agents
  check`; commit the regenerated `agents/*.md` with them. The ziran baseline does not change
  (no tool change).
- `skills/wuwei-plan/SKILL.md` Owner questions: one sentence: a decision card's labels are the
  option titles, the recommended first and marked (Recommended); each description is the
  rationale, the consequence and the lens lines; the question ends with the reasoning; pass
  them unchanged and paste the chosen label into the quoted record command.
- `docs/site/concepts.md`: glossary `### Lens` (two lines); under Decision classes, a short
  paragraph on the record shape (title, rationale, consequence, reasoning, class) and the
  lenses, and the three new classes.
- `docs/site/configuration.md`: line 17 index row adds `[decisions.lenses]`; a table row
  `decisions.lenses` | `{}` | the defaults, adding, dropping with `""`.
- `docs/specs/2026-09-24-wuwei-design.md`: 5.8 heading gains `#475`; the field list gains the
  option columns, `Reasoning:` and `Lenses:`, and the enforcement paragraph says the lint
  refuses a new record missing them; 5.8.1 table gains the three rows. Mark the amendment
  `(owner, 2026-10-04, #475)`.

## What must not change

- `evaluate(text)` without lenses accepts every record it accepts today (history readers:
  `consolidation`, `interview` re-ask, `waits`, `why`, `doctor`, `dashboard`, `closing`,
  `pr_actions`, `control_plane.pending`, `mcp.decide`).
- Scoring, `route`, `route_owner`, `seat_outcome`, `level`, `answered`, `set_outcome`,
  `owner_record`, `widget()` limits, `table()`.
- The question guard and `record_gate` logic in `guards/decision.py` (they call `lint_file`,
  which now applies the new-record check).
- `control_plane.parse` (replies name option ids), `plan` lint and `rank` (prioritisation
  lens), the Reversibility field.
- Telemetry `SCHEMA`; exit codes everywhere.

## Files

Code: `cli/wuwei/decision.py`, `cli/wuwei/commands/decision.py`, `cli/wuwei/mcp.py`,
`cli/wuwei/control_plane.py`, `cli/wuwei/interview.py`, `cli/wuwei/consolidation.py`,
`cli/wuwei/workspace.py`, `cli/wuwei/telemetry.py`, `cli/wuwei/scanner.py`,
`cli/wuwei/plan.py`, `cli/wuwei/pr_actions.py`, `cli/wuwei/commands/build.py`,
`cli/wuwei/retro.py`, `cli/wuwei/remote.py`.
Text: `charters/_common.md`, `charters/lead.md`, `charters/sentinel-arch.md`,
`charters/builder.md`, `agents/*.md` (generated), `skills/wuwei-plan/SKILL.md`,
`docs/site/concepts.md`, `docs/site/configuration.md`,
`docs/specs/2026-09-24-wuwei-design.md`.
Tests: `tests/test_decision.py` (most), `tests/test_workspace.py`, `tests/test_mcp.py`,
`tests/test_brief.py`, `tests/test_charters.py`, plus fixture updates where a record goes
through the lint or `write` (`tests/test_why.py`, `tests/test_remote.py`,
`tests/test_control_plane.py`, `tests/test_doctor.py`, `tests/test_dashboard.py`, and others
the suite names). Fixtures read only through `evaluate(text)` (for example
`tests/test_consolidation.py`, `tests/test_interview.py`) stay legacy: they prove FR-004.
