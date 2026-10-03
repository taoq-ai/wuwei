# Implementation Plan: The docs site uses the same MkDocs Material layout and design as ZIRAN

**Branch**: `392-mkdocs-site` | **Spec**: [spec.md](spec.md) | **Issue**: #392

## Summary

Swap Jekyll for MkDocs Material with ZIRAN's config shape. The site stays at `docs/site`
(`docs_dir`), so the release asset (#245), the integrity manifest, `bin/wuwei next`,
`doctor` doc links and every README link keep their paths. Two files move under
`docs/site` because MkDocs serves only `docs_dir`: the integrity page and the hero SVGs.
Pages lose their front matter and breadcrumb and link `.md`. The tests move from pinning
Jekyll to pinning MkDocs: nav coverage both ways, no `.html`, links resolve, no front
matter. No runtime code changes.

## Technical Context

- Build tool: MkDocs 1.6.1 with mkdocs-material, run only through `uvx` (CI and local).
  Never imported, never in `pyproject.toml`.
- Tests: stdlib plus pytest, `tests/test_docs.py` reads `mkdocs.yml` as text with a regex
  (it has `!!python/name` tags, so no YAML parser, and the suite stays stdlib).
- Prototype (scratch copy outside the repository, spec "Current state"): the config below
  plus the page rewrite builds `--strict` with zero warnings; the `validation` block is what
  makes an orphan page, a bad anchor and a `.html` link fail.
- Interpreter for tests: the one the task names; on this machine plain `python3` has no
  pytest. The WUWEI hooks may refuse compound shell lines: put the `uvx` build in a script
  file and run it with `bash <file>`.

## Constitution Check

- I. Stdlib only: no change under `cli/` or `adapters/`; MkDocs is a CI and local tool. Pass.
- III/IV. One behaviour, one test, test first: each change below has its test change
  first in `tasks.md`. Pass.
- V. Ponytail: one config file copied from ZIRAN, two moves instead of copies, the page
  rewrite is a one-off script outside the repository, no new helper in the suite beyond
  three regexes inline. Pass.
- VII. Security: the workflow gets `contents: write` only (ZIRAN's shape), drops
  `pages: write` and `id-token: write`. Nothing deploys code; `gh-deploy` publishes static
  docs, as the Jekyll workflow did. Pass.

## Changes

### 1. `tests/test_docs.py`, written first

Replace `test_site_pages_and_links` (lines 160-171) with three tests, and update the
existing Jekyll-shaped assertions.

```python
def test_site_pages_are_plain_markdown():
    for path in SITE.rglob('*.md'):
        text = path.read_text()
        assert not text.startswith('---') and '[Home](index' not in text, path.name
        for target in re.findall(r'\]\(([^)\s]+)\)', text):
            if ':' in target or target.startswith('#'):
                continue
            file = target.split('#', 1)[0]
            assert not file.endswith('.html') and (path.parent / file).is_file(), (path.name, target)
    assert '9.1' in (SITE / 'security.md').read_text()
    assert (ROOT / 'skills/wuwei-plan/SKILL.md').is_file()


def test_mkdocs_nav_covers_every_page():
    config = (ROOT / 'mkdocs.yml').read_text()
    for phrase in ('site_name: WUWEI', 'site_url: https://taoq-ai.github.io/wuwei/',
                   'repo_url: https://github.com/taoq-ai/wuwei', 'docs_dir: docs/site',
                   'name: material', 'scheme: slate', 'scheme: default', 'primary: indigo',
                   'accent: cyan', 'navigation.tabs', 'content.code.copy', 'permalink: true',
                   'omitted_files: warn', 'anchors: warn', 'unrecognized_links: warn'):
        assert phrase in config, phrase
    nav = set(re.findall(r'^\s*- (?:[^:\n]+: )?([\w./-]+\.md)\s*$', config, re.M))
    pages = {path.relative_to(SITE).as_posix() for path in SITE.rglob('*.md')}
    assert nav == pages, (sorted(pages - nav), sorted(nav - pages))
    index = (SITE / 'index.md').read_text()
    for page in sorted(pages - {'index.md'}):
        assert f'({page})' in index, page


def test_docs_workflow_deploys_mkdocs():
    workflow = (ROOT / '.github/workflows/docs.yml').read_text()
    for phrase in ('docs/site/**', 'mkdocs.yml', 'contents: write', 'astral-sh/setup-uv',
                   'uvx --with mkdocs-material mkdocs gh-deploy --force --strict'):
        assert phrase in workflow, phrase
    assert 'jekyll' not in workflow and 'pages: write' not in workflow
    assert not (SITE / '_config.yml').exists()
    ignore = (ROOT / '.gitignore').read_text().split()
    assert '/site/' in ignore and 'site/' not in ignore  # unanchored would also ignore docs/site
```

Existing assertions to update (only the path or extension changes, what they check stays):

| Line | Today | After |
|---|---|---|
| 96-97 | `'docs/assets/hero-light.svg'`, `'docs/assets/hero-dark.svg'` in README | `'docs/site/assets/hero-light.svg'`, `'docs/site/assets/hero-dark.svg'` |
| 102 | `ROOT / f'docs/assets/hero-{variant}.svg'` | `SITE / f'assets/hero-{variant}.svg'` |
| after 106 | (new, same test) | `index = (SITE / 'index.md').read_text()` then, for each variant, `assert f'<img src="assets/hero-{variant}.svg#only-{variant}"' in index` |
| 154 | `ROOT / f'docs/assets/hero-{v}.svg'` | `SITE / f'assets/hero-{v}.svg'` |
| 243 | `ROOT / 'docs/integrity.md'` | `SITE / 'integrity.md'` |
| 281 | `ROOT / f'docs/assets/hero-{name}.svg'` | `SITE / f'assets/hero-{name}.svg'` |
| 445 | `'(remote.html)'` | `'(remote.md)'` |
| 543 | `[*SITE.glob('*.md'), *(ROOT / 'docs/assets').glob('*.svg')]` | `[*SITE.glob('*.md'), *(SITE / 'assets').glob('*.svg')]` |
| 642 | `ROOT / 'docs/integrity.md'` | `SITE / 'integrity.md'` |
| 645-646 | `'(rehearsal.html)'`, `'(recovery.html)'` | `'(rehearsal.md)'`, `'(recovery.md)'` |
| 664 | `ROOT / f'docs/assets/hero-{variant}.svg'` | `SITE / f'assets/hero-{variant}.svg'` |
| 736-737 | CONTRIBUTING phrases | add `'uvx --with mkdocs-material mkdocs serve'` and `'gh-pages'` |
| 828 | `page.startswith('---\nlayout: default\n---\n') and len(...) <= 100` | `len(page.splitlines()) <= 100` (front matter is covered by `test_site_pages_are_plain_markdown`) |
| 835 | `'(agent.html)'` | `'(agent.md)'` |

Leave line 72 (`concepts\.(?:html|md)#`) as is: it already accepts `.md`, and the new test
forbids `.html`.

`tests/test_headless_e2e.py` needs no edit: `test_scratch_build_and_observer_preserve_hook_results`
calls `prepare()`, which copies `docs/integrity.md`; after the move it fails with
`FileNotFoundError` until `scripts/headless_e2e.py` follows (section 4).

### 2. `mkdocs.yml` (new, repository root)

ZIRAN's file with WUWEI values, `docs_dir`, the `validation` block and the nav. The
`description` comes from today's `docs/site/_config.yml` subtitle.

```yaml
site_name: WUWEI
site_url: https://taoq-ai.github.io/wuwei/
site_description: Autonomous delivery where the safe path is the default one.
site_author: TaoQ AI

repo_name: taoq-ai/wuwei
repo_url: https://github.com/taoq-ai/wuwei

docs_dir: docs/site

validation:
  omitted_files: warn
  unrecognized_links: warn
  anchors: warn

theme:
  name: material
  palette:
    - scheme: slate
      primary: indigo
      accent: cyan
      toggle:
        icon: material/brightness-4
        name: Switch to light mode
    - scheme: default
      primary: indigo
      accent: cyan
      toggle:
        icon: material/brightness-7
        name: Switch to dark mode
  features:
    - navigation.tabs
    - navigation.sections
    - navigation.expand
    - search.highlight
    - content.code.copy

markdown_extensions:
  - admonition
  - pymdownx.details
  - pymdownx.highlight
  - pymdownx.superfences:
      custom_fences:
        - name: mermaid
          class: mermaid
          format: !!python/name:pymdownx.superfences.fence_code_format
  - pymdownx.tabbed:
      alternate_style: true
  - pymdownx.emoji:
      emoji_index: !!python/name:material.extensions.emoji.twemoji
      emoji_generator: !!python/name:material.extensions.emoji.to_svg
  - tables
  - attr_list
  - md_in_html
  - toc:
      permalink: true

nav:
  - Home: index.md
  - Getting started:
    - Daily path: daily.md
    - What the session knows: agent.md
  - Concepts:
    - Concepts: concepts.md
    - Security: security.md
  - Reference:
    - Operator reference: reference.md
    - Configuration: configuration.md
    - Adapters and ports: adapters.md
    - Charter overrides: charter-overrides.md
  - Operations:
    - Recovery: recovery.md
    - Remote operation: remote.md
    - Release rehearsal: rehearsal.md
    - Integrity: integrity.md
```

### 3. Pages under `docs/site`

Rewrite all 12 existing pages with a one-off script kept outside the repository (scratch
directory, not committed). For each `docs/site/*.md`:

```python
text = re.sub(r'\A---\nlayout: default\n---\n\n', '', text)
text = re.sub(r'^\[Home\]\(index\.html\)\n\n', '', text, flags=re.M)
text = re.sub(r'\]\(([\w-]+)\.html(#[^)]*)?\)', r'](\1.md\2)', text)
```

Then by hand:

- `docs/site/security.md:81`: replace the link target
  `https://github.com/taoq-ai/wuwei/blob/main/docs/integrity.md` with `integrity.md`.
  The design spec link stays a GitHub URL.
- `docs/site/index.md`:
  - after the first paragraph (`WUWEI 无为 means ...`, which `test_readme_lead_and_limits`
    pins as the intro) and before the link list, insert the hero as two raw HTML lines,
    each with the README alt text verbatim (`README.md:5`) and `width="100%"`:

    ```html
    <img src="assets/hero-light.svg#only-light" alt="WUWEI day loop. ...same text as README.md:5..." width="100%">
    <img src="assets/hero-dark.svg#only-dark" alt="WUWEI day loop. ...same text as README.md:5..." width="100%">
    ```

    Raw HTML, not `![alt](...)`: `_prose` in the glossary first-use test blanks HTML tags
    but not Markdown alt text, and the alt names `gate`, `tier` and `shepherd`.
    `#only-light` and `#only-dark` are Material's built-in rules that follow the palette
    toggle.
  - add one list item after `- [Security integration](security.md): ...`:
    `- [Integrity](integrity.md): the signed release, its manifest and host reconfirmation`
    (no glossary term in it, so the first-use test is unaffected).
- Keep every heading. Anchors are unchanged: the prototype resolved all of them under the
  MkDocs `toc` slugs.

Moves (plain `mv`, leave the working tree unstaged):

- `docs/integrity.md` to `docs/site/integrity.md` (content unchanged; it has no front
  matter and no relative links).
- `docs/assets/hero-light.svg` and `docs/assets/hero-dark.svg` to `docs/site/assets/`;
  `docs/assets/` is then empty and goes.

Delete `docs/site/_config.yml`.

### 4. References that follow the moves

- `README.md:3-5`: `docs/assets/hero-dark.svg` and `docs/assets/hero-light.svg` (three
  occurrences) become `docs/site/assets/...`. `README.md:92`: `docs/integrity.md` becomes
  `docs/site/integrity.md`. No other README link changes.
- `scripts/build-hero.py:1` docstring and `:339` output path: `docs/assets/` becomes
  `docs/site/assets/`. Run `python3 scripts/build-hero.py` afterwards and confirm the
  moved files are byte-identical (`test_hero_files_match_their_generator`).
- `scripts/headless_e2e.py:148`: `'docs/integrity.md'` becomes `'docs/site/integrity.md'`,
  and `target.parent.mkdir(exist_ok=True)` on line 150 becomes
  `target.parent.mkdir(parents=True, exist_ok=True)` (the copy now needs `docs/site/`).

### 5. `.github/workflows/docs.yml` (replaced)

```yaml
name: Docs
on:
  push:
    branches: [main]
    paths:
      - "docs/site/**"
      - "mkdocs.yml"
      - ".github/workflows/docs.yml"
  workflow_dispatch:

permissions:
  contents: write

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7

      - uses: astral-sh/setup-uv@v7
        with:
          version: "latest"

      - name: Set up Python
        run: uv python install 3.12

      - name: Deploy to GitHub Pages
        run: uvx --with mkdocs-material mkdocs gh-deploy --force --strict
```

`--strict` is the one addition to ZIRAN's step: a broken link fails the deploy and the
live site keeps its last version.

### 6. `.gitignore`

Add one line `/site/` (MkDocs output of a local build or serve). It must be anchored to
the root: an unanchored `site/` also matches `docs/site/` and makes git ignore the new
`docs/site/integrity.md` and `docs/site/assets/` (corrected during the build).

### 7. `CONTRIBUTING.md`

Add a section after "Before you open a pull request". It must pass
`calibrate.instruction_like` (`test_contributing_points_at_the_rules`): do not put the word
"push" within 30 characters of "main", and no "skip/disable ... checks".

```markdown
## Docs site

The site at https://taoq-ai.github.io/wuwei/ is built with MkDocs Material from
`docs/site` and `mkdocs.yml`. Preview it with `uvx --with mkdocs-material mkdocs serve`
and check it with `uvx --with mkdocs-material mkdocs build --strict`: a broken link, a
missing anchor or a page left out of `nav` fails the build. After a merge the `Docs`
workflow publishes the site to the `gh-pages` branch. One-time owner setting: in the
repository settings, under Pages, set the source to "Deploy from a branch" with branch
`gh-pages` and folder `/ (root)`.
```

### 8. Verification

- `python -m pytest -q` from the repository root: everything passes.
- From the repository root, through a script file:
  `uvx --with mkdocs-material mkdocs build --strict` exits 0 with no `WARNING` line; then
  remove the generated `site/` (ignored, but keep the tree clean).

## PR body note (for whoever opens the PR)

The Pages source must switch from GitHub Actions to the `gh-pages` branch once, after the
first `Docs` run has created that branch: Settings, Pages, Build and deployment, Source
"Deploy from a branch", `gh-pages`, `/ (root)`. With an owner token the API form is
`gh api -X PUT repos/taoq-ai/wuwei/pages -f build_type=legacy -f "source[branch]=gh-pages" -f "source[path]=/"`.
Until the switch, the last Jekyll deployment keeps serving.

## What must not change

- `scripts/build-release.py` (it already ships all of `docs`), `cli/wuwei/integrity.py`
  and the manifest format.
- The `docs/site` path and every page filename: `cli/wuwei/commands/doctor.py:20-26,257,355`,
  `cli/wuwei/commands/next.py:137-138`, `cli/wuwei/heartbeat.py:11`, SECURITY.md and the
  README all point at them.
- Every heading and anchor in the pages; the heading-pinned coverage tests
  (`test_reference_lists_every_cli_command`, `test_configuration_names_every_config_section`,
  `test_remote_runbook_matches_the_code` and the rest) pass without edits.
- `docs/headless-e2e.md` and `docs/specs/` stay where they are and out of the nav.
- `pyproject.toml`, `cli/`, `adapters/`, hooks, skills and charters.
- The hero drawing: the SVG bytes move, they do not change.

## Deferred

- A pull-request check that runs the strict MkDocs build: the docs tests cover nav, links
  and front matter on every PR without network; anchors are checked by the strict build
  locally and on deploy. Add a PR job if anchor breaks slip through.
- Pinning mkdocs-material (ZIRAN does not pin either).
