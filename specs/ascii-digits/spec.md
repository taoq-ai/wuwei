# Feature Specification: PR numbers in owner answers, verdicts, refs and CLI arguments are ASCII digits only

**Feature branch**: `claude/ascii-digits`
**Item**: ascii-digits, tier full, goal G-2
**Input**: the security gate on draft-raise (#1102). Python's `\d` and `str.isdigit()` accept
Unicode digits and `int()` converts them, so an owner question naming `o/r#７` records a ruling
for a PR that no ASCII reader names, and `wuwei evidence o/r#７` reads PR 7. #1102 made the guards
ASCII-only; these readers were left.

## The promise in my words

Every regular expression under `cli/wuwei` that reads a number spells the digit class `[0-9]`,
and every `isdigit()` call sits right after an `isascii()` check on the same value. A PR number
written in fullwidth (`７`), Arabic-Indic (`٧`) or any other non-ASCII digits is then never read
as a PR: not as a ruling, a verdict PR line, a ref in a sent text, or a CLI argument.

The owner review and breaking rulings in `hook._answers` read one match, the module's `REF`
(`owner/repo#n at <sha>`), instead of two patterns. That frees lines; the runtime must not grow.

A test in `tests/test_setup.py` scans `cli/wuwei` for `\d` and for `isdigit()` not preceded by
`.isascii() and `, so a new reader cannot bring the gap back.

Outside: `\w` in repository names (no `re.ASCII`, so repository names read as before); the
wording of any message.

Rollback: revert the commit.

The acceptance scenarios, restated:

1. An AskUserQuestion answer `yes` to `owner review: o/r#７ at abc1234. Approve?` writes no ruling;
   with `o/r#7` the ruling is written with the same fields as on main.
2. A verdict whose PR line is `o/r#７` gets the PR line error from `verdict.parse`.
3. `wuwei evidence o/r#７` exits with the `owner/repo#number` message and makes no gh call.
4. `evidence.refs` returns no ref for a text naming `o/r#７`.
5. The scan in `tests/test_setup.py` finds no `\d` and no unguarded `isdigit()` in `cli/wuwei`,
   and the runtime line count is no higher than before.

## How this fails

1. The merged ruling reader changes which questions record a ruling. The old owner review pattern
   matched `owner review:` anywhere in the question, case-sensitive; the new one reads the class
   prefix. The guard in `guards.pre_tool` checks the shape only of questions that start with a
   class, so a question with text before the class passes the guard and records nothing. Held:
   that fails closed (no ruling, so no merge gap clears), and the existing ruling tests pass.
2. The merged reader takes the wrong REF. A first version (cda89f4, security gate) took the first
   REF anywhere in the question, so "owner review: with acme/lib#3 at 1234567 merged, acme/app#9
   at abcdef0 is ready. Approve?" answered yes approved lib#3 and cleared its owner review gap.
   Held: the REF must follow the class prefix directly (`\s*(?i:owner review|(breaking)):\s*`
   then `REF`), for both classes; the guard refuses an owner review or breaking question whose REF
   does not follow the class, so the owner is never asked a question the recorder would ignore.
   The two-REF cases are in `test_a_ruling_names_a_pr_in_ascii_digits_only` and the guard's
   shape test.
3. A `[0-9]` replacement inside a character class or a quantifier changes a pattern's meaning
   (for example `[^/\d]`). Held: no `\d` sat inside a character class at 0104d00 (guards.py
   already used `[^/0-9]`), checked by grep, and the full suite passes.
4. A later reader adds `\d` or a bare `isdigit()` and reopens the gap. Held: the scan test fails
   on it, naming file and line.

## Clarifications

### Session 2026-10-16

- Q: `[0-9]` or `re.ASCII`? A: `[0-9]`. `re.ASCII` also narrows `\w` and `\s`, which would change
  how repository names read, and the promise puts `\w` outside.
- Q: Does the merged reader keep `kind` off the owner review ruling? A: Yes. On main the owner
  review ruling has no `kind` key and readers rely on that; only breaking adds `kind: breaking`.
- Q: Which `isdigit()` calls change? A: only `__main__._ref`; the two in `guards.py` were already
  guarded by #1102. The scan accepts `x.isascii() and x.isdigit()` and the walrus form
  `(n := ...).isascii() and n.isdigit()`.
- Q: The plan's line numbers (hook 249, 281; evidence 52; verdict 8, 45; guards 344, 349;
  `__main__` 22) were taken at fe5bc0b. A: Re-found at 0104d00 with
  `grep -rn '\\d\|isdigit' cli/wuwei`: evidence 36, 37, 47, 50, 52, 185, 352; guards 341, 346;
  upgrade 16; verdict 7, 44; hook 209, 225, 245, 277; `__main__` 19.

## User Scenarios and Testing

### US1: an owner answer names its PR in ASCII digits (P1)

Given `owner review: o/r#７ at abc1234. Approve?` answered `yes`, no ruling is written. Given
`o/r#7`, the ruling `{pr: o/r#7, head: abc1234, approved: true, question, answer}` is written. The
same holds for `breaking:` with `٧`, which keeps `kind: breaking`.
Test: `tests/test_hook.py::test_a_ruling_names_a_pr_in_ascii_digits_only`.

### US2: a verdict PR line in non-ASCII digits is an error (P1)

Test: `tests/test_verdict.py::test_lint_names_what_is_wrong` with `PR: o/r#７`.

### US3: the CLI refuses a PR argument in non-ASCII digits before any gh call (P1)

Test: `tests/test_evidence.py::test_evidence_names_the_shape_for_a_pr_not_in_ascii_digits_and_calls_no_gh`.

### US4: refs ignores non-ASCII digits (P2)

Test: `tests/test_evidence.py::test_refs_reads_ascii_digits_only`.

### US5: the runtime holds no `\d` and no unguarded `isdigit()` (P1)

Test: `tests/test_setup.py::test_the_runtime_reads_numbers_in_ascii_digits_only`, and
`test_the_runtime_holds_its_size_budget`.

## Requirements

- FR-001: every `\d` under `cli/wuwei` becomes `[0-9]`.
- FR-002: `__main__._ref` checks `number.isascii() and number.isdigit()`.
- FR-003: `hook._answers` reads owner review and breaking rulings from one match: the class
  prefix, then `REF` right after it; the owner review ruling keeps no `kind` key.
- FR-006: `guards.pre_tool` refuses an owner review or breaking question whose `owner/repo#n at
  <sha>` does not follow the class prefix directly.
- FR-004: a scan test holds FR-001 and FR-002 for every runtime module.
- FR-005: the runtime line count is no higher than on main.

## Assumptions

- Reading the class prefix instead of a substring for owner review is safe. A question with text
  before the class is not checked by the guard's shape rule and records nothing, which fails
  closed. Overturned if a seat's charter asks owner review questions with leading text; none does
  (`grep -rn "owner review:" charters`).
- The class prefix is read case-insensitively after leading whitespace, as the guard reads it.
  Main read `owner review:` case-sensitively; `  Owner Review:` and `BREAKING:` now record, pinned
  in the hook test. Overturned if the owner wants only the lower-case form.

## Breaking

None. The CLI, verdict and ledger shapes are unchanged; only non-ASCII digits stop reading as
numbers.
