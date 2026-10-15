---
name: wuwei
description: How work runs under WUWEI, the process auditor: evidence over steps, the few doors it holds, and when the owner is asked. Use when unsure what done means, why a call was refused, or whether to ask the owner.
---

# Working under WUWEI

WUWEI reads what you produce and says what is missing; it never prescribes the command. Use git,
gh and the repository's tools directly.

## Done means evidence

For a PR, `wuwei evidence owner/repo#n` lists the gaps; `wuwei status` lists them for every open item.

- The body names its item: `WUWEI-Item: <id>`.
- A test is in the diff, or a `No test: <reason>` line explains why none can hold the change.
- At `standard` and `full`, the spec engine's artifacts are in the diff when the repository has one.
- The gates the tier needs passed at an ancestor of the head, and one passed at the head itself:
  light quality; standard arch, quality, security; full adds goal. A verdict counts only when
  WUWEI recorded it at the reviewer's stop.
- CI is green, every review thread is answered, a reviewer is requested.
- A change under `owner_paths` has the owner's review.

## The doors

WUWEI refuses: a merge with gaps; a force push, a push to or deletion of the default branch; admin
merges, protection, status and access writes through `gh api`; a secret or the workspace canary in
an outward call; writes to `.wuwei/ledger.jsonl`; a forged `wuwei hook` call; and a question to the
owner that the process answers. Infrastructure commands ask the owner through the harness.
Everything else passes and is recorded.

## Asking the owner

Start the question with its class: `one-way:`, `scope:`, `goal:`, `trust:`, `infra:` or
`owner review: owner/repo#n at <sha7>`. Give your recommendation. Anything else is yours to decide:
record it under Assumptions and go on. Never ask whether to continue planned work.
