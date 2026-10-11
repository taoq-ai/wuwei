# Implementation Plan: a CI-fix item's briefs list every step of the failing job, and its gate verdicts cite each

**Branch**: `733-ci-fix-every-step` | **Date**: 2026-10-10 | **Spec**: `spec.md`

## Summary

The existing workflow reader learns step boundaries. Three small functions in `brief.py`
find the jobs a text names, list their run steps and render a block. The item records the
jobs it fixes (`items.<item>.ci_jobs`) in the state writes `wuwei brief` and the fix-round
opener already make, so every later brief, including the fixed-body gate briefs and the
resumed delta seats, lists the same steps. `verdict.lint_file` reads the same steps from the
item and the worktree and `verdict.lint` refuses a verdict that does not carry one result row
per step. Two charter lines, one `FORMAT` row, regenerated agents, one invariant row, one docs
bullet.

## Technical Context

Python 3.11+, stdlib only; pytest for tests. Workflow YAML is read by the line parser in
`cli/wuwei/calibrate.py` (`_workflows`, `_workflow`); no YAML library. Tests write a
`.github/workflows/ci.yml` under `tmp_path` (the brief fixture's worktree) and use the fake
VCS and code host the existing tests use.

## Constitution Check

- I (stdlib): no new import outside the standard library.
- II (exits, fail closed): a recorded job whose workflow file is skipped by `calibrate._read`
  (symlink, not a file, outside, over 1 MiB) or raises `OSError` makes `ci_steps` raise; the
  brief write exits 2 and `lint_file` returns exit 2 (`UNRUN`) through its existing except.
  A workflow file that is gone is not an error: the job is reported as not at this head.
- III (one behaviour, one function): detection, listing and rendering each live once in
  `brief.py`; the lint reads the steps through `brief.ci_steps`, never a second parser.
- IV (test first): every behaviour has its test task before its implementation task.
- V (ponytail): no new module, no config key, no new event kind. The state key rides the two
  existing `_write_state` closures. `calibrate` is imported lazily and only when an item
  records `ci_jobs`, so hooks that lint a non-CI gate pay nothing.
- VII (security): workflow text never reaches a shell; it is printed into a brief as data.
  `ci_jobs` is producer-owned (FR-009), so a seat cannot clear it to escape the rows.
- Workflow, guard or decision rule changed: yes (the verdict lint), so design 9.2 gains I60
  and `tests/test_invariants.py` its check and mutation.

## Design

### 1. `cli/wuwei/calibrate.py` `_workflow` (line 201): steps

Each job dict gains `'steps': []`. Inside a job, a `steps:` key at the job property indent
(`prop`) opens the step list; each line at the list indent that starts with `-` opens a step
`{'name': None, 'run': None, 'line': <number>}` and the text after `- ` is read as that
step's first key. Keys at the step's key indent set `name` (`_scalar(value)`) and `run`:

- `run: <command>` (single line): `_scalar(value)`.
- `run: |`, `run: >`, `run: |-`, `run: >-` (a block scalar): the following lines whose
  indent is greater than the `run` key's indent, dedented by the first such line's indent,
  joined with `\n`. The loop already skips blank and comment lines; that stays (a `#` line
  inside a block is dropped, recorded in a `ponytail:` comment beside the existing one).

Fix the existing single-line regex at line 267 so a block indicator is never a command:
`r'-?\s*run:\s*([^\s|>].*)'`. `job['runs']` keeps its meaning (single-line commands with the
`run:` line number); `fast_check` proposals and `ci_checks` do not change (`TEST_STEP` never
matched `|`).

### 2. `cli/wuwei/brief.py`: three functions beside `checks_line`

```python
# #733: the conclusions pr_actions._fix reports as red (everything but success, neutral, skipped)
RED = ('failure', 'error', 'cancelled', 'timed_out', 'action_required', 'stale', 'startup_failure')


def ci_jobs(text, tree):
    """#733: sorted '<workflow path>#<job id>' of each worktree workflow job the text names:
    'job <name>', '<name> job', or the fix-feedback line '<name>[ (<matrix>)]: <red conclusion>',
    <name> being the job id or its name:."""


def ci_steps(refs, tree):
    """#733: (steps, missing) for recorded refs. steps: one dict per run step in ref order and
    file order, numbered from 1: {'n', 'label' ('<job id> / <step name or unnamed>'),
    'source' ('<path>:<line>'), 'run'}. missing: refs whose job is not in the worktree at this
    head. Raises ValueError naming the file when calibrate skipped a recorded workflow."""


def ci_block(refs, tree):
    """#733: the step block for recorded refs, ending in a newline; '' when there are none."""
```

`tree` is a path; callers pass the item's worktree as recorded in state (an absolute path
string, `brief.write` stores `str(tree)`).

- `ci_jobs` calls `calibrate._workflows(Path(tree), [])` (skipped files simply name nothing)
  and, per job, tests the job id and `job['name'][0]` with `re.escape`d patterns:
  `(?<![\w-])job[ \t]+[`'"]?NAME[`'"]?(?![\w-])` and `(?<![\w-])[`'"]?NAME[`'"]?[ \t]+job\b`
  (case-insensitive), and `^[ \t]*NAME(?: \([^)\n]*\))?:[ \t]*(?:RED)\b` (multiline).
- `ci_steps` collects `found = []` from `calibrate._workflows`; a `skipped` finding whose
  source path is a recorded ref's file raises `ValueError(f'CI workflow {path} unreadable
  ({reason}); fix the file, then retry')`. Only steps with `run` are listed.
- `ci_block` renders, after a first line naming the jobs:

```text
CI steps: this item fixes CI job lint (.github/workflows/ci.yml). Run every step below locally from the worktree root, not only the one that was red, and cite each as one row in your verdict or handoff: CI step <n>: PASS|FAIL|NOT RUN <what ran and what it showed>.
CI step 1: lint / Ruff (.github/workflows/ci.yml:8)
    ruff check .
CI step 2: lint / Types (.github/workflows/ci.yml:10)
    pip install mypy
    mypy cli
CI job .github/workflows/ci.yml#old: not in the workflow file at this head
```

No blank line inside the block (the brief header contract cuts at the first blank line; the
block goes after the body anyway).

### 3. `cli/wuwei/brief.py` `write` (line 376)

After `tree` is known and only when `(role == 'builder' or gate) and tree`:

```python
refs = sorted({*current.get('ci_jobs', ()), *ci_jobs(body + '\n' + current.get('title', ''), tree)})
ci = ci_block(refs, tree)
```

- The text becomes `header + body + '\n' + block + ci`, appending `ci` only when it is not
  already in `body` (a second-opinion copy, `dispatch.opinion` line 779, carries the first
  brief's body including its block).
- In `update(fresh)` (line 557), beside the `track`/`worktree`/`depth` writes:
  `if refs and item in fresh['items']: fresh['items'][item]['ci_jobs'] = refs`.
- An item that names no job and records none: `refs == []`, `ci == ''`, no key written, the
  brief is byte-for-byte today's.

### 4. `cli/wuwei/commands/build.py` `open_fix` (line 186)

Extend the function's existing import to `from wuwei.brief import ci_block, ci_jobs,
launch_prompt` (the local name `brief` is a path there), then, before the non-resume
`brief_writer.write`:

```python
refs = sorted({*data['items'][item].get('ci_jobs', ()), *ci_jobs(feedback, record['worktree'])})
ci = ci_block(refs, record['worktree'])
...
prompt = launch_prompt(brief, agent_path(root, 'builder'), root=root) + '\n\n' + feedback + ('\n' + ci if ci else '')
```

and in its `update(fresh)` (line 232): `if refs: fresh['items'][item]['ci_jobs'] = refs`.
The non-resume path's `brief_writer.write` also records them (Design 3); the union keeps the
two writes equal. Detection runs before the new fix brief is written, so a skipped workflow
refuses the round before any state changes.

### 5. `cli/wuwei/dispatch.py`: delta continue prompts

- `_seats`, line 567, and `opinion`, line 790 (its delta branch): append the block of the
  item's recorded jobs to the delta feedback, so the resumed seat (whose brief predates a job
  named later) gets the steps the lint will require:

```python
ci = brief.ci_block(row.get('ci_jobs', ()), Path(row['worktree']))
feedback = _delta_feedback(...) + ('\n' + ci if ci else '')
```

  `row` is `data['items'][item]` at `_seats` and the existing `row` in `opinion`. The same two
  lines at both sites; no new helper. The initial gate brief needs nothing here:
  `brief.write` adds the block from the item record.

### 6. `cli/wuwei/verdict.py`

- `FORMAT` gains, after `Probe`:
  `'CI step': ('`CI step <n>: PASS|FAIL|NOT RUN <what ran and what it showed>`, one row for each CI step your brief lists, at every depth', 'CI step 1: PASS ruff check . exited 0')`.
  The rendered example then carries a CI row; with no steps the lint ignores it, so I44 stays
  green.
- One function holds the rule (also the mutation hook for I60):

```python
CI_ROW = re.compile(r'^[ \t]*(?:[-*+][ \t]+)?CI step (\d+):[ \t]*(PASS|FAIL|NOT RUN)\b[ \t]*\S', re.I | re.M)


def ci_rows(text, verdict, steps):
    """#733: failures for the CI steps a verdict must cite: one row per step, no FAIL under PASS."""
```

  For each `(n, label)` in `steps`: no row gives
  `f'CI step {n} ({label}) has no result row' + _fix('CI step')`; more than one gives
  `f'CI step {n} has {k} result rows; write one'`; `verdict == 'PASS'` with a `FAIL` row gives
  `f'PASS verdict with CI step {n} FAIL' + _fix('Verdict')` plus `', or rerun the step'`.
- `lint(..., steps=())` appends `ci_rows(text, verdict, steps)` to `failures` after the Head
  check. Light depth does not skip it.
- `lint_file` passes `steps=ci_steps(path, data)`, a new reader beside `recorded_docs`:

```python
def ci_steps(path, data):
    """#733: [(n, label)] the gate file's seat item must cite; () when the seat or item is
    unresolved or records no ci_jobs. A recorded workflow that cannot be read raises."""
```

  It resolves the seat and item as `light` does (catching `KeyError`, `TypeError`,
  `ValueError`, `AttributeError` for the resolution only), then returns
  `[(s['n'], s['label']) for s in brief.ci_steps(row['ci_jobs'], Path(row['worktree']))[0]]`.
  `ValueError` and `OSError` from `brief.ci_steps` reach `lint_file`'s existing except and
  become exit 2.

### 7. `cli/wuwei/state.py` `_producer_error` (line 341)

Add `'ci_jobs': 'wuwei brief or the fix round (wuwei build next, wuwei pr act)'` to the item
producer map.

### 8. Charters, agents, docs, design

- `charters/builder.md`: one sentence at the end of step 9 (handoff): "When your brief has
  `CI step` lines, the item fixes a CI job: run every listed step from the worktree root with
  the command shown, not only the step that was red, and report one
  `CI step <n>: PASS|FAIL|NOT RUN <what ran and what it showed>` line per step in your
  handoff."
- `charters/sentinel-goal.md`: one sentence in step 1: "When the brief lists `CI step` lines,
  run each at the reviewed head and write its row; a listed step the builder's handoff does
  not show passing, or that fails at the head, is a blocking gap (`blocks: yes`)."
- `bin/wuwei agents build` regenerates `agents/builder.md`, `agents/sentinel-goal.md` and
  every `agents/sentinel-*.md` Verdict format section. Never hand-edit `agents/`.
- `docs/site/reference.md`, "The lint rules" list (line 367): one bullet for the CI step rows.
- `docs/specs/2026-09-24-wuwei-design.md` 9.2: append row `I60` (text in tasks T016).

## What must not change

- Items that name no job: brief text, header lines and state are unchanged; every existing
  `tests/test_brief.py` test passes untouched.
- `verdict.lint` with no `steps`: identical results; `guards/pr.py:117`, `:181`,
  `obligations.py:132` and `dispatch.py:702` keep calling it without steps.
- `job['runs']`, `fast_check` proposals and `ci_checks` in `calibrate`.
- The brief header (no new header line; `launch_prompt` reads only `Depth:` from it).
- `LIGHT_GATE`, `GATE_BODY`, `_delta_feedback`'s own text.

## Files

| File | Change |
| --- | --- |
| `cli/wuwei/calibrate.py` | `_workflow` records steps; run regex excludes the block indicator |
| `cli/wuwei/brief.py` | `RED`, `ci_jobs`, `ci_steps`, `ci_block`; `write` records and appends |
| `cli/wuwei/commands/build.py` | `open_fix` records the jobs and appends the block to the prompt |
| `cli/wuwei/dispatch.py` | delta continue prompts carry the block |
| `cli/wuwei/verdict.py` | `FORMAT['CI step']`, `CI_ROW`, `ci_rows`, `ci_steps`; `lint(steps=)`; `lint_file` |
| `cli/wuwei/state.py` | producer name for `items.*.ci_jobs` |
| `charters/builder.md`, `charters/sentinel-goal.md` | the rule |
| `agents/*.md` | regenerated by `bin/wuwei agents build` |
| `docs/site/reference.md` | lint rule bullet |
| `docs/specs/2026-09-24-wuwei-design.md` | 9.2 row I60 |
| `tests/test_calibrate.py`, `tests/test_brief.py`, `tests/test_dispatch.py`, `tests/test_verdict.py`, `tests/test_invariants.py` | tests |
