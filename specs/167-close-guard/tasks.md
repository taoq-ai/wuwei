# Tasks: Refuse unresolved day close

## Setup

- [X] T001 Read contracts and reproduce the dry-run failure read-only; record evidence in specs/167-close-guard/plan.md.
- [X] T002 Write and validate specs/167-close-guard/spec.md and plan.md.

## US1: Approved work and pushed branches

- [X] T003 [US1] Add failing item and branch close tables in tests/test_stop.py and adapter checks in tests/test_close_branches.py.
- [X] T004 [US1] Extend cli/wuwei/closing.py and adapters/vcs/git.py with registry and fake support for pushed branch evidence.

## US2: Pending owner decisions

- [X] T005 [US2] Add failing decision, retry and mixed-error tables in tests/test_stop.py.
- [X] T006 [US2] Enforce pending owner decisions in cli/wuwei/closing.py using validated records and existing verified dispositions.

## US3: Build parks

- [X] T007 [US3] Add failing lint, close integration and preserved-record tests in tests/test_build.py.
- [X] T008 [US3] Produce valid recorded seat decisions in cli/wuwei/commands/build.py.

## Validation

- [X] T009 Document close and park behavior in docs/site/concepts.md.
- [X] T010 Run targeted and full tests, review scope/trust/error handling and check authored file hygiene; finish specs/167-close-guard/tasks.md.

## Adversarial review fixes

- [X] T011 [F1] Integrate main's #187 build loop and decision writer; reproduce rejected build parks, record item dispositions, and adapt regressions to the persisted build record.
- [ ] T012 [F1] Rebase branch metadata onto main. Sandbox prevents writing the shared Git index (`git rebase --autostash main`: `could not write index`); main's files are integrated in the working tree.
- [X] T013 [F2] Reproduce owner-decider seat routing returning exit 2; return a recorded exit-1 rejection with the correct Decided-by diagnostic.
- [X] T014 Run the required full pytest suite on the combined tree after both fixes: 5230 passed, 2 skipped in 81.98s (0:01:21).

## Dependencies and execution

T001 -> T002 -> T003 -> T004; T005 -> T006; T007 -> T008; all -> T009 -> T010.
US1 and US2 share the close reader and run sequentially. US3 tests could be prepared
independently, but this seat implements all changes locally. Each story has its own
in-process acceptance tests; a focused read-only review follows implementation. Deliver all three
stories, starting with the unresolved approved-item regression.
