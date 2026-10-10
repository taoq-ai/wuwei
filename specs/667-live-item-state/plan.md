# Implementation Plan: seats read live item state

**Branch**: `667-live-item-state` | **Date**: 2026-10-10 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/667-live-item-state/spec.md`

## Summary

The brief stops copying the two values the day changes under a gate seat (the quality
`Docs:` value and the gate `Spec:` state) and instead tells every builder and gate seat to
read them with `bin/wuwei why <item> --json`. `why` gains `--json`, built from the readers
that already exist (`docs.shown`, `docs.command`, `specmode.brief_line`, the `tickets` map).
The verdict lint gains one rule, fed by the same `docs.shown` read at lint time: a finding
that calls a recorded docs value missing is rejected.

## Technical Context

**Language/Version**: Python 3.11+, stdlib only at runtime
**Primary Dependencies**: none new
**Testing**: pytest, in process (`main([...])`, `verdict.lint_file`), no subprocess
**Target Platform**: the WUWEI CLI and its hooks
**Project Type**: single project (`cli/wuwei`, `charters`, `agents`, `docs`)
**Performance Goals**: the verdict guard runs `lint_file` only on gate file writes; the new
read is one `load_config` and a dict lookup on a state the lint already reads
**Constraints**: three-state exits; no new state key, event kind or file
**Scale/Scope**: about 60 lines of code across four modules, one charter, docs

## Constitution Check

- I stdlib only: yes, no import added outside the package.
- II three-state exits: `why --json` exits 0 with the object, 1 for an unknown item (existing
  `Missing`), 2 for a non-item target. The lint rule only adds exit-1 failures.
- III one behaviour, one function: the docs value is read by `docs.shown` in both `why` and
  the lint; the spec state by `specmode.brief_line`; no copy.
- IV test first: every task pair below is test then code.
- V ponytail: no new module, no new state, no config. The lint checks docs only (spec A3).
- VII security: JSON strings pass the same redaction `render` applies; the lint can only
  reject more, never accept more; the receive docs check is untouched.
- Workflow: the lint rule is a verdict guard rule, so it adds invariant I46 to design 9.2 and
  `tests/test_invariants.py`. The owner reserved I46 for this item; I38 to I41 are held
  for other in-flight items.

## Changes, by file

### `cli/wuwei/commands/why.py`

- `register`: add `parser.add_argument('--json', action='store_true', help='print the item\'s
  live docs, ticket and spec values and its steps as JSON')`.
- Extract the first lines of `item()` (PR ref resolution and the `days` list, lines 88-98)
  into `_days(root, name)` returning `(name, days)`; `item()` calls it. No behaviour change.
- New `live(root, name, level)`: `name, days = _days(root, name)`; `day, data = days[-1]`;
  `row = data['items'][name]`; `config = workspace.load_config(root)`; `shown =
  docs.shown(config, row)`; return

  ```python
  {'item': name, 'day': day.name,
   'docs': {'value': shown, 'reason': (row.get('docs') or {}).get('reason', ''),
            'command': None if shown == 'n/a' else docs.command(config, name)},
   'ticket': ((data.get('tickets') or {}).get(name) or {}).get('id'),
   'spec': spec and spec.removeprefix('Spec: '),
   'steps': render(item(root, name), level, root)}
  ```

  where `spec = specmode.brief_line(config, name, row, Path(row['worktree']) if
  row.get('worktree') else None, True)`. String values (`docs.value`, `docs.reason`,
  `ticket`, `spec`) go through the same `security.redact(redact(...), markers)` as `render`
  (one small local helper or a comprehension; no new module).
- `run`: when `args.json`, a target that matches `last refusal`, `EVENT_ID`,
  `decision.DECISION_ID`, `DRAFT` or `novelty.KEY` prints
  `wuwei why: --json reads an item; pass an item id` to stderr and returns `UNRUN` (2);
  otherwise `print(json.dumps(live(root, target, level(root, args.full))))` inside the
  existing `try/except Missing` (exit 1 path unchanged).
- Imports: `docs`, `specmode` (lazy inside `live` is fine; `docs` is stdlib plus state and
  workspace only) and `Path`.

### `cli/wuwei/brief.py`

- Line 440: the `Spec:` line is appended only for `role == 'builder'` (was `role == 'builder'
  or gate`); pass `False` for `gate`.
- Line 482-485: keep the `docs.brief_line` call; after the docs change below it returns a line
  only for the builder.
- Add, for `role == 'builder' or gate`, one header line at the place the quality `Docs:` line
  was:
  `Live: run bin/wuwei why {item} --json when you start and again before your verdict or
  handoff; its docs, ticket and spec fields are the record at that moment. This brief copies
  none of them.`
  As a module constant `LIVE` beside `LIGHT_GATE`, formatted with the item.

### `cli/wuwei/docs.py`

- `brief_line`: delete the quality branch (lines 113-121) and change the role test to
  `role != 'builder'`; update the docstring to "The Docs: header line of a builder brief".
  `required`, `unmet`, `shown` and `command` stay (used by receive, close, why and lint).

### `cli/wuwei/verdict.py`

- Constant `DOCS_MISSING`, compiled with `re.I`, matched per finding block:
  `r'\bdocs? (?:value|path):? (?:is |was )?(?:still )?(?:missing|not set|not recorded|unset|absent)\b'
  r'|\b(?:missing|no|unset) docs? (?:value|path)\b|\bdoc\b[^\n]{0,40}\bvalue missing\b'`.
  The words must touch the value: `the docs path docs/cli.md is missing the --json flag` and
  `the return value missing a zone` do not match. The table test in T007 pins both sides.
- `lint(..., docs=None)`: `docs` is `(item, value)` or `None`. When set, for each finding block
  matching `DOCS_MISSING` append
  `f'finding {number}: says the docs value is missing, but {item} records docs {value} '
  f'(bin/wuwei why {item} --json); drop or correct the finding'`. Inside the existing
  `for number, block in enumerate(blocks, 1)` loop.
- New `recorded_docs(path, data, root)`, beside `light`: resolve the seat from the gate file
  stem exactly as `light` does (`brief.seats(data).get(Path(path).stem[len('gate-'):])`), the
  item row, then `docs.shown(workspace.load_config(root or workspace.find_workspace(
  Path(path).parent)), row)`; return `(item, value)` when `value not in ('missing', 'n/a')`,
  else `None`; any `KeyError, TypeError, ValueError, AttributeError, OSError` returns `None`
  (spec A4).
- `lint_file`: read `data = day_state(path)` once and pass `light=light(path, data)` and
  `docs=recorded_docs(path, data, root)`.

### `charters/sentinel-quality.md`, then `bin/wuwei agents build`

- Bump `version: 1.1.0` to `1.2.0`.
- Step 7 becomes: "Run `bin/wuwei why <item> --json` when you start and again before the
  verdict; its `docs` field is the obligation now, never a copy in the brief. When
  `docs.value` is not `n/a`, check it against the diff under `DOC`. A `missing` value, or
  `none` for a change to documented behaviour (a command, a config key, an interface or
  user-visible output), is a blocking `DOC: FINDING` naming `docs.command`. A finding that
  calls a recorded value missing is refused by the verdict lint."
- Run `bin/wuwei agents build` so `agents/sentinel-quality.md` matches.

### `docs/specs/2026-09-24-wuwei-design.md`

- 5.12, "Checks, at two points", first bullet: replace "The quality brief carries the
  obligation and the recorded value." with "The quality brief names the obligation's reader,
  `wuwei why <item> --json`, which the sentinel runs when it starts and before its verdict;
  the brief copies no value (#667). The verdict lint refuses a finding that calls a value
  recorded at lint time missing."
- 9.2: add row I46: "A gate verdict never calls a recorded docs value missing: `lint_file`
  refuses a finding that says the docs value is missing while the item records one, and adds
  nothing when the value is missing, not required or unresolvable" | test: `verdict.lint` on
  a missing-value finding with `docs` set and unset, and on a page-content finding with
  `docs` set | "#667; one read through `docs.shown` in `verdict.recorded_docs`".

### `docs/site/reference.md`

- Why section: one paragraph for `--json` (the fields, read at call time, exit 2 for a
  non-item target).

## Reuse, do not rewrite

- `docs.shown`, `docs.command`: the docs value and its recording command.
- `specmode.brief_line(..., gate=True)`: the spec state text (its gate branch keeps exactly
  one caller, `why.live`).
- `why.render`: redaction for the JSON strings and the `steps` lines.
- `verdict.light` and `verdict.day_state`: the seat-to-item resolution pattern and the day
  state read.

## Must not change

- `dispatch.receive`'s docs check (`dispatch.py:676-682`): a quality PASS with a missing value
  is still refused.
- The builder brief's `Spec:` and `Docs:` lines (text and presence), `charters/builder.md`.
- `why` text output for every target; `why` exit codes without `--json`.
- `verdict.lint` behaviour when `docs` is `None` (every existing caller: `guards/pr.py`,
  `obligations.py`, `dispatch.py:672`).
- No new state key, event kind or reserved producer.

## Project Structure

Documentation (this feature): `specs/667-live-item-state/` with `spec.md`, `plan.md`,
`tasks.md`. No research, data model, contract or quickstart file: the plan above holds all
of it.

Source touched: `cli/wuwei/commands/why.py`, `cli/wuwei/brief.py`, `cli/wuwei/docs.py`,
`cli/wuwei/verdict.py`, `charters/sentinel-quality.md`, `agents/sentinel-quality.md`
(generated), `docs/specs/2026-09-24-wuwei-design.md`, `docs/site/reference.md`.

Tests touched: `tests/test_why.py`, `tests/test_brief.py`, `tests/test_verdict.py`,
`tests/test_charters.py`, `tests/test_invariants.py`.

## Complexity Tracking

None.
