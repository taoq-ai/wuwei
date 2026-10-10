# Implementation Plan: one verdict format for the lint and the charters

**Branch**: `665-verdict-format` | **Date**: 2026-10-10 | **Spec**: [spec.md](spec.md)

## Summary

The lint already is the one parser every verdict reader uses (`verdict.lint`,
`verdict.finding_blocks`). Fix it there: a numbered line starts a finding only under a
`Findings` heading or when a severity, `Severity:` or an id follows the number; section
headings close a finding block. Add one table, `verdict.FORMAT`, that feeds the lint's
messages and renders the `## Verdict format` section (`verdict.section()`). `agents.render`
puts that section into every sentinel agent and refuses a charter that carries its own copy.
`_common.md` item 8 stops showing the literal `CLASS:` form.

Why rendered into the agents and not copied into `_common.md`: `tests/test_process_depth.py`
pins `_common.md` plus `builder.md` at 65 lines (#567) and they are at 65 today. A first
probe with the section copied into `_common.md` failed that test (95 lines) and
`test_owner_records_lint` (its error message said "paste"). The rendered design below was
then probed on a scratch copy of `main`: `tests/test_verdict.py`, `test_process_depth.py`,
`test_docs.py`, `test_pr_guards.py`, `test_obligations.py`, `test_dispatch.py`,
`test_invariants.py` (I39 included), `test_metrics.py`, `test_stop.py`, `test_runtime.py`,
`test_charters.py`, `test_agents.py`, `test_tone.py`, `test_ziran.py` and
`test_owner_records_lint.py` passed with no change to any existing test, after regenerating
the agents. The rest of the suite passed except tests that need the copy to be a git
repository (it was not).

## Technical Context

Python 3.11+ stdlib only, pytest dev-only. No new module, command, event kind, state key or
config key. Files touched: `cli/wuwei/verdict.py`, `cli/wuwei/commands/agents.py`,
`charters/_common.md` (one parenthetical and the version), the nine regenerated
`agents/*.md`, `docs/site/reference.md`, `docs/specs/2026-09-24-wuwei-design.md` (9.2 row),
tests.

## Constitution Check

- I stdlib: nothing new imported; `agents.py` imports `wuwei.verdict` (stdlib only).
- II exits: a charter-side copy is a `ValueError` in `render`, which `build` and `check`
  already turn into exit 2 with the reason; lint findings stay exit 1.
- III one behaviour one function: the format lives in `verdict.FORMAT`, the parser in
  `verdict.finding_blocks`, the rule in `verdict.lint`. The write guard, seat stop,
  `dispatch.receive`, the PR guard and obligations reach it through `lint`, `lint_file` or
  `finding_blocks`; none changes.
- IV test first: tasks.md orders each test before its code.
- V simplicity: one string appended in `render`, no template engine; one example for all
  sentinels; no new CLI subcommand; no charter growth; the class names become one tuple.
- VII security: no finding form that carries `blocks: yes` today stops being parsed
  (#677, #712 hold); a PASS can still not carry a blocking finding.
- Workflow: the changed guard rule adds a 9.2 row and its check in
  `tests/test_invariants.py`.

## Design

### cli/wuwei/verdict.py

Constants (lines 16-18):

```python
CLASS_NAMES = ('AUTH', 'VAL', 'DOC', 'TEST', 'INF', 'RET', 'ERR', 'STATE', 'CON', 'BUD',
               'DATA', 'PROOF')
CLASSES = '(' + '|'.join(CLASS_NAMES) + r'): *(PASS|N\.A\.|FINDING)'
FIELDS = r'(?:File|Location|Scenario|Severity|blocks?|Probe|Mutation):'
HEADING = r'^\s*(?:#{1,6}\s+(.+?)|([A-Za-z][\w ()/-]*):)\s*$'
FORMAT = {  # #665: the one verdict format; agents build renders section() into the sentinel agents
    'Verdict': ('`Verdict: PASS|FIX|PARK|ESCALATE`, once', 'Verdict: FIX'),
    'Head': ('`Head: <7 to 40 hex>`, the sha you reviewed, once', 'Head: 3f1c2ab'),
    'Finding': ('`F<n> <severity> <file:line> <failure scenario> blocks: yes|no`; a numbered '
                'line is a finding only under a `Findings` heading',
                'F1 medium src/calc.py:19 fails when the input is empty. blocks: yes'),
    'Probe': ('`Probe: <what ran and what it showed>`, or `Probe: not run`', 'Probe: not run'),
    'Class': ('`<CLASS>: PASS|N.A.|FINDING <id>`, one line per class you check, CLASS one of '
              + ', '.join(CLASS_NAMES) + ' (arch, quality and security)', 'VAL: FINDING F1'),
    'Simplicity': ('`Simplicity: <what to delete and what replaces it, or none and why>` (quality)',
                   'Simplicity: none, one guard and one division'),
    'Design': ('`Design: <what makes this change harder to test or change, or none and why>` (quality)',
               'Design: none, a single pure function'),
    'Blocked': ('`Blocked: <evidence or none>`', 'Blocked: none'),
    'Gap': ('`Gap: <evidence or none>`', 'Gap: none'),
    'Change': ('`Change: <evidence or none>`', 'Change: none'),
}
```

The wording above passed `test_agents.py`, `test_charters.py` and `test_tone.py` in the
probe. `FIELDS` is the field-name list of line 68 plus `Severity`; leave line 68 itself as it is
(adding `Severity` there would stop a bulleted `- Severity: P2` line from starting a
finding, a behaviour change).

Two small functions after `FORMAT`:

```python
def section():
    """The charter's verdict section, rendered from FORMAT (#665)."""
    rows = ''.join(f'- {key}: {form}\n' for key, (form, _) in FORMAT.items())
    example = ''.join(line + '\n' for _, line in FORMAT.values())
    return ('## Verdict format\n\nWrite these lines; the verdict lint checks them.\n\n' + rows
            + '\nAn example the lint accepts:\n\n```text\n' + example + '```\n')


def _fix(key, line=None):
    return (f" in '{line.strip()[:80]}'" if line else '') + f'; write: {FORMAT[key][0]}'
```

`finding_blocks` (line 57), the only parser change:

- Keep a `findings` flag, False at the start.
- `numbered` becomes: a finding id at the line start (unchanged), or `\d+[.)]\s+` that is
  followed by `\[?` + `SEVERITY`, `Severity:` or `FINDING_ID`, or whose line carries
  `BLOCKS` anywhere; under `findings` any `\d+[.)]\s+` counts. Probe form:
  `lead = '' if findings else r'(?=\[?' + SEVERITY + r'|Severity:|' + FINDING_ID + r'|.*?(?:' + BLOCKS + '))'`
  then `re.match(r'^\s*(?:\d+[.)]\s+' + lead + '|' + FINDING_ID + ')', line, re.I)`. The
  `BLOCKS` case keeps a numbered `... blocks: yes` line a finding, so a PASS still cannot
  carry it and a FIX still parses it.
- `heading` = the line matches `HEADING`, does not start a finding (`start`, `numbered`) and
  does not match `^\s*` + `FIELDS`. On a heading set `findings` to whether its text matches
  `findings?\b` (case-insensitive).
- In the `elif current:` branch, a `heading` closes the block exactly as the existing
  `#|Blocked:|...` match does (line 78).
- `start`, `explicit`, `row`, `heading_only` and everything else stay as they are.

`lint` (line 88), messages only; the checks and their order do not change:

| Line today | Becomes |
|---|---|
| 98 `'expected exactly one Verdict: line'` | same + `_fix('Verdict', <the Verdict lines after the first, joined by '; '>)` |
| 112 `'no class-sweep line (CLASS: PASS\|N.A.\|FINDING <id>)'` | `'no class-sweep line' + _fix('Class', near)`, where `near` is the first active line matching `^\s*[A-Z]+: *(?:PASS\|N\.A\.\|FINDING)\b.*$` (all caps, so `Verdict:` never matches) |
| 125 `'PASS verdict carries a blocking finding'` | same + `_fix('Verdict', <first line of the first blocking block>) + ', or blocks: no'` |
| 128-131 FIX with no blocking finding | the hint `(start each finding with its severity, a number or an id ...)` becomes `(start each finding with its severity or an id such as F1, Q1 or Finding 1, or list it under a Findings heading; write Verdict: PASS when none blocks)` |
| 133 `'no finding with severity (...)'` | same + `_fix('Finding')` |
| 134-139 one line per missing field | one line per finding: `f'finding {n}: missing {", ".join(missing)}' + _fix('Finding', block.splitlines()[0])`; the field names and their order (severity, file:line, blocks yes/no, failure scenario) stay |
| 147 `'expected exactly one Head: <7 to 40 hex> row'` | same + `_fix('Head', heads and 'Head: ' + heads[-1])` |

The Verdict-missing, Probe, retro and quality-row messages already name the line to write
and stay as they are. Example result for `CLASS: PASS`:
`no class-sweep line in 'CLASS: PASS'; write: `<CLASS>: PASS|N.A.|FINDING <id>`, one line
per class you check, CLASS one of AUTH, VAL, ... (arch, quality and security)`.

### cli/wuwei/commands/agents.py

`render` (line 39), inside the role loop, replacing line 54 (`body = ...`):

```python
charter = _charter(root, role, overrides)
if any('## Verdict format' in text for text in (common, authoring, charter)):
    raise ValueError(f'{role}: a charter carries its own Verdict format section; the format '
                     'lives in cli/wuwei/verdict.py FORMAT and agents build renders it; '
                     'remove the section')
verdict_format = verdict.section() + '\n' if role.startswith('sentinel-') else ''  # #665
body = common + '\n' + verdict_format + authoring + '\n' + charter
```

Import `verdict` beside `security, workspace`. The check runs before any write in `build`,
`check` and `workspace_files` (all go through `render`), on the plugin charters and on
workspace overrides alike. `check` needs no change: a `FORMAT` edit without a rebuild makes
the sentinel agents differ from `render`, which it already reports as drift (exit 1). Do not
word the message with "paste" or "edit the file" (`tests/test_owner_records_lint.py`).

### charters/_common.md

- Version `1.8.0` to `1.9.0`.
- Item 8 (line 24): `require a class-sweep line (`CLASS: PASS|N.A.|FINDING <id>`); goal
  verdicts do not.` becomes `require a class-sweep line (see Verdict format); goal verdicts
  do not.` Nothing else changes: the 5.3 anchors in `tests/test_charters.py` `RULES` live in
  item 8, and the file must stay at 30 lines (`test_charters_follow_the_depth_line`).
- Regenerate `agents/*.md` with `bin/wuwei agents build` (never by hand). The four sentinel
  agents gain the section; all nine gain the item 8 edit and the version. Grants do not
  change, so the ZIRAN baseline is not re-recorded.

### docs/site/reference.md

"Gate verdict layout", lint rules (lines 365-370):

- The bullet "Arch, quality and security add class-sweep lines ..." gains: "Write the class
  name, never the word `CLASS`."
- In the finding-start bullet, "A numbered line or an id line also starts one" becomes "An id
  line also starts one (`F1`, ...); a numbered line starts one under a `Findings` heading,
  when a severity, `Severity:` or an id follows the number, or when it carries `blocks:`.
  A numbered list elsewhere, such as under `Evidence`, is prose."
- New bullet: "A rejection quotes the line it refused and the accepted form. The forms live
  in one table in `cli/wuwei/verdict.py`; `bin/wuwei agents build` renders it as the Verdict
  format section of every sentinel agent and fails when a charter carries its own copy."

### docs/specs/2026-09-24-wuwei-design.md 9.2 and tests/test_invariants.py

Row (next free id at build time; I44, reserved for this item): "A numbered list outside a Findings
heading is not a finding, and every sentinel agent carries the verdict format the lint
accepts | `verdict.finding_blocks` on an `Evidence` numbered list (no block) and a
`Findings` numbered list (one block per line); `verdict.lint_file` on the example in each
`agents.render(ROOT)` sentinel agent with that role (`OK: FIX`) | #665; one table in
`verdict.FORMAT`, one parser in `verdict.finding_blocks`, rendered by `agents.render`".

`tests/test_invariants.py`: `i44(case, rules)` in the style of `i39` (pure, memoised with
`rules.memo(('verdict format',), compute)`), registered in `INVARIANTS` and in `READS` with
`()`. It calls `agents.render` on the repository root in memory (no write) and lints the
examples through a temporary file.

### Must not change

- `BLOCKS`, `BLOCKS_YES`, `SEVERITY`, `CITATION`, `FINDING_ID`, `VERDICT_ROW`, and the
  `start`, `explicit`, `row` and `heading_only` rules of `finding_blocks`.
- Which verdicts the lint accepts or refuses, apart from numbered lines outside a
  `Findings` heading. The refusal order (`test_source_refusal_order`) and the leading words
  of every refusal.
- `active_text`, `rows`, `retro_fields`, `lint_file`, `light`, `record_rejection`.
- `dispatch.receive`, `guards/verdict.py`, `guards/pr.py`, `obligations`, `closing`: they
  read `lint` and `finding_blocks` and gain the fix with no edit.
- Role charters (`builder.md`, `sentinel-*.md`), `_common-authoring.md`, `allowlist.json`,
  the 65-line pin in `tests/test_process_depth.py`, and the non-sentinel agents apart from
  the item 8 edit.

## Existing tests that encode the old rule

None. The probe needed no change to an existing test; the `plugin` fixture in
`tests/test_agents.py` keeps working because the section is rendered, not required in the
stub charters. Any failure the full suite shows is read before changing a test.
