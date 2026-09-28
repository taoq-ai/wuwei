# Implementation Plan: README and documentation site

**Branch**: `039-readme-docs` | **Date**: 2026-09-28 | **Spec**: `specs/039-readme-docs/spec.md`

## Summary

Replace the scaffold README with a ZIRAN-style introduction and two SVG hero variants. Publish plain Markdown from `docs/site/` through GitHub Pages Actions. Document shipped behavior from the template, CLI, registry and guards, and label design-only features planned. Add documentation checks before writing the pages.

## Technical Context

- Markdown and SVG assets; no runtime dependency.
- Python 3.11+ and pytest for documentation tests.
- Source of configuration defaults: `templates/workspace/config.toml` and `cli/wuwei/workspace.py`.
- Source of current commands: `cli/wuwei/commands/`; no skill directory exists on this baseline.

## Constitution Check

- No runtime code or dependency added.
- Documentation checks are written and run red before content.
- Pages workflow uses the standard GitHub Pages action path.
- Planned commands are clearly identified so readers are not misled.

## Project Structure

- `README.md`, `docs/assets/hero-light.svg`, `docs/assets/hero-dark.svg`
- `docs/site/` Markdown pages and `_config.yml`
- `.github/workflows/docs.yml`
- `tests/test_docs.py`

## Design

Use relative links in the site. The configuration page includes exact dotted paths and values from the template, including commented optional keys and nested repository fields. Use one workflow to build Jekyll from `docs/site/` and deploy on a main push. No JavaScript, site generator dependency in the repository, or new CLI behavior.
