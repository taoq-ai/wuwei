# Tasks: DORA and the error budget count conventional reverts and read past the first page (1177)

- [x] T001 Teach FakeGh in tests/conftest.py to answer paged reads and the deployments and releases lists
- [x] T002 Write the failing tests: revert titles (report and evidence), 150 deploys and releases over two pages, 250 merges with a stop, a warm board's one merged read
- [x] T003 Run them red (5 new tests failed); the board test holds one call on main and fails under the mutant that drops limit=1
- [x] T004 Add the stop to gh.pages; page merged_prs, deployments and releases; keep the board at one page
- [x] T005 Add evidence.reverts and use it in budget and dora; copy the four files to .claude/wuwei/cli/wuwei/
- [x] T006 Move the replay case key to the paged first read; run the full suite green at 3,211 runtime lines
