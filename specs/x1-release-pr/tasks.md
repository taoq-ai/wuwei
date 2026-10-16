# Tasks: a release-please PR is read as generated (X-1, X-2)

- [x] T001 Write the failing tests in tests/test_evidence.py: the 1.2.1 shape, a person, another branch, an extra code file, an unreadable config, package paths
- [x] T002 Run them red (6 failed: the release shape still listed "no test in the diff" and "gates missing: quality")
- [x] T003 Add RELEASE_BOTS and release(repo, pr) to cli/wuwei/evidence.py; drop the test and gate gaps for a release PR in gaps
- [x] T004 Free the added lines in evidence.py without a behavior change
- [x] T005 Run the full suite green, runtime at 2,999 lines
- [x] T006 Fix round 1: tests for a hooks entry in the plugin.json patch, a missing patch, a manifest patch with more than a version, a rename into CHANGELOG.md and a deep config, run red (6 failed: 5 assert [] == both gaps, 1 RecursionError)
- [x] T007 Keep patch and the rename flag in gh.pr; count an extra-file or the manifest only when its patch changes version lines; catch any config error in release
- [x] T008 Tests for a config of {}, an extra-files entry with no path and a string extra-files; a design.md line on release PRs; full suite green at 2,999 lines
