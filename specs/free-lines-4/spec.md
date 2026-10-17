# Feature Specification: free runtime lines with no behaviour change, and make the dense guard lines readable

**Feature branch**: `claude/free-lines-4`
**Item**: free-lines-4, tier full, goal G-2
**Input**: the runtime sits at 2,999 of its 3,000 lines, so every runtime fix waits for headroom.
The shell-doors quality gate also named two dense lines in `guards.py` as hard to read.

## The promise in my words

Shrink `cli/wuwei/` by at least 22 lines without changing what any function returns, and split the
two dense guard lines into named parts. The changes are fixed by the item:

1. A value bound and then tested on the next line (`x = f(...)` then `if x:` or `if not x:`) becomes
   one `if x := f(...):` line, in guards, sync, plan, upgrade, evidence, report, hook, setup and
   verdict, where the line stays within 150 characters and reads at least as clearly. A rewrite
   that reads worse is skipped: `if repo := match[1] or repo:` in `hook.exception_refs` stays two
   lines.
2. In `guards.bash` the leak, git push and gh checks take the same found-then-return form.
3. In `guards.segments` the `$'`/`$"` check and the glued-redirect check become two named
   booleans, `dollar` and `glued`. The `tokens[2:] + ['']` end sentinel stays, with a comment that
   says why: without it zip drops the last pair.
4. The input-redirect line in `guards._unwrap` becomes an explicit if/else.
5. `OPS` drops only `;;`, which the single-character fallback splits into `;` `;`, read the same.
   `&&`, `||`, `|&` and `&>` stay, because dropping any of them changes how some punctuation runs
   split. The item also dropped `\|\|`; the arch gate showed that `||&>` then splits as `|`, `|&`,
   `>` instead of `||`, `&>` (see Clarifications).
6. The ledger refusal text becomes one constant, `LEDGER_DENIED`, read at its three call sites.

The vendored copies under `.claude/wuwei/cli/wuwei/` are re-vendored to match.

The acceptance scenarios, restated:

1. `cat cli/wuwei/*.py | wc -l` prints 2,977 or less, and `.claude/wuwei/cli/wuwei/` is identical to
   `cli/wuwei/`.
2. The full suite passes. No existing test changes; the only test change is the new split tests.
3. A generated probe feeds `guards.segments` at 9d6701e and at the head every command built from
   24 operators in pairs, 6 words in pairs and 4 positions (82,944 commands). 0 outputs differ.
4. `guards.OPS` still holds `&&`, `|&` and `&>`. A test splits `x&&>|y` into x, &&, >|, y and
   `x|&>y` into x, |&, >, y.

## How this fails

1. A walrus rewrite binds a different value than the two-line form did, for example by operator
   precedence: `if x := a or b` binds `a or b`, but a missed parenthesis in `if not (x := f())`
   would bind `not f()`. Guarded by the full suite and by reading every rewritten line in the diff.
2. Merging an `if found:` into the `elif program == 'gh'` chain lets a gh command with no finding
   fall through to a later `elif` branch it never reached before. Here the only later branch is
   `program in INFRA`, and `gh` and `git` are not in `INFRA`, so nothing new runs.
3. Dropping an alternative from `OPS` changes how a run of punctuation splits, so a glued redirect
   or separator reads differently and a door is missed or a clean command is refused. Guarded by
   the 82,944-command differential probe, an exhaustive probe of every punctuation run over
   `|&;<>()` up to length 5, and the new split tests, which fail when `&&`, `||`, `|&` or `&>` is
   dropped.

## Requirements

- FR-001: `cli/wuwei/` totals 2,977 lines or fewer and adds no line elsewhere in the runtime.
- FR-002: `guards.segments` returns the same output as at 9d6701e for every probe command.
- FR-003: `guards.OPS` holds `&&`, `||`, `|&` and `&>`; it no longer holds `;;`.
- FR-004: the `tokens[2:] + ['']` sentinel stays with a comment naming why.
- FR-005: the three ledger refusal call sites read `LEDGER_DENIED`.
- FR-006: `.claude/` matches what `setup.vendor()` writes from the tree.

## Clarifications

### Session 2026-10-17

- Q: The prototype puts the glued check on one line of 151 characters. Does it stay? A: No. The
  promise caps rewritten lines at 150 characters, so the generator moves to a second line and the
  sentinel comment takes its own line above it.
- Q: Does the `_unwrap` if/else keep the prototype's `targets += [] if ... else [...]`? A: No. A
  nested `if not re.fullmatch(...)` with `targets.append(...)` is the explicit form the item asks
  for, and it costs one line.
- Q: Which test pins `&>`? A: Acceptance 4 names only the `&&` and `|&` runs. A third split case,
  `x&>;y`, pins `&>` too, since the item keeps it for the same reason.
- Q: Does `\|\|` leave OPS as the item says? A: No. The arch gate at 50f66d8 found that without it
  `\|&` matches at the second pipe of `||&>`, so `||&>` and `||&>>` split differently: 72 of 20,736
  operator pairs trailing both words differ, and `guards.bash` turns 62 targeted denials into
  allows. `\|\|` is restored, a split case `x||&>y` pins it, and the differential probe now also
  covers every punctuation run up to length 5 alone, glued, spaced and trailing. This overturns
  promise (5) for `||`; it costs no line.

## Assumptions

- The `pre_tool` ledger check fits on one line once it names `LEDGER_DENIED` (89 characters), so
  it joins. Overturned if the quality gate reads it as worse; it costs one line.
- `LEDGER_DENIED` uses double quotes so the apostrophe needs no escape. The text is unchanged.
- The skipped `hook.exception_refs` rewrite and the two longer lines (the sentinel comment and the
  split generator) leave the runtime at 2,976, inside the 2,977 ceiling and above the 22-line floor
  (23 freed).

## Rollback

Revert the commit. No data, config or contract depends on the refactor.
