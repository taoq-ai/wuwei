# Implementation plan: pr-draft-text

**Spec**: `specs/pr-draft-text/spec.md`
**Item**: pr-draft-text, tier full, goal G-2

## Technical context

- `guards.bash` returns `charters/_pr.md` as a note once per session when it reads a PR create
  (`cli/wuwei/guards.py:252-256`, `PR_STANDARD` at line 62), with `<version>` filled in.
- No generated agent includes `_pr.md`; `setup.vendor('.')` copies `charters/` into
  `.claude/wuwei/charters/`, and `tests/test_setup.py` holds the copy to the tree.
- `tests/test_charters.py` holds every charter to 35 words per sentence and a 20-word average.
- Runtime budget 3,000 lines; the change adds none (2,976).

## Design

1. Replace the closing paragraph of `_pr.md` with three sentences on the draft route and keep the
   delta sentence.
2. One guard test reads the note through `guards.bash` for `gh pr create --draft` and holds the
   three sentences whole, refuses the old reviewer instruction and the old "before it opened", and
   checks the once-per-session rule.
3. Re-vendor with `setup.vendor('.')`; run `bin/wuwei agents build` to confirm no agent moves.

## Verification

- Red first: the new test against the old charter.
- Mutants in a scratch copy of the head (`git archive`): negate the draft sentence, drop the
  shepherd clause, restore "Request a reviewer", leave the vendored copy stale. Each must fail.
- Full suite with `pytest -q -W error`.

## Constitution check

Stdlib only, no new door, no config key, test first, runtime unchanged, no emoji, no em dash.
