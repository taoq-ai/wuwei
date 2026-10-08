# Specification Analysis Report: #561 README Principles

Artifacts: spec.md, plan.md, tasks.md, constitution 1.5.0. Docs and docs tests only; no
runtime code.

| ID | Category | Severity | Location(s) | Summary | Resolution |
|----|----------|----------|-------------|---------|------------|
| A1 | Inconsistency | HIGH | spec.md FR-001, tests/test_docs.py:182 | Nine wrapped paragraphs plus new credits would push the README past its 300-line cap, and raising the cap would weaken a pinned test. | Resolved: each principle and each new credit is one line (soft wrap), like the "What ships today" bullets. A dry run of the drafted text gives 276 lines before the ships and credit lines, about 285 after. |
| A2 | Coverage gap | HIGH | spec.md US2, issue Scope item 5 | The issue asks that the tests pin "landing" disappearing when an issue closes; no test can call the tracker. | Resolved: the landing rule reads `specs/<n>-*` on the base (every feature lands with its spec directory). plan.md change 1 and T002. |
| A3 | Constitution | HIGH | plan.md Risks, test_glossary_words_link_at_first_use | Removing Philosophy removes the first linked `unmeasured`; the new text introduces `mandate` and `novel` for the first time. Unlinked, the glossary test fails. | Resolved: the drafted items link all three at first use; plan.md Risks lists the glossary words to avoid. |
| A4 | Coverage gap | MEDIUM | spec.md FR-004, tasks.md T004 | The deploy sentence removal from "What WUWEI is and is not" had no test. | Resolved: T004 asserts no `deploy` in that section. |
| A5 | Ambiguity | MEDIUM | plan.md change 1, item 7 pin | The pin `'ci'` matches inside many words. | Resolved: the pin is `'ci is the gate'`. |
| A6 | Underspecification | MEDIUM | spec.md Assumptions, plan.md Acknowledgements | The MIT CISR briefing and the vGOAL paper have no verified deep link offline; the drafts link the CISR site and KU Leuven. | Accepted: recorded as an assumption for review; the owner can swap the deep links without a test change. |
| A7 | Underspecification | MEDIUM | spec.md FR-005 | #586 has no issue file in this run, so it has no plain-words name. | Accepted: listed as a bare issue link in the landing line (Assumptions). |
| A8 | Inconsistency | LOW | plan.md technical context | The drafted principles alone read 3.6 nominalisations per 100 words, above the docs class rate of 3.0. | Checked: the docs class after the change measures 2.853 per 100 words with 77 long sentences (budget 3.0 and 77). T011 re-measures. |
| A9 | Inconsistency | LOW | spec.md US2 scenario 3 | If #557 or #560 lands on main before this item merges, the landing test fails on the rebased branch. | Intended: that failure is the pin; the builder removes the word on the base it builds on. |
| A10 | Constitution | LOW | constitution Workflow | The constitution lists clarify and checklist; this run answers clarifications as Assumptions. | Accepted per AGENTS.md (no clarifying questions; record assumptions). |

## Coverage

| Requirement | Has task? | Task IDs | Notes |
|-------------|-----------|----------|-------|
| FR-001 Principles section, nine one-line items | Yes | T001, T003, T006 | |
| FR-002 Mechanism per item, in order | Yes | T001, T006 | PRINCIPLES tuple in the test |
| FR-003 Comparison removed | Yes | T001, T007 | |
| FR-004 What WUWEI is and is not | Yes | T004, T009 | |
| FR-005 Path line and landing line | Yes | T002, T004, T008 | |
| FR-006 Acknowledgements and NOTICE | Yes | T005, T010 | |
| FR-007 Test strength kept | Yes | T001 to T005 | word ban, em dash and 300-line cap kept |
| FR-008 Unchanged sections | Yes | T011 | existing tests |

Every behaviour has a test task ordered before its implementation task.

## Metrics

- Requirements: 8; tasks: 12; coverage 100 percent.
- CRITICAL: 0; HIGH: 3 (all resolved); MEDIUM: 4 (2 resolved, 2 accepted as assumptions); LOW: 3.

## Next action

Ready for speckit-implement.
