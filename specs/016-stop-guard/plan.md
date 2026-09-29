# Implementation plan

## Technical context and constitution check

Python 3.11+, stdlib runtime, pytest development tests. No external processes in core.
Use existing workspace scope, obligation evaluator, watch poll and reserved state writer.
No commits, network tools or extension hooks. Current worktree supplies isolation.
Tests precede implementation; all errors carry reasons and return 2. No new dependencies.

## Design

- `cli/wuwei/closing.py`: ordered retro checks plus day-close orchestration.
- `cli/wuwei/guards/stop.py`: planner/session scoping and raw 0/1/2 Stop registration.
- `cli/wuwei/commands/close.py`: persistent close request and standalone retro checks.
- `cli/wuwei/pr_actions.py`: consume recorded actions and verify owner-routed dispositions
  from the code host. Watch does not create placeholder actions or inherit old actions.
- `cli/wuwei/guards/outward.py`: refuse raw disposition markers before native tool bypasses.
- `cli/wuwei/commands/pr.py`: dedicated disposition producer, using existing decision parsing.
- Add vcs `changes_on(repo, day)` and `read_tree(repo, ref, paths)` operations. The latter
  accepts HEAD or a full commit ID. Closed git command allowlist, fake methods,
  contract tests and recorded output tests cover both.
- Expose the provider's merged boolean in code_host.pr; never infer merge from closed.
- Add retro config for repository, charter paths and changelog. Existing capture
  events and files replace the harness notes.jsonl; verify parity without another writer.

## Verification

Start with the source P7 shortfall/parity cases, then retro tables.
Test adapters before core implementation. Add action consumer and Stop integration tables
with owner-comment forgery, corrupted state, empty ownership, retry and configured-repo
scope cases. Mutation test removes Stop registration and confirms the refusal test fails.
Run the full suite using the requested interpreter, then inspect diff and hygiene.

## Tradeoffs and deferred work

Defer action production to #120 and weekly consolidation to its own feature.
Do not duplicate polling or implement notifications, merge policy or report generation.
