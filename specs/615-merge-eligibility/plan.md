# Implementation Plan: merge eligibility after a real day

**Branch**: `615-merge-eligibility` | **Date**: 2026-10-09 | **Spec**: [spec.md](spec.md)

## Summary

Three small changes on existing code: `plan add` records risk flags and can backfill them
(one lookup in `merge.py`), a per-repository `deploys` row in the interview table whose first
choice follows calibration's deploy facts, and one glob list in `MERGE_SCHEMA` that the size
rule in `merge.check` reads.

## Technical Context

Python 3.11+ stdlib only (constitution I). pytest dev-only. No new module, no new event kind,
no new port operation. One new config key, `repos.merge.size_exclude`; one new interview row,
`deploys`.

## Constitution Check

- I stdlib: no new import beyond the modules already used.
- II exits: missing evidence stays exit 2 with the one command that now works; an unmeasured
  repository recommends the fail-closed choice; completeness checks keep the unfiltered sums.
- III one behaviour one function: `merge.risk_evidence` (read by merge and plan add),
  `calibrate.deploys` (read by profile and the interview), `merge.matched` (never-auto and
  size_exclude).
- IV test first: each change starts with a failing test.
- V simplicity: the replan reuses `plan.added`; the recommendation reuses the `first` ordering
  setup already uses for the spec engine.
- VII security: item flags stay producer-owned; the owner's answer is the only writer of
  `merge_deploys = false`; excluded files still meet never-auto paths.

## Design

### cli/wuwei/merge.py

- `risk_evidence(root, name)`: the flags dicts of `plan.approved`, `state.import` and
  `plan.added` rows whose `payload['flags']` names the item, across `watch.days(root)`.
- `item_evidence` uses it; the missing reason reads `approved item risk evidence is missing;
  run bin/wuwei plan add <name> so its risk is recorded`.
- `check`: the size rule moves after the path loop and sums only the files where some path
  (`path`, `previous_path` when set) has `matched(path, policy['size_exclude']) is None`. The
  completeness checks keep the unfiltered sums.

### cli/wuwei/plan.py

- `add`: after the gate check, an item already in `day['items']` is refused when
  `risk_evidence` finds evidence, else `state.append_event('plan.added', {'item', 'source':
  'replan', 'flags': {item: day['items'][item]['flags']}})` and `{'action': 'risk recorded'}`.
- The admission `plan.added` payload gains `flags: {item: candidate['flags']}`.

### cli/wuwei/calibrate.py

- `deploys(facts)`: `bool(deploy_workflows or deploy_deny or never_auto)`; `profile` uses it.

### cli/wuwei/interview.py

- Row `deploys` (scope repo, header `Deploys`) before `merge`: `Merges deploy` sets
  `repos.merge_deploys = true`, `Merges do not deploy` sets `false`.
- `deploys_first(facts)`: `Merges do not deploy` when `calibrate.deploys(facts)` is false,
  `Merges deploy` when it is true or the facts are missing (fail closed).
- `leads(root, repos)`: `{'deploys': {repo: deploys_first(snapshot.get(repo))}}` from
  `calibrate.approved(root)`.
- `ask(..., first=...)`: a `first` value may be a mapping by repository. `widgets` orders the
  choices by `leads(root, repos)` the same way.

### cli/wuwei/commands/setup.py and commands/calibrate.py

- Setup runs `calibrate.survey` before the interview and passes
  `first={'spec': ..., 'deploys': {name: deploys_first(facts)}}`.
- `calibrate --interview` passes `first=interview.leads(root, repos)`.

### cli/wuwei/workspace.py, template and docs

- `"size_exclude": [(str, None)]` in `MERGE_SCHEMA`; a commented line under `[repos.merge]` in
  `templates/workspace/config.toml`.
- configuration.md: `repos.merge.size_exclude` row, `repos.merge_deploys` row names the
  question, the interview table gains `deploys`, the calibration paragraph says the interview
  asks. daily.md names the question in the setup list.

## Tests

- `tests/test_intraday_intake.py`: `plan.added` carries flags (candidate and owner item); the
  replan records evidence once and is refused the second time.
- `tests/test_merge.py`: an item admitted by `plan add` passes `merge check`; missing evidence
  names `plan add item-7`; the replan recovers it; `size_exclude` passes, without it the size
  rule refuses, an excluded never-auto file is refused, a rename out of an excluded path counts.
- `tests/test_interview.py`: the table ids; the `deploys` widget order from the snapshot (no
  facts, a deploy workflow, unmeasured); answering sets `repos.N.merge_deploys`; terminal replies
  and the id list updated.
- `tests/test_setup.py`: setup passes the deploys order from the survey.
- `tests/test_docs.py` (existing): the template key is documented.
