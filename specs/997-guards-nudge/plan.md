# Implementation Plan: #997 guards-nudge

## Technical Context
Python 3.11+, stdlib runtime, pytest development only. Reuse hook.enforce, guard floor classification, shell normalization, workspace migration, merge evidence checks, recorded build handbacks and verdict finding parsing. No new adapter or state key.

## Constitution Check
The owner explicitly amends principle VII and design 4.6/4.7/4.9/9.1/9.2 in this issue. Preserve three-state exits, scope, relevance, protected producers, no subprocess in core, test first, and existing retry caps. Stop remains untouched.

## Design
1. Hook display transforms let-through reasons into nudges without changing events. Schema/template default false; explicit true remains.
2. Infrastructure refusal gets a narrow prefix floor instead of putting all deployments on it. Narrow host permissions and migrate known shipped obsolete denies. Retain infrastructure cards.
3. Ordinary merge eligibility becomes evidence annotation, with gates/checks/protection, explicit veto, breaker and waits retained. Keep head-bound cards for owner_paths and never_auto_paths. Raw merges of raised or claimed PRs stay on the floor and name bin/wuwei merge as the next step.
4. UUID normalization is a small outward comparison helper using stdlib UUID. Named servers stay exact.
5. Read the existing build result text and initial verdict findings. Require one qualified no-change answer per blocking finding, then keep the existing checked-head transition. Delta prompts include the same handback for every review route.

## Validation
Write and run failing tests per behavior, implement the minimum change, then run explicit test files using the task interpreter with -m pytest -q -p no:cacheprovider. For this fix round, only files importing changed modules are run, as requested. Tests use existing port fakes. Inspect changed files for forbidden local paths, em-dashes and emojis. Check related refusal paths for #857/#987/#982 against code.

## Alternatives
Keeping action cards would retain the reported failures. Removing evidence checks would violate the boundary. The selected change keeps evidence checks and makes ordinary hook refusals visible guidance.
