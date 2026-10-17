Verdict: FIX
Gate: arch
Item: merge-evidence
PR: taoq-ai/wuwei#1114
Head: fc27033543ad8c0a57ec39f84fd0082d5d8587f2
Confidence: high
Breaking: yes: an approved breaking: or exception: ruling no longer clears the owner review on owner_paths, so a PR that read mergeable now holds; a repository whose CI runs only on pull_request_target now gets "CI not started at <sha7>" on a head with no checks; the gap text on an unreadable Actions host changes to "CI not started at <sha7> (Actions host unreadable: <error>)"; a docs-only head with no checks no longer holds

## Findings
- [medium] cli/wuwei/evidence.py:382 blocks: yes. Failure: the docs-only skip of the CI-not-started gap reuses the no-test reading, where DOCS matches any `.txt`, so a dependency-only PR (requirements.txt, requirements-dev.txt) with an empty rollup in a repository with pull_request CI now reads no gaps and can merge before its CI registers; on main the gap held it. This contradicts the rule `needed()` (evidence.py:252, #1050) already fixed, that a risky `.txt` is code, and the plan's assumption covers only docs ("a docs-only change is safe"), not dependency manifests. Fix: read `code` the way `needed()` does (a `.txt` matching RISKY counts as code), with a test for a requirements.txt-only diff.
- [low] blocks: no. The BREAKING CHANGE line names the owner review change and pull_request_target (so the pull_request_target change is declared), but not the changed gap text on an unreadable Actions host (CLI output of `wuwei evidence`/`status`) nor the docs-only relaxation; add both so the owner's `breaking:` confirmation covers everything that changes.
- [low] blocks: no. The PR body has no `Announcement:` line, so breaking_gaps will hold the merge until one is added; the migration line for open owner-path PRs is otherwise complete (owner review rulings recorded by hook.py:244 carry no kind, so past owner review rulings keep counting).
- [low] blocks: no. The cache key `ci-<repo>` is unchanged, so a `[]` cached by the old code (pull_request only) is served for up to a day after upgrade and a pull_request_target-only repository is seen up to a day late. Acceptable; worth a line under Assumptions.
- [low] blocks: no. A release-please PR whose only file is CHANGELOG.md now skips the CI-not-started gap (it is all docs); one with a manifest or extra-file still gets the read. The generated exemption itself moved correctly: no-test still exempts generated PRs (mutant removing `not generated` fails 4 release tests), gates_for is unchanged, and the CI gap stays unexempted as on main.

## Probes
- Suite in a git archive copy at fc27033: 1207 passed, 2 skipped (pytest -q).
- Added probe test in the copy: files ('requirements.txt',), ('requirements-dev.txt','docs/x.md'), ('CMakeLists.txt',) with empty rollup and pull_request CI: evidence.gaps returned [] for all three (no CI not started).
- Mutants, each in a fresh archive copy: drop `not kind` on rulings -> test_only_an_owner_review_ruling_clears_the_owner_review fails; drop `code and` from ci -> test_a_docs_only_diff_gets_no_ci_not_started[files0] fails; drop the pull_request_target read -> test_a_failed_actions_read_is_not_cached (and the target test) fails; drop `not generated` -> 4 release-please tests fail. All killed.
- Callers: owner_approved has one caller (evidence.gaps); ruling producers are hook.py:244 (owner review, no kind; breaking) and hook.py:250 (exception); breaking_gaps, excepted and report.py read by kind and are unaffected. No code consumer parses the "CI not started" text (git grep).
- Actions reads: the combined answer is cached a day per repository, so at most one extra read per repository per day, only where no pull_request run exists; docs-only heads make no read; a failed read is not cached.
- Principles 4 and 7: the docs-only skip spares the owner an exception for a path-filtered docs workflow (4) and a rollup with any check still holds (7); the two-way choice is recorded under the plan's Assumptions. Fine for docs, not for risky .txt (finding 1).
- Docs: design.md and docs/site/concepts/evidence.md agree with the code on owner review and on "code head"; design.md also names pull_request_target and the unreadable-host text.
- Line budget: runtime 2976 -> 2977 (+1, budget 6); with records (+12) and gh-args (+3) it reaches 2992 of 3000, headroom 8, enough for the one-line fix.
- Confidence high: the hole is reproduced by a running probe, and the code diff is small and fully read.

## Residual risk
Other non-docs `.txt` files (CMakeLists.txt) still read as docs for both the no-test gap and the CI skip; reading them as code is outside this item's promise unless the owner widens it.
