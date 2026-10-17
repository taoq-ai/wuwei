# Implementation plan: shell-doors

**Spec**: `specs/shell-doors/spec.md`
**Item**: shell-doors, tier full, goal G-2

## Technical context

- Stdlib-only Python 3.11+, runtime under `cli/wuwei/`, budget 3,000 lines. Main 83f1f09 holds
  2,996 after gh-doors (#1108), so this item has 4 lines.
- `guards.segments` reads a command with `shlex` in punctuation mode, which returns a run of
  `();<>|&` as one word, and splits on `CONTROL`. `_unwrap` reads redirects and wrappers.
- `guards.bash` refuses a multi-line or unreadable command whose raw text matches a `DOOR_WORDS`
  entry. `hook.door` reads the same table for the fail-closed path.
- The allowlist spike prototyped (d) splitting punctuation runs at +3 lines and (e) the ledger
  pattern at +0.

## Design

1. `OPS` lists sh's operators, longest first, then each single character of `();<>|&`. A word that
   is all punctuation is replaced by `re.findall(OPS, word)`; every other word is kept.
2. `|&` joins `CONTROL`. `_unwrap`'s redirect tuple holds every operator `OPS` yields that takes a
   word: `>`, `>>`, `>|`, `&>`, `&>>`, `<`, `<>`, `>&`, `<&`, `<<<`. The dead `2>` and `1>` entries go
   (shlex never returns them in punctuation mode).
3. The pre-lexer `re.sub` drops an fd number glued before `<` or `>` when it starts a word, outside
   quotes, so `2>&1 git push` reads `git` as the command.
4. Before the loop, `segments` scans quote spans left to right (`$'`, `$"`, a single-quoted span,
   a double-quoted span, a backslash escape). When a span opens with `$`, `out` starts with
   `UNREAD`, so `bash` applies the door-word refusal and still reads every segment.
5. `LEDGER` becomes `(^|[/=])\.wuwei(/(\.?/)*ledger(\.jsonl)?)?(/\.?)*$|(^|[/=])\.wuwei/(\.?/)*ledger/`.
6. The ledger `DOOR_WORDS` entry becomes `\.wuwei[/.]*(/ledger|(?![\w./-]))`; the multi-line
   refusal names `.wuwei or .wuwei/ledger`.

Line cost: +2 runtime lines (2,996 to 2,998), inside the +4 budget.

## Constitution check

Stdlib only, no new dependency, no config key, no new door (refusals on the existing ones), test
first, under the line budget.

## Test plan

Tests in `tests/test_guards.py` and `tests/test_hook.py`, run red on 83f1f09, then green. Real
execution: each acceptance shape under `bash -c` with a stub `git` on PATH that logs its argv.
The route corpus probe on main and head with the corpus sha256, and every traced Bash command in
`.wuwei/traces.jsonl` read by main's and head's guards offline.
