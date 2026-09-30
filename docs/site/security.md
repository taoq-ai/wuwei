---
layout: default
---

# Security integration

[Home](index.html)

## Current controls

Hooks invoke the CLI for relevant actions. Guard scope is a WUWEI workspace, its configured repositories and worktrees. Outside that scope, guards return 0. Relevance is checked before parsing; malformed input blocks a relevant call with exit 2 and a reason. CLI state and events use dedicated writers, and the outward policy limits text-bearing adapter calls. The `none` scanner reports unmeasured rather than clean.

## ZIRAN integration

The ZIRAN scanner adapter provides runtime trace analysis, MCP registry checks and agent-surface gates. Init and upgrade register attached MCP configurations; morning planning checks for drift before any seat launches. High/critical findings require an owner decision on the host. Incomplete checks block with exit 2. Snapshots and accepted decisions are protected producer records, and raw descriptions stay in report files. See [configuration](configuration.html) for discovery paths and the owner decision flow. Do not treat an unavailable scanner as a clean audit.

## S1: Reviewed role grants in CI

Pull requests and pushes to main run `taoq-ai/ziran@v0.40.0` in audit mode with
`ziran==0.40.0`, high severity and `agents/ziran-baseline.json`. ZIRAN reads the
Claude Code agents directly. The recorded baseline is the reviewed proposal of
tool grants and dangerous chains; no WUWEI converter or runtime dependency is
needed. Existing grants pass, while widened tools/chains and new critical
findings fail. For example, adding WebFetch to the builder fails with a finding
naming the chain it creates. Both findings (exit 1) and an audit that could not
run (exit 2) fail CI. The action uploads SARIF to code scanning when
permissions allow; an upload failure does not change the audit result.

After a reviewed charter or allowlist change, use ZIRAN 0.40.0 in a disposable
dev environment. From the plugin repository root, outside an initialized WUWEI
workspace, run:

```sh
bin/wuwei agents build
ziran audit agents/ --write-baseline agents/ziran-baseline.json
ziran audit agents/ --baseline agents/ziran-baseline.json --format json
```

Review and commit the generated agents and baseline together with their source
changes. Do not re-record an unreviewed widening just to make CI green. Default
pytest checks baseline/allowlist consistency offline; real clean and widened
audits run when ZIRAN is on PATH, including in the audit job. See the
[agent maintenance instructions](https://github.com/taoq-ai/wuwei/blob/main/agents/README.md)
for installation and regeneration details.

## Threat model 9.1

The guards address agent mistakes, corner cutting and prompt injections sent through normal tools. They are cooperative mistake prevention, not an isolation boundary: no hook, Claude Code or git, is a hard boundary against a process running as the owner. Such a process can edit local files, including state, events and approval records. Hard boundaries are code host server-side rules (protected refs, required checks, required reviews), publication credentials kept out of seat environments, owner-sent approve-tier messages, and, when built, an external control plane. For push, merge, deploy and PR approval the guards refuse what they recognise; push and merge are guaranteed by the host rules (protected refs, and a merge lands only through required checks and reviews), and approval and deploy by the credential layout. WUWEI must never bypass branch protection, approve its own pull requests or deploy. Codex seats can be isolated in a write sandbox limited to their worktree. More hardening for Claude seats is **planned**.

The design also describes a signed manifest, workspace integrity checks, a prompt canary and a honeytoken. These are **planned**, not current protections. Read the [design spec](https://github.com/taoq-ai/wuwei/blob/main/docs/specs/2026-09-24-wuwei-design.md) for the full intended model.
