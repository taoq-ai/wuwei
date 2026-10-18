# Feature Specification: an exception: question names its gap after its refs, or it is refused

**Feature branch**: `fix/exception-shape`
**Item**: exception-shape (issue #1130), tier full, goal G-2
**Input**: `guards.pre_tool` passes an `exception:` question once it finds one `owner/repo#n at <sha7>`
anywhere in it. `hook.exception_refs` records the gap only from the text after the last ref, up to
the first ". " or "?". A question like `exception: o/r#1 at abc1234. Some prose. Accept?` passes the
guard, reaches the owner, and the owner's answer is recorded as nothing: no ruling, no follow-up.

## The promise in my words

The guard lets an `exception:` question through only when the hook will record it. That means: the
question starts with `exception:` (any case, no leading space, as the hook reads it), names at least
one `owner/repo#n at <sha7>` (optionally joined by ` and #m at <sha7>`), and the last ref is followed
by `:` and gap text that is not empty. Any other `exception:` question is refused with the existing
"Use the exact shape" text, which already names the shape. `owner review:` and `breaking:` keep
their current shapes. The change is one regex in the AskUserQuestion branch of `guards.pre_tool`,
plus tests and the vendored copy. Runtime lines grow by 1 (budget 2).

The acceptance scenarios, restated:

1. `exception: o/r#1 at abc1234. Some prose. Accept?` is refused; the reason names the shape
   `exception: owner/repo#n at <sha7> [and #m at <sha7>]: <the gap as wuwei evidence prints it>. <question>`.
2. `exception: o/r#1 at abc1234: gates missing at head abc1234: quality. Accept?` answered Accept
   leaves one ruling row: kind exception, pr o/r#1, head abc1234, gap
   `gates missing at head abc1234: quality`.
3. `exception: o/r#1 at abc1234 and #2 at def5678: no test in the diff. Accept?` passes the guard.
4. Every route in `tests/fixtures/routes.json` reads the same at main and at the head.

## How this fails

1. A lead writes an exception in a near shape the hook could read (refs joined by a comma, no colon
   after the sha, a gap that starts with "." or ":"). The guard now refuses it. The refusal names the
   shape, so the lead resends in one turn; nothing is recorded wrong. Probe: 70,285 of the 462,000
   generated questions fall here, all off the documented shape.
2. A gap that names another PR ref (`blocked by #12 at abc1234`) is refused, because the hook would
   read that ref as a further PR and record an empty gap. The lead must word the gap without
   `#n at <sha>`. No gap `wuwei evidence` prints holds such a ref.
3. The lazy prefix and the lookahead make the match quadratic on a pathological question. Measured:
   2,000 repeated refs (36,011 characters) take 0.36 s; real questions are a few hundred characters.

## Clarifications

### Session 2026-10-18

- Q: Is prose before the first ref still allowed (`exception: for the hotfix o/r#1 at abc1234: ...`)?
  A: Yes. The hook reads refs anywhere and the gap after the last one, so the guard keeps the lazy
  prefix it had.
- Q: What counts as "followed by : and a gap"? A: After the last ref, optional whitespace, `:`,
  optional whitespace, then a character that is not whitespace, `.`, `?` or `:`, and no further
  `#n at <sha>` from there on. That character survives the hook's `lstrip(' :')`, its split at
  ". " or "?", its `strip()` and its `rstrip('.')`, so the recorded gap is never empty.
- Q: Why refuse a leading space before `exception:` now? A: The hook's `exception_refs` checks
  `question.lower().startswith('exception:')` without stripping, so such a question was recorded as
  nothing too. The guard reads it the same way. `owner review:` and `breaking:` keep their leading
  `\s*`, which their hook regex also allows.
- Q: Does the refusal text change? A: No. It already names all three shapes.
- Q: Does routes.json gain rows? A: No. The corpus holds shell commands read through `guards.bash`;
  an AskUserQuestion never reaches that path. The new question cases live in `tests/test_guards.py`
  and `tests/test_hook.py`.

## User Scenarios & Testing

### US1: a question the hook cannot record is refused (P1)

Acceptance 1, plus: refs joined by `and` then prose, a gap followed by another ref, a gap that names
a ref, an empty gap (`: .`), and a leading space are each refused with the shape.

### US2: a question in the shape reaches the owner and is recorded (P1)

Acceptance 2 and 3, plus a capitalised class word and prose before the ref.

### US3: the guard and the hook agree (P1)

A generated set of questions (prefixes x refs x separators x gaps x tails) holds no question the
guard passes and the hook records as nothing.

### US4: no route moves (P1)

Acceptance 4.

## Requirements

- FR-001: `guards.pre_tool` refuses an `exception:` question unless its last
  `owner/repo#n at <sha7>` ref is followed by `:` and non-empty gap text, with the existing reason.
- FR-002: The question must start with `exception:` with no leading whitespace.
- FR-003: `owner review:` and `breaking:` questions pass and fail exactly as before.
- FR-004: No route in `tests/fixtures/routes.json` changes verdict or reason.
- FR-005: Runtime grows by at most 2 lines; `.claude/wuwei/` matches `cli/wuwei/`.

## Assumptions

- No recorded route asks an `exception:` in the "at <sha>." form expecting it to record. Overturned
  if a corpus row moves (none did: 0 of 251).
- routes.json stays as it is, because it reads shell commands only. Overturned if the owner wants
  question shapes in the corpus.
- Refusing a leading space before `exception:` is inside the promise ("the shape
  hook.exception_refs reads"). Overturned if the owner wants the hook to strip instead.

## Rollback

Revert the commit. No config key, ledger kind or file format changes; rulings already recorded stay
as they are.
