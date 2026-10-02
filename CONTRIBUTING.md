# Contributing

The rules live in two files; read both before you start:

- [AGENTS.md](AGENTS.md): how work is done in this repository, for people and coding agents.
- [.specify/memory/constitution.md](.specify/memory/constitution.md): the principles every
  change is held to.

What to build is in the [design spec](docs/specs/2026-09-24-wuwei-design.md).

## Workflow

- One GitHub issue is one spec-kit feature: `specify`, then `plan`, then `tasks`, then
  `implement`. The skills are in `.agents/skills/`.
- Test first: write the failing test, run it, see it fail, then implement.
- Runtime code is stdlib only, Python 3.11 or newer. pytest is a dev dependency only.
- Keep it simple: reuse what exists, shortest working diff.
- No emojis and no em-dashes in anything you write.

## Before you open a pull request

- Run the suite from the repository root: `python3 -m pytest -q`. It must pass.
- If you change the hero, run `python3 scripts/build-hero.py` and commit both SVGs.
- Use conventional commit messages (`feat:`, `fix:`, `docs:` and so on).
- A pull request merges with the suite green and an adversarial review covering
  correctness, security and over-engineering with no open blocking findings.

## Security

Report vulnerabilities as described in [SECURITY.md](SECURITY.md), never in a public issue.
