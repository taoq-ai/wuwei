# Implementation Plan: Codex plugin spike

**Branch**: `261-codex-plugin-spike` | **Date**: 2026-09-30 | **Spec**: [spec.md](spec.md)

## Summary

A documentation spike. The deliverable is `docs/specs/2026-09-30-codex-plugin-spike.md`
(already written in this change): sources with dates, the Codex hook contract, a gap table,
the planner route without the Agent tool, a recommendation (partial port: guards yes,
planner not now) and four sized follow-up issues. The builder verifies it against the
acceptance and runs the suite; no runtime code changes.

## Technical Context

- Language: Markdown only. Python 3.11+ stdlib runtime and pytest are untouched.
- Evidence base: Codex documentation fetched 2026-09-30 (`learn.chatgpt.com/docs/*`, the
  redirect target of `developers.openai.com/codex/*`), codex-cli 0.156.1 help output, and
  four openai/codex GitHub issues. The research content lives in the spike document
  itself; no separate `research.md`.
- Constraints: under 1500 words; no em-dashes, no emojis, no absolute local paths
  (`tests/test_hygiene.py` enforces the last one on tracked files).

## Constitution Check

- I (stdlib), II (exits), III (one behaviour, one function), IV (test first): no code
  changes, so nothing to test first. The acceptance checks in `tasks.md` run before the
  document is accepted and fail on a missing citation, marker or scope breach.
- V (ponytail): one document, no new test, no helper, no template.
- VII (security): the document states what enforcement loses where hooks do not run, and
  what holds per spec 9.1.

## Code read to ground the document (read only)

| File | What the document relies on |
|---|---|
| `hooks/hooks.json` | The six hook events and the `command` plus `args` entry form |
| `cli/wuwei/commands/hook.py` | `validate()` line 96 requires non-empty `transcript_path`; `refuse()` line 103 prints exit 2 plus `permissionDecision: "deny"` |
| `cli/wuwei/guards/__init__.py` | `MODULES`: tool names each guard keys on (Bash, Write, Edit, MultiEdit, NotebookEdit, Agent, AskUserQuestion) |
| `cli/wuwei/guards/protect_state.py`, `decision.py`, `verdict.py` | File guards read `tool_input.file_path` or `notebook_path` |
| `cli/wuwei/guards/agent_launch.py` | Launch guard reads `subagent_type`, `prompt`, `resume`; SubagentStop calls `build.stopped()` at line 229 |
| `cli/wuwei/guards/outward.py` | `mcp__` prefix for MCP chat and tracker tools |
| `cli/wuwei/guards/deploy.py` | `PERMISSIONS_DENY` written by `wuwei init` |
| `cli/wuwei/commands/init.py` | `.claude/settings.json` deny rules and the printed statusLine |
| `cli/wuwei/commands/build.py` | `run_loop` polling form for Codex; `stopped()` is the only fast-check reuse point |
| `adapters/runtime/codex.py` | Companion `task`, `status`, `result`, `cancel`; `--resume-last` at line 154 |
| `skills/wuwei-plan/SKILL.md` | `${CLAUDE_SESSION_ID}` at line 10; Agent-based launch and continue |

## Files

- Added: `docs/specs/2026-09-30-codex-plugin-spike.md` (done).
- Added: `specs/261-codex-plugin-spike/` (`spec.md`, `plan.md`, `tasks.md`,
  `checklists/requirements.md`).

## Must not change

Everything else: `cli/`, `adapters/`, `hooks/`, `skills/`, `agents/`, `charters/`,
`templates/`, `tests/`, `docs/site/`, `README.md`, `.claude-plugin/`, the design spec and
the constitution. Findings about code (for example the `transcript_path` validation) go to
the follow-up issues in the document, not into this change.

## Builder's job

Run the checks in `tasks.md`. If a check fails, fix the spike document only (a missing
source cell, a lost unverified marker, an em-dash, the word budget). Do not re-research
unless a cited URL no longer supports its row; then mark the row unverified rather than
guess.
