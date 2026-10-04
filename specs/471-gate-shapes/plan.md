# Implementation Plan: quoted owner mentions are data, lead goals in either shape, question lint warns outside strict

**Branch**: `471-gate-shapes` | **Spec**: `specs/471-gate-shapes/spec.md`

## Summary

Three small changes, each at the one spot every caller routes through:

1. `protect_state._owner_action`: a reader is `_READERS` or the shared `wuwei.shell.reads`;
   readers' argv is not scanned for the CLI word, and a call made only of readers has no
   unseen-mention refusal. Three edited lines.
2. `goals.proposed`: ids-only lead goals raise one seat-facing reason; the host-terminal
   tail of every `goals.parse` reason is replaced by the same next step. `rank.py` and
   `plan.py` already call `goals.proposed`, so they do not change.
3. `guards.AREAS['decision.check_question'] = 'outward'` and a one-line `Morning gate`
   reason in `decision.check_question`. The hook's existing `posture()` does the warn,
   the `guard.would_refuse` event and the strict refusal.

Then text: lead charter step 3 (regenerate agents), plan skill step 2, the posture table
cell in the design spec and the site docs, and one lint pattern.

## Technical Context

Python 3.11+, stdlib only. Tests: pytest, in process, under `tmp_path`, with
`WUWEI_WORKSPACE`/`WUWEI_NOW` as the existing fixtures set them. `wuwei rank` runs in
process through `wuwei.__main__.main` as `test_rank_lead_json_on_provisional_goals` does;
`plan propose` reuses the `empty` fixture and `lead()` in `tests/test_plan.py`. No new import on
the hook path: `reads` comes from `wuwei.shell`, which `_owner_action` already imports from.

## Constitution Check

- I stdlib only: yes.
- II exits: unchanged; guard errors stay exit 2; `rank`/`plan propose` stay exit 2 with the
  reason printed.
- III one behaviour, one function: the reader test is `shell.reads` (shared, #349); the goal
  shape rule lives once in `goals.proposed`; the posture decision stays in `hook.posture`
  via `guards.level`.
- IV test first: every task pair in `tasks.md`.
- V ponytail: no new posture area, no new helper, no change to `shell.py`, no per-word
  re-parse, no mover allowlist.
- VII security: every command-position refusal and every executor probe stays; the only
  relaxation is a call in which no command can execute anything.

## Design

### 1. `cli/wuwei/guards/protect_state.py` `_owner_action` (lines 167-239)

```python
from wuwei.shell import _launcher, is_opaque, mentions, reads          # line 170
...
readers = [bool(c.argv) and (Path(c.argv[0]).name in _READERS or reads(c.argv, cwd))
           for c in commands]                                            # line 174
...
            if not relevant or readers[index]:                           # line 196
...
    if relevant and unseen > 0 and not all(readers):                     # line 235
```

- Line 196 uses `readers[index]` so a `jq` or `cat` filter string is never scanned with
  `_CLI_WORD`; `feeds` (lines 176-179) already uses `readers`, so a reader piped into a
  non-reader still marks its mentions unseen.
- Line 235: a call whose every command is a reader cannot run anything, so a mention in a
  heredoc body, a comment or a reader's redirected text is data. Add a one-line comment
  saying so.
- Keep the `_READERS` comment accurate: it now lists only the readers `reads()` does not
  cover (`echo`, `printf`, `rg`, `cut`, `tr`).

What must not change: `_wuwei_action`, `_pair`, `_OWNER_ACTIONS`, `_owner_relevant`, the
xargs, non-literal and gate-edit branches, `check_bash`, `owner_script`, the `ParseError`
branch, and `cli/wuwei/shell.py` (owned by #469 and #470 this wave). The source-count test
for the `Opaque owner action` string (`tests/test_protect_state.py:948`, count 2) stays true.

Verified in a scratch copy with these three edits: `tests/test_owner_actions.py`,
`tests/test_protect_state.py`, `tests/test_launcher_relevance.py`,
`tests/test_owner_edits.py` pass except the one regression row the issue flips.

### 2. `cli/wuwei/goals.py`

`parse`: replace the tail `; the owner fixes memory/goals.md with bin/wuwei goals edit in a
host terminal` in all 8 reasons (lines 29, 32, 37, 40, 47, 52, 57, 59) with
`; have the lead write goals as blocks (outcome, measure, target, date, priority), or run
/wuwei:wuwei-plan again`. Keep it inline in each literal (no module constant):
`tests/test_reasons.py` reads the literal text of each reason for its next step, and a
`{FIX}` placeholder would hide it.

`proposed`: after the `defined(text)` early return and before the dict-only check, raise
for string entries:

```python
    if defined(text) or not isinstance(goals, list) or not goals:
        return text, False
    ids = [goal for goal in goals if isinstance(goal, str)]
    if ids:
        raise ValueError(f'the lead JSON names {", ".join(ids)} without its block; have the lead '
                         'write goals as blocks (outcome, measure, target, date, priority), or run '
                         '/wuwei:wuwei-plan again')
    if not all(isinstance(goal, dict) for goal in goals):
        return text, False
```

Callers unchanged: `commands/rank.py:40` prints `wuwei rank: <reason>` and exits 2;
`plan.propose` (`plan.py:99`) raises it and `commands/plan.py` prints `wuwei plan: <reason>`
and exits 2. `rank template`, `plan template`, `plan approve` and the confirmed-goals path
(`defined(text)` true) are untouched.

### 3. `tests/test_owner_records_lint.py`

Add `\bowner fixes memory/` to `PATTERN` (one alternative). `test_lint_catches_planted_instruction`
asserts the planted old goals sentence is reported. With design 2 done, the repository scan
stays clean (`merge.py` and `shepherd.py` say "the owner fixes" about config, not `memory/`).

### 4. `cli/wuwei/guards/__init__.py` `AREAS` (lines 39-43)

Add `'decision.check_question': 'outward'`. `level()` already resolves `module.function`
keys before the module key, so `check_write`, `record_gate` and `check_stop` stay `records`
(floor). `hook.posture` (`commands/hook.py:232-271`) then records one `guard.would_refuse`
with `guard: decision`, `area: outward` under `observe`/`guarded` and enforces with
`posture: outward = block (set security.areas.outward)` under `strict`.
`tests/test_posture.py::test_guard_areas_table` accepts dotted keys whose area is in
`workspace.AREAS`; `tests/test_telemetry.py:129` needs the area in `telemetry.AREAS`
(`outward` is).

### 5. `cli/wuwei/guards/decision.py`

Split the `Morning gate` mark out of `gate_question` into a tiny helper used by both:

```python
def _morning(question, text):
    header = question.get('header', '')
    return text.startswith('Morning gate') or (isinstance(header, str) and header.startswith('Morning gate'))
```

In `check_question`, where `ids` is empty (line 190): if `_morning(question, text)`, append
`(1, f'Morning gate questions cite {rel}' + ('' if plan.is_file() else '; run bin/wuwei plan propose <lead.json> first'))`
with `plan = workspace.day_dir(root) / 'plan.md'` and `rel = plan.relative_to(root / '.wuwei').as_posix()`
(`days/<date>/plan.md`); otherwise append `(1, hint)` as today. A morning question that
does cite `D-n`/`C-n` keeps the record lint path. `gate_question` keeps its contract, so
`record_gate` and the #357 allowance are unchanged.

### 6. Text

- `charters/lead.md` step 3: add "While `memory/goals.md` has none, write each proposed
  goal in `goals` as a block (`id`, `outcome`, `measure`, `target`, `date`, `priority`),
  never an id alone." Regenerate `agents/` with `bin/wuwei agents build`
  (`tests/test_agents.py::test_checked_in_agents_match_charters_and_allowlist`).
- `skills/wuwei-plan/SKILL.md` step 2: after "Ask for one JSON proposal ...", add "While
  `memory/goals.md` has no goals, the lead writes each proposed goal in `goals` as a block
  (id, outcome, measure, target, date, priority), never an id alone; if `rank` or
  `plan propose` says the lead JSON names a goal without its block, dispatch the lead again
  for blocks."
- `docs/specs/2026-09-24-wuwei-design.md` section 9 posture table and
  `docs/site/security.md` (line 50): the `outward` row's "What it covers" becomes
  "The outward text lint (`outward`) and the question citation check
  (`decision.check_question`)". Levels are unchanged, so
  `tests/test_docs.py::test_security_posture_table_matches_the_code` still passes.

No em-dashes, no emojis, no absolute local paths in any of it.

## Files

| File | Change |
| --- | --- |
| `cli/wuwei/guards/protect_state.py` | design 1 (3 lines and a comment) |
| `cli/wuwei/goals.py` | design 2 |
| `cli/wuwei/guards/__init__.py` | design 4 (one dict entry) |
| `cli/wuwei/guards/decision.py` | design 5 |
| `charters/lead.md`, `agents/lead.md` (generated) | design 6 |
| `skills/wuwei-plan/SKILL.md` | design 6 |
| `docs/specs/2026-09-24-wuwei-design.md`, `docs/site/security.md` | design 6 |
| `tests/test_owner_actions.py`, `tests/test_goals_rank.py`, `tests/test_plan.py`, `tests/test_owner_records_lint.py`, `tests/test_decision.py`, `tests/test_posture.py`, `tests/test_docs.py` | tests |

Not changed: `cli/wuwei/shell.py`, `cli/wuwei/commands/rank.py`, `cli/wuwei/plan.py`,
`cli/wuwei/commands/hook.py`, `cli/wuwei/workspace.py`.
