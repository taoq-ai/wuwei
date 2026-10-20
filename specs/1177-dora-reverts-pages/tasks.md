# Tasks: DORA and the error budget count conventional reverts and failed deploys, and read past the first page (1177)

- [x] T001 Teach FakeGh in tests/conftest.py to answer paged reads and the deployments and releases lists
- [x] T002 Write the failing tests: revert titles (report and evidence), 150 deploys and releases over two pages, 250 merges with a stop, a warm board's one merged read
- [x] T003 Run them red (5 new tests failed); the board test holds one call on main and fails under the mutant that drops limit=1
- [x] T004 Add the stop to gh.pages; page merged_prs, deployments and releases; keep the board at one page
- [x] T005 Add the shared revert rule and use it in budget and dora; copy the four files to .claude/wuwei/cli/wuwei/
- [x] T006 Move the replay case key to the paged first read; run the full suite green
- [x] T007 Merge origin/main (#1176, #1172) into the branch; keep both sides in conftest.py and test_report.py
- [x] T008 Owner ruling "In this PR": FakeGh answers deployment statuses; write the ai-stacks test and run it red (rate 0.2, time to restore unmeasured)
- [x] T009 Replace the revert rule with evidence.failures (reverts plus failed production deploy runs, with restores); use it in budget and dora; filter deployments to the window in gh.deployments
- [x] T010 Answer the deployments read in the replay case; update design.md section 6 and the DORA and error budget docs; full suite green at +12 runtime lines
- [x] T011 Fix round 1 (arch, security, quality at 8e626d2): FakeGh plays a refused deployments read and a missing status; write tests for the refused reads, production names, the production flag, the superseded green deploy, unfinished reruns, another environment's success, revert word boundary, the rate cap and the 100 status bound, and a cold board's budget read; run red (14 failed; 1200 status reads on the cold board)
- [x] T012 Budget counts the reverts when a deploy read is refused; production needs the flag or prod as a word not led by pre or non; the newest 100 production deploys are read; the rate is at most 1; the board reads the budget once before its pool; focused suites green at +12 runtime lines against 2226d90
- [x] T013 Mutants: 15 of 15 killed; route differential plain, reverts and refused: 0 moved against main (57 moved at 8e626d2 in the refused variant); docs and spec updated
