# Implementation plan

Use the existing review_contexts workflow classifier and evidence.gaps consumer. Change only the auto-merge waiting allowlist and classifier error propagation in cli/wuwei/evidence.py. Keep the ready door's existing common evidence path.

## Technical Context

Python 3.11+, stdlib only. Tests use the repository's FakeGh. Runtime budget is net +3 physical lines against 3745; the proposed change adds none. No command parser, config, external API or persisted data shape changes.

## Constitution Check

Test first, no runtime dependency, evidence failures remain closed, no new owner decisions, one issue per branch. The fix keeps the declared runtime cap and repeats source changes in the vendored plugin.

## Steps

1. Record the existing observed review-status fixture and ready-door behavior.
2. Add red cases for pending-review auto-merge across CLI, REST and MCP routes; preserve failed-review and real-gap refusals.
3. Add red unreadable-classifier cases and retain absent-review-workflow CI behavior.
4. Make the minimum runtime change, update the design wording and vendor copy, then run focused suites.
5. Run main/head route differential in archived scratch copies with passed gates at the fake PRs.
6. Record results, commit as the owner, push and open a draft PR. Independent gates and CI remain for the planner.
