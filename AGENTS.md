# AGENTS.md

Instructions for coding agents working in this repository.

- What to build: `docs/design.md`. How to build it: `.specify/memory/constitution.md`. Read both first.
- Test first. Write the failing test, run it, see it fail, then implement.
- Runtime code is stdlib-only Python 3.11+ under `cli/wuwei/`, at most 3,400 lines. Run the suite
  with `python3 -m pytest -q` from the repository root, or `pytest -q` where python3 lacks the
  module.
- Charters in `charters/` are the one source for `agents/`. After changing a charter, run
  `bin/wuwei agents build`; a test fails when they drift.
- Keep it simple: reuse what exists, no speculative abstractions, shortest working diff.
- No emojis and no em dashes in anything you write.
- Every PR body names `WUWEI-Item: <issue number>`.
- Commits are authored by the owner, `Leone <leone.lage@gmail.com>`, never by an agent. Before the first
  commit, check `git config user.name`; if it names an agent (Claude, Codex), set the owner's name and
  email in the repository config. An agent appears only as a `Co-Authored-By:` trailer.

## Testing the guards

Lessons about this repository's own guard code (`cli/wuwei/guards.py`, `cli/wuwei/hook.py`). Seats
read them here and in the standards lines of their brief; the charters stay generic.

- A change to guard code runs the route corpus (`tests/fixtures/routes.json`) on main and on the
  branch, records the corpus sha256, and lists every route whose verdict or reason moves as its own
  row. A refusal that names a different PR or repository is its own row too.
- A change to guard parsing (how a guard reads a command) carries a generated combinatorial probe
  run under real bash with a stub program on PATH: operator or spelling classes x positions x
  targets. The PR and each verdict report how many commands were generated, how many really ran
  the door program (the guarded program the stub stands for), and the holes. A gate round on a
  parser re-runs it and adds a class for each hole it finds.
- When a change to guard parsing makes more commands unreadable or rewrites the guard's parser,
  also probe the checks that do not rely on door words (the program names and paths a guard
  matches to refuse a command), for example the leak check on network programs or the ask rule for
  infrastructure commands, with the new command shape.
- Probe fixtures that hold JSON escapes are written by code (json.dumps or a Python literal),
  never typed into a shell.
- A normalisation round (a fix that adds input normalisation to a guard or parser) probes one input
  per path class (`//`, `%xx`, `/./`, `/../`) and per working-directory wrapper (`cd`, `env -C`,
  `sudo -D`).
- A gate brief for a change to `guards.py` or `hook.py` asks for the main-versus-head differential:
  every route in `tests/fixtures/routes.json` read through the guards at main and at the head,
  naming each route whose verdict moves.
