---
name: wuwei
description: How work runs under WUWEI, the process auditor. Use when unsure what done means, why a call was refused, whether to ask the owner, or how to pull the andon cord.
---

# Working under WUWEI

WUWEI reads what you produce and says what is missing; it never prescribes the command. Use git,
gh and the repository's tools directly. `wuwei status` shows every open item's gaps;
`wuwei evidence owner/repo#n` shows one PR's.

## Done means evidence

Only safety gaps (tests, gates, CI, review threads, owner review) hold a merge or show on the board.
The rest is process fit: follow it, and the merge records any misfit for the retro.

- The body names its item (`WUWEI-Item: <id>`) and keeps the repository's PR template sections.
- A test is in the diff, or a `No test: <reason>` line explains why none can hold the change.
- The diff stays under about 400 changed lines (generated files aside), or a `Size: <reason>` line
  says why it cannot be split.
- At `full` or on `owner_paths`, a `Rollback: <how to undo>` line.
- At `standard` and `full`, when the repository has a spec engine, its steps are done by their artifacts
  at the head: spec-kit `spec.md`, `plan.md`, `tasks.md` all checked (full adds `## Clarifications`, an
  `analysis.md` with no open CRITICAL or HIGH, checked checklists); OpenSpec `proposal.md`, a capability
  spec, `tasks.md` all checked.
- The gates the tier needs passed at an ancestor of the head, one of them at the head: light
  quality; standard arch, quality, security; full adds goal. When a repository's 28-day change
  failure rate is over 15 percent, every tier there rises one step until it recovers.
- A breaking change to an outward contract (declared with `!` or `BREAKING CHANGE:`, or found by the
  arch gate) has an `Announcement: <link>` line and the owner's `breaking:` confirmation at the head.
- CI is green, every review thread is answered, a reviewer is requested, the owner reviewed changes
  under `owner_paths`, and the PR is not stale (three days or more open).

## The doors

WUWEI refuses: a merge with gaps; a force push, a push to or deletion of the default branch; admin
merges, protection, status and access writes through `gh api`; a secret or the workspace canary in
an outward call; writes to `.wuwei/ledger.jsonl`; a hand-made `wuwei hook` call; and a question to
the owner that the process answers. Infrastructure commands ask the owner through the harness.
Everything else passes and is recorded.

## Deciding

| | Sure | Unsure |
|---|---|---|
| Undone cheaply | act | act, record the assumption |
| Hard to undo | act, with `Rollback:` | ask the owner |

Ask with the class first (`one-way:`, `scope:`, `goal:`, `trust:`, `infra:`,
`owner review: owner/repo#n at <sha7>`, `exception: owner/repo#n at <sha7>: <gap>`, `plan:`, `breaking: owner/repo#n at <sha7>: <what breaks>. Announced at <link>. Proceed?`) and your
recommendation. Never ask whether to continue planned work.

## Andon

A problem that breaks work for everyone in a repository: `wuwei andon owner/repo --reason "..."`.
New builds there wait; clear it with `wuwei andon owner/repo --clear` once fixed.
