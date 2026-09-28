# AGENTS.md

Instructions for coding agents (Codex, Claude) working in this repository.

- What to build: `docs/specs/2026-09-24-wuwei-design.md`. How to build it:
  `.specify/memory/constitution.md`. Read both before starting.
- Work follows spec-kit: `speckit-specify`, then `speckit-plan`, then `speckit-tasks`, then
  `speckit-implement` (skills in `.agents/skills/`). One GitHub issue is one feature,
  created with `.specify/scripts/bash/create-new-feature.sh --json --number <issue>
  --short-name <slug> "<description>"`. Do not ask clarifying questions; record assumptions
  in the spec under Assumptions and move on.
- Test first. Write the failing test, run it, see it fail, then implement.
- Runtime code is stdlib-only Python 3.11+. pytest is dev-only. Run tests with
  `python -m pytest -q` from the repository root using the interpreter your task names.
- Keep it simple: reuse what exists, no speculative abstractions, shortest working diff.
- No emojis and no em-dashes in anything you write.
- Do not run `git commit`, `git push` or any `gh` command. Leave changes in the working tree.
