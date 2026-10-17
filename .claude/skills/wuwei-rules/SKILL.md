---
name: wuwei-rules
description: How work runs under WUWEI, the process auditor. Use when unsure what done means, why a call was refused, whether to ask the owner, or how to pull the andon cord. Not for running the day (/wuwei-run), a watch pass (/wuwei-watch) or the close (/wuwei-close); those skills act, this one explains.
---

# Working under WUWEI

WUWEI reads what you produce and says what is missing; it never prescribes the command. Use git,
gh and the repository's tools directly. `wuwei status` shows every open item's gaps;
`wuwei evidence owner/repo#n` shows one PR's.

## Done and deciding

The plugin's `charters/_common.md` (`.claude/wuwei/charters/_common.md` when vendored) states once
what done means (Done) and how to decide and when to ask the owner (Decisions). Read it there;
this skill gives only the short form. Only safety gaps hold a merge (a test, the gates the diff
needs at the head, green CI, threads answered, owner review on `owner_paths`, a breaking change
confirmed, the spec at `full`). The rest is process fit: follow it, and the merge records any
misfit for the retro. Ask the owner only for a hard-to-undo choice you are unsure of, a change of
scope or goals, a trust question, an owner review or an exception, with the class first and your
recommendation. Never ask whether to continue planned work.

## The PR body

The body keeps the repository's PR template sections and ends with the WUWEI footer, filled from
`wuwei --version` and `wuwei plan show <id>`:
`` <sub>[WUWEI <version>](https://taoq-ai.github.io/wuwei/) · Item `<id>` · <title> · Goal <G-n> · Tier <tier></sub> ``.
It holds a test or a `No test: <reason>` line, a `Size: <reason>` line over about 400 changed
lines, and a `Rollback: <how to undo>` line at `full` or on `owner_paths`. At `standard` and
`full`, when the repository has a spec engine, its artifacts are at the head. For spec-kit that is
`spec.md`, `plan.md` and `tasks.md` all checked; `full` adds `## Clarifications`, an `analysis.md`
with no open CRITICAL or HIGH, and checked checklists. For OpenSpec it is `proposal.md`, a
capability spec and `tasks.md` all checked.

## The doors

WUWEI refuses: a merge with safety gaps; a PR opened ready, marked ready or given reviewers before
its gates pass (a draft opens first); a force push, a push to or deletion of the default branch;
admin merges, protection, status and access writes through `gh api`; a secret or the workspace
canary in an outward call; writes to the ledger (`.wuwei/ledger/`); a hand-made `wuwei hook` call;
and a question to the owner that the process answers. Infrastructure commands ask the owner through
the harness. Everything else passes and is recorded.

## Andon

A problem that breaks work for everyone in a repository: `wuwei andon owner/repo --reason "..."`.
New builds there wait; clear it with `wuwei andon owner/repo --clear` once fixed.
