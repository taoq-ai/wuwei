Verdict: PASS
Gate: arch
Item: breaking-proceed
PR: taoq-ai/wuwei
Head: ddbe122cc7d0209daf2931abdfd4810b8652bc66
Confidence: high
Breaking: no

## Findings
- [low] cli/wuwei/hook.py:243 blocks: no. The yes tuple is shared by every class that reads an owner answer in _answers: owner review rulings, exception rulings (and their follow-up item), breaking rulings and plan approval (plan.approve vs plan.change). "proceed" now approves in all four, so a plan: answer "Proceed with these changes: ..." approves instead of recording a change request. The promise says the rule stays shared, and the spec records this under How this fails (bounded like "Yes, but ...") and the prefix match under Assumptions, so it is a recorded decision, not a silent one.
- [low] blocks: no. Prefix matching means "proceeding ..." also reads as yes; the negations tested ("Do not proceed", "No", "Not now, do not proceed") stay false because they do not start with a yes word. Recorded in the spec's Assumptions.

## Probes
- git diff origin/main...ddbe122: only the yes line in cli/wuwei/hook.py and its vendored copy (byte-identical, cmp), tests/test_breaking.py, and specs/breaking-proceed/.
- git grep at the head for the yes words and answer interpreters: the only answer-text interpreter is hook._answers; guards.py classifies questions, evidence.py reads the recorded approved field, not the answer text. No doc, charter, skill or docs/site page lists the yes words, so none goes stale; the nine "Proceed?" template places (design.md, docs/site decisions and evidence, skills/wuwei, charters/shepherd, guards.py, evidence.py and copies) are unchanged and now consistent with the hook.
- Full suite at the head in a scratch archive copy: 466 passed (runtime size test included).
- Mutant: dropped 'proceed' from the tuple in the copy; test_a_proceed_answer_to_the_breaking_question_approves[Proceed-True] and [proceed.-True] fail.
- probe.py (scratch): owner review answered "Proceed" records approved True; exception answered "Proceeding is fine" records approved True with its follow-up; breaking answered "Not now, do not proceed" records approved False.
- Breaking: the ruling row schema is unchanged; only an answer starting with "proceed", previously recorded as not approved, is now approved. The yes words are not a published contract (not a CLI output, config key, API or documented format), and the change matches the documented template's intent. Breaking: no.

## Residual risk
An owner who types "Proceed" to mean something other than yes on an owner review, exception or plan question now records approval; the free-text answer stays in the ruling row for audit.
