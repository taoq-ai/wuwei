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
by `:` and gap text that starts with a letter or digit. Every `#` in the question belongs to that
chain, so the hook records exactly the PRs the chain names. Any other `exception:` question is refused with the existing
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
   after the sha, a tab or newline around the colon, a gap that starts with a mark, a `#` in the
   prose before the refs). The guard now refuses it. The refusal names the shape, so the lead resends
   in one turn; nothing is recorded wrong.
2. A gap that names another PR ref (`blocked by #12 at abc1234`) is refused, because the hook would
   read that ref as a further PR and record an empty gap. The lead must word the gap without
   `#n at <sha>`. No gap `wuwei evidence` prints holds such a ref.
3. A gap followed by a newline and more text (`: CI failing\nAccept?`) is recorded with the next
   line in it, because the hook cuts the gap only at ". " or "?". The recorded gap still holds the
   written one, so evidence.excepted matches it. Left to the exception-parser follow-up.

## Clarifications

### Session 2026-10-18

- Q: Is prose before the first ref still allowed (`exception: for the hotfix o/r#1 at abc1234: ...`)?
  A: Yes, without a `#` in it (gate round 1). The hook records every ref in the question, so a ref in
  the prose (`o/r#9 at 9999999 was rejected; only o/r#1 at abc1234: ...`) would record an approved
  ruling on a PR the owner did not accept.
- Q: What counts as "followed by : and a gap"? A: After the last ref, optional spaces, `:`, optional
  spaces, then a letter or digit (`[^\W_]`), and no further `#n at <sha>` from there on. The hook's
  `lstrip(' :')` strips exactly those spaces and colons, so the recorded gap starts at the letter or
  digit the owner reads. Every gap `wuwei evidence` prints starts with one; an invisible character
  such as U+200B is refused.
- Q: Why spaces only around the colon? A: The hook strips only spaces and colons. A tab or newline
  there was recorded as a gap that starts with ":", or as the next line (`:\nAccept?`).
- Q: How is the match kept linear? A: The prefix cannot pass a `#`, a repo starts only at a word
  start (`(?<![\w.-])`), and the spaces after the colon are possessive (`*+`).
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

Acceptance 1, plus: refs joined by `and` then prose, a gap followed by another ref (on the same or
the next line), a gap that names a ref, an empty or invisible gap, no colon, a tab before the colon,
a newline after it, a ref in the prose before the chain, the same PR at another sha in that prose,
and a leading space are each refused with the shape.

### US2: a question in the shape reaches the owner and is recorded (P1)

Acceptance 2 and 3, plus a capitalised class word and prose before the ref.

### US3: the guard and the hook agree (P1)

A generated set of questions (prefixes x refs x separators x gaps x tails) holds no question the
guard passes and the hook records as nothing, with refs other than the chain names, or with a gap
other than the one written.

### US5: a long question is read in linear time (P2)

Six pathological 36,000-character questions each take under 0.5 s.

### US4: no route moves (P1)

Acceptance 4.

## Requirements

- FR-001: `guards.pre_tool` refuses an `exception:` question unless its last
  `owner/repo#n at <sha7>` ref is followed by `:` and a gap that starts with a letter or digit, with
  the existing reason.
- FR-001a: No `#` may appear before the ref chain, so the hook records only the chain's refs.
- FR-002: The question must start with `exception:` with no leading whitespace.
- FR-003: `owner review:` and `breaking:` questions pass and fail exactly as before.
- FR-004: No route in `tests/fixtures/routes.json` changes verdict or reason.
- FR-005: Runtime grows by at most 2 lines; `.claude/wuwei/` matches `cli/wuwei/`.

## Assumptions

- No recorded route asks an `exception:` in the "at <sha>." form expecting it to record. Overturned
  if a corpus row moves (none did: 0 of 251).
- routes.json stays as it is, because it reads shell commands only. Overturned if the owner wants
  question shapes in the corpus.
- Round 1 narrows the whitespace around the colon to spaces (quality's low notes (a) and (b)), in
  the same regex, so the recorded gap is the written one. Overturned if a lead's real question needs
  a newline there.
- Refusing a leading space before `exception:` is inside the promise ("the shape
  hook.exception_refs reads"). Overturned if the owner wants the hook to strip instead.

## Rollback

Revert the commit. No config key, ledger kind or file format changes; rulings already recorded stay
as they are.
