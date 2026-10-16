# Implementation Plan: a gate never edits a written verdict, each seat has its own scratch folder, and Codex jobs are not seats

**Branch**: `claude/gate-charters` | **Spec**: `specs/gate-charters/spec.md`

## Summary

Edit three charters and two site pages, rebuild `agents/`, re-vendor `.claude/`.

## Technical Context

Docs only. Charters in `charters/` are the one source for `agents/`; `bin/wuwei agents build`
writes them, and `tests/test_setup.py` fails on drift in `agents/` and in `.claude/`.

## Constitution Check

- I. Stdlib only: no code.
- III. An auditor: no door changes; the charters describe the attestation the hook already does.
- V. Test first: the existing drift tests ran red in a scratch copy before the build.
- VI. Budgets: runtime unchanged.

## Design

- `_gate.md`, The verdict: replace "fix it and hand back again" with the never-edit rule and the
  next free `-2.md` for a taken file or a refused shape, in `_verdict_problem`'s words.
- `_common.md`, Boundaries 2: the scratch folder rule. Evidence 4 points the probe copy into it.
- `planner.md`, Running the work 2: the routes differential for `guards.py` and `hook.py`, the
  attestation rule, the `codex-companion` limit and the probe as the switch.
- `reference.md`, Verdict format: the PR line before a PR, the blocking and note lines from FORMAT,
  and the never-edit rule.
- `codex.md`: a "Gates on Codex" section.
