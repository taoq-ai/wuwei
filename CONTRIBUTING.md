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
- Runtime code is stdlib only, Python 3.11 or newer. pytest and pytest-xdist are dev
  dependencies only.
- Keep it simple: reuse what exists, shortest working diff.
- No emojis and no em-dashes in anything you write.

## Before you open a pull request

- Run the suite from the repository root: `python3 -m pytest -q`. It must pass.
  In parallel: `python3 -m pytest -q -n auto --dist loadgroup` (the timing tests share one
  worker). While you work, `python3 scripts/changed_tests.py` runs only the tests your diff
  against origin/main touches; extra arguments go to pytest.
- If you change the hero, run `python3 scripts/build-hero.py` and commit both SVGs.
- Use conventional commit messages (`feat:`, `fix:`, `docs:` and so on).
- A pull request merges with the suite green and an adversarial review covering
  correctness, security and over-engineering with no open blocking findings.

## Docs site

The site at https://taoq-ai.github.io/wuwei/ is built with MkDocs Material from
`docs/site` and `mkdocs.yml`. Preview it with `uvx --with mkdocs-material mkdocs serve`
and check it with `uvx --with mkdocs-material mkdocs build --strict`: a broken link, a
missing anchor or a page left out of `nav` fails the build. After a merge the `Docs`
workflow publishes the site to the `gh-pages` branch. One-time owner setting: in the
repository settings, under Pages, set the source to "Deploy from a branch" with branch
`gh-pages` and folder `/ (root)`.

## Security

Report vulnerabilities as described in [SECURITY.md](SECURITY.md), never in a public issue.
