# Implementation Plan: the next-step test also collects `x or 'literal'` fallbacks

**Branch**: `456-reasons-or-fallbacks` | **Spec**: `specs/456-reasons-or-fallbacks/spec.md`

## Summary

One branch in the test's `_text` makes the #362 ratchet see `or` fallbacks; the 19
fallbacks it then finds each gain a next step, in place, as string edits. No runtime
behaviour changes.

## Technical Context

Python 3.11+, stdlib only. The test uses `ast` and `re`, as today. No new file under
`cli/`, no new helper, no new constant, no new import except where noted (none needed:
`inbox.py` already imports `ADAPTER_DATA`).

## Constitution Check

- I stdlib only: yes.
- II exits: unchanged; every edited site keeps its exit, exception type and control flow.
- III one behaviour, one function: the collector stays in `tests/test_reasons.py`; the
  change is one branch in `_text`, the function every reason site already routes through.
- IV test first: the fixture test fails before the collector change; the wall test fails
  after the collector change and before the rewrites (T001 to T004 in tasks.md).
- V ponytail: reuse `_text` recursion and `_passthrough`; no new allowlist; no family
  constant invented; the `ADAPTER_DATA` family is reused where its text is true.
- VII security: no new data in any message; texts name commands only.

## Design

### 1. `tests/test_reasons.py` `_text`: one branch

Add before the final `return []` (next to the `IfExp` branch):

```python
    if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or):  # x or 'fallback' (#456)
        return [] if _passthrough(node.values[-1]) else _text(node.values[-1])
```

`_passthrough` is defined below `_text`; it is resolved at call time, so order does not
matter. Do not touch `add`, `reasons`, `NEXT_STEP`, `KEEP`, `PERSON_MODULES` or
`PERSON_PARTS`.

### 2. `tests/test_reasons.py`: new fixture test

Next to `test_collector_finds_a_new_bare_wall`:

```python
def test_collector_finds_an_or_fallback_wall():
    texts = lambda source: [text for _, text, _ in reasons(source)]
    assert texts("raise ValueError(result.reason or 'branch protection unmeasured')") == [
        'branch protection unmeasured']
    assert texts("import sys\nprint(result.reason or f'{name}: unreadable scopes', file=sys.stderr)") == [
        '{}: unreadable scopes']
    assert texts("Result(2, None, a or b or 'poll failed now')") == ['poll failed now']
    assert reasons("raise ValueError(result.reason or f'{exc}')") == []
    assert reasons("raise ValueError(result.reason or f'build: {exc}')") == []
```

(A named `def` instead of the lambda is fine if a linter objects.)

### 3. The 19 fallbacks: exact new texts

Keep the left operand and the leading text; append the step. Seat-facing unless marked
person. The `{...}` values stay the expressions the code has.

| File:line (main) | New fallback literal |
|---|---|
| `shepherd.py:168` and `:178` (`ping_gate`) | `'branch protection unmeasured; retry; if it repeats, run bin/wuwei config check, which reads the protection and names the source'` |
| `brief.py:91` (`read`) | `'adapter read unavailable; retry; if it repeats, run bin/wuwei doctor, which tests the adapters'` |
| `commands/build.py:335` | `'fast check could not run; rerun bin/wuwei fast-checks in the worktree; if it repeats, run bin/wuwei doctor'` (mirrors `:330`) |
| `commands/config.py:265` (`_protection`) | `f"{repo['name']}: unreadable protection result; retry; if it repeats, run bin/wuwei doctor, which tests the code host adapter"` |
| `commands/config.py:302` | `f'{name}: unreadable scopes; retry; if it repeats, run bin/wuwei doctor, which tests the code host adapter'` |
| `commands/doctor.py:547` (`_dry`, person) | `f'dry run exit {code} with no output; run the fix command by hand to see its error'` |
| `commands/doctor.py:582` (`_reconfirm_preview`, person) | `'nothing to confirm; run bin/wuwei integrity check to see the current verdict'` |
| `commands/doctor.py:598` (`_promote_preview`, person) | `'nothing to promote; run bin/wuwei config promote to see its output'` (build: `config.promote` always reaches the confirm call through `offer`, so an empty run does not show config.toml matches the calibration) |
| `commands/runtime.py:52` | `'runtime operation did not complete; retry; if it repeats, run bin/wuwei doctor'` |
| `consolidation.py:108` | `'could not commit archived days; retry with bin/wuwei consolidate; if it repeats, run bin/wuwei doctor'` |
| `control_plane.py:120` (`poll_replies`) | `'control plane: poll failed; retry; if it repeats, run bin/wuwei doctor'` |
| `control_plane.py:137` (`poll_replies`) | `'control plane: echo failed; retry; if it repeats, run bin/wuwei doctor'` |
| `inbox.py:56` | `f'inbox: redactor returned malformed data; {ADAPTER_DATA}'` (family; already imported) |
| `integrity.py:275` (`cached`) | `'plugin integrity unmeasured; run bin/wuwei integrity check, which measures it again'` |
| `obligations.py:21` (`_read`) | `'code-host read unavailable; retry; if it repeats, run bin/wuwei doctor, which tests the code host adapter'` |
| `registry.py:120` (`data`) | `'VCS operation unavailable; retry; if it repeats, run bin/wuwei doctor'` |
| `scanner.py:151` | `'scanner unavailable; retry; if it repeats, run bin/wuwei doctor'` |
| `steward.py:230` | `'steward runtime could not launch; retry; if it repeats, run bin/wuwei doctor'` |

Every text above was checked against `NEXT_STEP`, `PRONOUN` and `OWNER` of the test: all
match `NEXT_STEP`, none has a pronoun or "the owner". Line numbers are main at d911002;
match by file and old text if they drift.

## What must not change

- `NEXT_STEP`, `LABEL`, `PRONOUN`, `OWNER`, `KEEP`, `PERSON_MODULES`, `PERSON_PARTS`, `add`,
  `reasons`, `all_reasons` and every other test in `tests/test_reasons.py`.
- The left operand of every edited `or` (`result.reason`, `record['reason']`,
  `text.strip()`, `getattr(result, 'reason', '')`), exception types, exit codes, the
  `Result` shapes, control flow. A real adapter reason still wins over the fallback.
- `or` fallbacks outside the collected call shapes (spec Deferred).
- Hook path imports and latency: only string literals change.

## Risks for the builder

- `registry.py` and `integrity.py` are on the hook path; a string edit is free, an import
  is not. None is needed.
- Long lines are the norm in these files (see `shepherd.py:142`); keep each text on one
  logical line, or split it with adjacent literals inside parentheses (the parser folds
  them into one node, so the collector sees one text), as `shepherd.py:65` does.
