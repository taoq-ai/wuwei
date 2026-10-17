Verdict: PASS
Gate: quality
Item: charter-review
PR: taoq-ai/wuwei#1124
Head: 7f67ab2479c16c529ee54bf19a172ba495ab0c61
Confidence: medium
Breaking: no

## Findings
- [low] charters/_common.md:44 blocks: no. The new "(over at least five merges)" floor is not pinned. Mutant: "five" changed to "two" in the copy, all 79 tests in test_charters.py pass. The value matches evidence.py:221 (`found['merged'] >= 5`) at the head; the missing test is a phrase or constant check like the other thresholds.
- [low] tests/test_charters.py:73 blocks: no. `10 code files` is pinned as a literal; evidence.py:259 hardcodes `len(code) > 10` with no constant, so only the 200 is tied to evidence.WIDE. Changing the 10 in evidence.py would not fail a test.
- [low] blocks: no. Carried, unchanged and not re-opened: the clause-level reading of the 35-word cap (the splitter breaks at `;`), the wrapped-line-starting-with-placeholder drop, the AGENTS.md heading-rename and bullet-deletion survivors in test_setup.py, the count-only trigger fixture, and the 13,785 to 15,294 word growth against the spec's "shorter charters" rationale.

## Probes
- Guard code: this diff changes no guard code (cli/ unchanged from the previous head; the only runtime file touched is none), so the AGENTS.md "Testing the guards" probes do not apply and none were run.
- Closed from the previous verdict, each re-read at the head:
  - Red-first counts. `git archive origin/main` with the head's tests/test_charters.py, tests/test_setup.py and tests/fixtures/skill-triggers.json copied in, `pytest -q tests/test_charters.py tests/test_setup.py`: `32 failed, 85 passed`; `test_no_sentence_is_over_35_words` fails 11 (of 19 files); `word_ceiling` fails 0 (of 8). This matches spec.md US1 (lines 110-119), tasks.md T008 and the PR body line 29.
  - Other figures: `git diff --stat origin/main 7f67ab2` 65 files; 30 files outside agents/ and .claude/ (30 hand-written); `wc -w agents/*.md` sentinel-arch 2,230 (largest), lead 1,658 (smallest), total 15,294 (13,785 on main); 14 `def test_` in tests/test_charters.py. All match the spec and PR body.
  - Dead branch: `done = text.split('## Done', 1)[1]` and one `re.split(..., maxsplit=1)` replace the conditionals at tests/test_charters.py:85-86. Gone.
  - Average test: renamed `test_sentences_average_under_20_words`, threshold 20; passes at the head (previous highest per-file average 16.7).
  - Constants: tests/test_charters.py imports `evidence` and builds the TRIVIAL, BUDGET, MAX_LINES, STALE_DAYS and WIDE phrases from it.
- `pytest -q -W error` in a `git archive 7f67ab2` copy: 1682 passed, 2 skipped (same as before; the 2 skips are ssh-keygen absent in test_release.py, unchanged).
- Mutant (h), each in a fresh copy, `pytest -q tests/test_charters.py`: evidence.WIDE 200 to 250, TRIVIAL 20 to 25, BUDGET 0.15 to 0.2, MAX_LINES 400 to 500, STALE_DAYS 3 to 5 (this one fails on the `{3: 'three'}` lookup, a KeyError, still a failure): each fails `test_decisions_and_done_are_stated_once_in_common`. "over 200 lines" changed to "over 300 lines" in charters/_common.md fails the same test. The surviving wide-change mutant from the previous round is killed.
- Survivor: "five merges" changed to "two merges" in _common.md (see the first finding).
- charters/sentinel-arch.md reword: the preamble no longer names `docs/design.md` or the ADR sub-fields; the closing paragraph now says a trust defect seen is a finding that blocks under gate rule 5. Prose only; the sentence-length, ceiling (2,230 under 2,250) and generated-agent drift tests pass, and agents/ and .claude/ were rebuilt (`test_the_generated_agents_match_the_charters` and the vendored-copy test pass).
- wuwei-rules wording change: the safety-slice test (`test_a_requested_reviewer_and_staleness_are_process_fit_everywhere`) passes on the new text.
- Simplicity: none left from the previous round. The dead branch is deleted and the average pinned at the charter's 20. The `{3: 'three'}[evidence.STALE_DAYS]` lookup is a deliberate fail-loud tie to the constant, not deletable. Nothing here is trust-boundary validation, fail-closed handling or a data-loss safeguard.
- Confidence is medium: all prior blockers re-measured and closed, the mutants were caught, but the surviving notes remain untested prose limits.

## Residual risk
Charter prose is held by phrase-presence tests, so a rewrite that keeps the pinned phrases can still drift (the five-merge floor, the 10-file count, builder.md and skill copies of the thresholds). The trigger fixture still has no consumer.
