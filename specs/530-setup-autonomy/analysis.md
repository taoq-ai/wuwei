# Specification Analysis Report: 530-setup-autonomy

Artifacts: `spec.md`, `plan.md`, `tasks.md`, checked against `.specify/memory/constitution.md`
and the design spec sections 9.1 and 9.2.

| ID | Category | Severity | Location(s) | Summary | Recommendation |
| --- | --- | --- | --- | --- | --- |
| C1 | Constitution | CRITICAL (resolved) | plan.md Docs; spec FR-015 | The first draft added a "Setup" paragraph to the design spec, which the constitution says only its owner amends. | Resolved: design edits limited to the 9.2 row and the I5 note the Workflow rule requires; the prose goes to `docs/site/configuration.md`. |
| H1 | Inconsistency | HIGH (resolved) | plan.md `next.py`; tasks T019 | `THEN['calibrate']` told the planner to show only `config promote`, but an unconfirmed allowlist answer prints a different `Next:` line. | Resolved: FR-009, plan and T019/T020 make `then` show the printed `Next:` line and update the existing assert. |
| H2 | Constitution (hook latency, test_hooks pin) | HIGH (resolved) | spec FR-009 | Counting unanswered questions inside `next.step` would import `interview` and `calibrate` on the SessionStart hook path. | Resolved: the row comes once per day (telemetry precedent) and the CLI command computes the list; T019 keeps `test_calibrate_is_off_every_hook_path` green. |
| H3 | Security / I5 | HIGH (resolved) | spec FR-005, Assumptions | "Grants allow today" could be read as a default that creates grant rows, which I5 forbids. | Resolved: a config read in `grants.active` like a standing line, no grant row; the shipped value stays `""` and I5's check asserts it (T027). |
| M1 | Ambiguity | MEDIUM | spec US4, Assumptions | "init proposes on a card" is met by a setup question row, not a separate decision record; the card lists rule classes, not each rule. | Accepted as recorded assumption; the answer prints each rule written and the rule table is fixed per adapter. |
| M2 | Scope | MEDIUM | spec Assumptions | "Grants" narrowed to merges; deploy, release and publish keep cards. | Accepted: owner comment 4 puts deploys and releases in the publish floor, and `deploy.deny` is the owner's own never-run list. |
| M3 | Coverage | MEDIUM | FR-013 | No dedicated test task for "no new refusal". | Covered by the existing reason corpus walk in `tests/test_invariants.py` (I1), run in T027 and T029. |
| M4 | Underspecification | MEDIUM | plan.md interview row | The autonomy question and descriptions are not fixed verbatim. | Constrained by `test_interview_options_lead_with_plain_words`, the 12-character header rule and the label rule; T007 and T008 run them. |
| L1 | Inconsistency | LOW | plan.md Docs | Another parallel item may take I18 first. | Plan says use the next free id on the base. |
| L2 | Security | LOW | plan.md `ALLOW` | `Bash(<executable> *)` and `git commit *` widen what runs without a prompt. | Acceptable: PreToolUse hooks still run on allowed commands, so every WUWEI guard still applies; no push, merge, release, deploy or `gh api` rule. |
| L3 | Edge | LOW | spec Edge Cases | A same-day `interview.json` from the older table fails `interview.load` naming the retired id. | Accepted: exit 2 with the reason and the rerun command; earlier days still count through `_recorded`. |

## Coverage Summary

| Requirement | Has task? | Task IDs | Notes |
| --- | --- | --- | --- |
| FR-001 autonomy row, rows removed | Yes | T007 to T010 | |
| FR-002 no shadow_since from the interview | Yes | T007, T008, T011 | |
| FR-003 setup --shadow | Yes | T011, T012 | |
| FR-004 card_for skips autonomy | Yes | T007, T008 | |
| FR-005 merge default in grants.active | Yes | T001 to T004 | |
| FR-006 plan skips the covered card | Yes | T005, T006 | |
| FR-007 unanswered and widgets | Yes | T013, T014 | |
| FR-008 init --upgrade and doctor line | Yes | T015 to T018 | |
| FR-009 calibrate row every day | Yes | T019, T020 | |
| FR-010 allowlist row | Yes | T023, T024 | |
| FR-011 allow_rules and allow | Yes | T021, T022 | |
| FR-012 write on card or terminal answer | Yes | T023 to T026 | |
| FR-013 no new refusal | Yes | T027, T029 | existing I1 walk |
| FR-014 I18 and I5 | Yes | T027, T028 | |
| FR-015 docs | Yes | T028 | |

## Constitution Alignment

Stdlib only, three-state exits, one function per behaviour, test first (every behaviour has a
test task before its implementation task), ponytail (no new module, key, state key or event
kind) and security (records floor and #529 confirmation unchanged; I18 added): aligned after C1.

## Unmapped Tasks

None. T029 is the verification step.

## Metrics

- Requirements: 15; tasks: 29; coverage: 100 percent.
- Ambiguities: 1 (M1, accepted); duplications: 0.
- CRITICAL: 1, resolved. HIGH: 3, resolved. Open CRITICAL or HIGH: 0.

## Next Actions

No CRITICAL or HIGH finding is open; implementation may proceed with `speckit-implement`.
