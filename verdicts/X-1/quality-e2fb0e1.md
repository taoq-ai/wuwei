Verdict: FIX
Gate: quality
Item: X-1
PR: taoq-ai/wuwei
Head: e2fb0e1d96fccb45a5adb8a8a11853971a946d7c
Confidence: medium
Breaking: no

## Findings
- [medium] tests/test_evidence.py:700 blocks: yes. Failure: the deletion half of the patch guard in release() (`if x[:1] in ('+', '-')`) has no test. Reversed to `x[:1] == '+'`, the whole suite (316 tests) still passes. Every existing patch case puts the unwanted content on a `+` line, and every `-` line in the tests is a valid version line. The input the reversed guard lets through is a plugin.json patch `@@ -1,3 +1,2 @@\n {\n-  "hooks": {"PreToolUse": []},\n-  "version": "1.2.0",\n+  "version": "1.2.1",` (checked: the real VERSION_LINE rejects the hooks line). A bot release-please-- PR that deletes a hook or guard entry from an extra-file would then be read as generated with no test and no gate. The code is correct; the missing test is the finding. Fix: add one parametrised case to test_a_patch_that_smuggles_more_than_a_version_bump_keeps_every_gap with a `-` line that is not a version line, and the same for the manifest.
- [low] cli/wuwei/evidence.py:122 blocks: no. Mutant `files and all(...)` to `all(...)` survives (an empty file list). Equivalent: a PR with no files owed no test or gate. Same note as at 13fc173.
- [low] cli/wuwei/evidence.py:389 blocks: no. Mutant `size >= MAX_LINES` survives: the 400 line boundary has no test. The operator is unchanged by the walrus reshape, so it is an existing gap, not this delta.
- [low] cli/wuwei/evidence.py:110 blocks: no. Extra-files whose version lines are not `"key": "x.y.z"` (version.txt, TOML, YAML) never count as bumps and keep every gap. This fails closed and design.md says a patch that is not a version line keeps the gaps; noted as a limit.

## Probes
- Fetched e2fb0e1 and ran the suite in a clean `git archive` copy under scratchpad/qual2-*: 316 passed; runtime 3,000 lines (wc -l cli/wuwei/*.py), at the cap.
- Compared with my 13fc173 verdict (PASS). Closed since: the KeyError case (`{}` and an extra-files entry with no path, now parametrised and caught by `except Exception`; the narrowed-except mutant is killed by the `deep` case), the `[] +` type check (test_extra_files_given_as_a_string_are_not_read_as_paths kills the listcheck mutant), the design.md paragraph (present and accurate), and the CHANGELOG.md pin. The DEFERRED/REASON and _rule survivors stay closed as existing gaps.
- The `:=` reshapes, mutants all killed except the boundary note above. item_for: guard disabled (test_the_wuwei_footer_links_a_pr_to_its_item) and match[0] for match[1] (test_complete_evidence_has_no_gaps). gate_gaps: inverted list (test_a_declared_breaking_change_needs_an_announcement_then_the_owner) and guard disabled (test_a_contract_file_calls_the_arch_gate_at_any_tier). gaps: template guard disabled (test_the_repository_pr_template_is_honoured), size computed from no files and size without the Size: line (test_a_big_batch_asks_to_split_or_say_why), threads disabled and plural (test_ci_threads_and_reviews). `size` is read only inside its own if, so binding it in the condition changes nothing; spec_gaps was only re-wrapped. I read all four as behaviour-equal.
- New release logic, mutants killed: renamed ignored (test_a_release_pr_that_renames_a_file_into_an_allowed_path_keeps_every_gap), gh.pr drops renamed or patch (same test, test_a_release_please_pr_is_read_as_generated), bumped() removed, patch type check removed, empty patch accepted, key "version" check removed, manifest-only key rule removed (the manifest takes path keys test), split('\n') to splitlines() (the smuggling cases), fullmatch to match, re.A removed, semver shortened, manifest not always allowed, author and branch checks removed. Survivors: the two above.
- Read the patch rules for bypasses: hunk headers and context lines are skipped as they cannot change the file; "\ No newline" is skipped; a CR, form feed, U+2028 or vertical tab inside a line fails fullmatch (tested); a missing patch (large or binary diffs) keeps the gaps. CHANGELOG.md has no content check, as pinned; it is a docs path anyway.
- Open question from the first round (budget overrun): unchanged and consistent with design section 6. Not retested.
- Simplicity: none to delete. The `bumped` closure is one use but keeps the allow rule readable beside the files test; the `:=` and re-wrap changes only free lines under the cap. The fail-closed `except Exception` is a trust-boundary guard and stays.

## Residual risk
Once the deletion case is tested the release logic is well covered. A bot PR can still change a version value in an allowed file to any strict semver; that is the stated limit.
