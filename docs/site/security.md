---
layout: default
---

# Security integration

[Home](index.html)

## Current controls

Hooks invoke the CLI for relevant actions. Guard scope is a WUWEI workspace, its configured repositories and worktrees. Outside that scope, guards return 0. Relevance is checked before parsing; malformed input blocks a relevant call with exit 2 and a reason. CLI state and events use dedicated writers, and the outward policy limits text-bearing adapter calls. The `none` scanner reports unmeasured rather than clean.

## ZIRAN integration

The design calls for ZIRAN role audits, runtime trace analysis, MCP registry checks and agent-surface gates through the scanner port. **Planned:** the shipped scanner directory currently contains only `none`; no ZIRAN adapter or automatic init scan is available. Do not treat scanner output as a clean audit while `adapters.scanner = "none"`.

## Threat model 9.1

The guards address agent mistakes, corner cutting and prompt injections sent through normal tools. They are local controls, not a hard trust boundary against a process running as the owner. Such a process can edit local files, including state, events and approval records. Hard boundaries are code host server-side rules, owner-sent approve-tier messages, and, when built, an external control plane. WUWEI must never bypass branch protection, approve its own pull requests or deploy. Codex seats can be isolated in a write sandbox limited to their worktree. More hardening for Claude seats is **planned**.

The design also describes a signed manifest, workspace integrity checks, a prompt canary and a honeytoken. These are **planned**, not current protections. Read the [design spec](https://github.com/taoq-ai/wuwei/blob/main/docs/specs/2026-09-24-wuwei-design.md) for the full intended model.
