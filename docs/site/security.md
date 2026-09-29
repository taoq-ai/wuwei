---
layout: default
---

# Security integration

[Home](index.html)

## Current controls

Hooks invoke the CLI for relevant actions. Guard scope is a WUWEI workspace, its configured repositories and worktrees. Outside that scope, guards return 0. Relevance is checked before parsing; malformed input blocks a relevant call with exit 2 and a reason. CLI state and events use dedicated writers, and the outward policy limits text-bearing adapter calls. The `none` scanner reports unmeasured rather than clean.

## ZIRAN integration

The ZIRAN scanner adapter provides runtime trace analysis, MCP registry checks and agent-surface gates. Init and upgrade register attached MCP configurations; morning planning checks for drift before any seat launches. High/critical findings require an owner decision on the host. Incomplete checks block with exit 2. Snapshots and accepted decisions are protected producer records, and raw descriptions stay in report files. See [configuration](configuration.html) for discovery paths and the owner decision flow. Do not treat an unavailable scanner as a clean audit.

## Threat model 9.1

The guards address agent mistakes, corner cutting and prompt injections sent through normal tools. They are local controls, not a hard trust boundary against a process running as the owner. Such a process can edit local files, including state, events and approval records. Hard boundaries are code host server-side rules, owner-sent approve-tier messages, and, when built, an external control plane. WUWEI must never bypass branch protection, approve its own pull requests or deploy. Codex seats can be isolated in a write sandbox limited to their worktree. More hardening for Claude seats is **planned**.

The design also describes a signed manifest, workspace integrity checks, a prompt canary and a honeytoken. These are **planned**, not current protections. Read the [design spec](https://github.com/taoq-ai/wuwei/blob/main/docs/specs/2026-09-24-wuwei-design.md) for the full intended model.
