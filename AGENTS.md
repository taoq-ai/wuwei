# AGENTS.md

Instructions for coding agents working in this repository.

- What to build: `docs/design.md`. How to build it: `.specify/memory/constitution.md`. Read both first.
- Test first. Write the failing test, run it, see it fail, then implement.
- Runtime code is stdlib-only Python 3.11+ under `cli/wuwei/`, at most 3,000 lines. Run the suite
  with `python3 -m pytest -q` from the repository root.
- Charters in `charters/` are the one source for `agents/`. After changing a charter, run
  `bin/wuwei agents build`; a test fails when they drift.
- Keep it simple: reuse what exists, no speculative abstractions, shortest working diff.
- No emojis and no em dashes in anything you write.
- Every PR body names `WUWEI-Item: <issue number>`.
