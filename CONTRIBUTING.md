# Contributing

Read [AGENTS.md](AGENTS.md) and the [constitution](.specify/memory/constitution.md) before you
start. What to build is in the [design](docs/design.md).

- One GitHub issue is one change. A feature runs the spec-kit steps in `.agents/skills/` and keeps
  its spec under `specs/<issue>-<slug>/`. A bug fix is a failing test and the fix.
- Test first: write the failing test, run it, see it fail, then implement.
- Runtime code is stdlib only, Python 3.11 or newer, at most 3,800 lines. pytest is dev only.
- Charters are the one source for `agents/`: after a charter change run `bin/wuwei agents build`,
  and after a tool grant change rewrite the ZIRAN baseline with
  `ziran audit agents --write-baseline agents/ziran-baseline.json`.
- If you change the hero, run `python3 scripts/build-hero.py` and commit both SVGs; a test checks
  they match the generator.
- Preview the docs with `uvx --with mkdocs-material mkdocs serve`; CI publishes them from `main`.
- No emojis and no em dashes in anything you write.

## Before you open a pull request

- `python3 -m pytest -q` passes from the repository root (`pytest -q` where python3 lacks the
  module).
- The body ends with the WUWEI footer naming the issue as its item (see `charters/_pr.md`);
  WUWEI audits its own changes. The older `WUWEI-Item: <issue number>` line still links.
- Conventional commit messages (`feat:`, `fix:`, `docs:` and so on).
