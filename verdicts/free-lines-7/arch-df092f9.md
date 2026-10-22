Verdict: FIX
Gate: arch
Item: free-lines-7
PR: taoq-ai/wuwei#1237
Head: df092f90cab026fa3e085cc9d75883c1b67044fe
Confidence: medium
Breaking: no (patch: charter prose and generated agents only; no public API element changes)

## Findings
- [medium] PR-body:0 blocks: yes. Failure: the item's promise fixes the Done wording as "a delta off risky paths of docs, generated files or at most 20 lines". The head now reads "a delta of docs, or of generated files or at most 20 lines off risky paths, carries the passes". That departure is a sound two-way choice that matches needed(), but no Assumptions line records it. The PR body still states the old wording in four places: What and why, Promise in my words, the Done table row and the Tests line. It also still shows the old Boundaries 4 table row and sentinel-arch at 2,147 words with 103 words of room (now 2,150 and 100). The goal gate and the owner read a promise the head no longer carries, with no recorded reason (requirement: item promise; arch charter 6, an unrecorded two-way decision). Fix: an Assumptions line saying the Done wording departs from the promise so it matches evidence.needed() (docs carry on any path), why, and what would overturn it. Also update the four stale wording mentions, the Boundaries 4 row and the word counts. No code or charter change is needed.
- [low] charters/_common.md:40 blocks: no. The Done sentence still leaves out two qualifications the code applies. A generated-file delta carries only off risky, owner and contract paths, and only when a dated `Generated` standards line names it (evidence.py:341-344). A delta of at most 20 lines carries only when the gate it needs is quality, so off owner paths and contract files as well (evidence.py:348). The wording before this PR had the same gap, and docs/design.md:94 holds the detail.
- [low] blocks: no. Every generated agent is now at least 100 words under the ceiling, as the acceptance asks, but sentinel-arch has exactly 100 words of room (2,150 of 2,250). The next word added to `_common.md`, `_gate.md` or sentinel-arch.md fails test_a_generated_agent_leaves_100_words_of_room_under_the_ceiling.

## Probes
- closed: Boundaries 4 outward-call scope at df092f9. charters/_common.md:70-71 now reads "Outward text follows `_common-authoring.md`; no outward call carries a secret or workspace content." Both old rules are back: the authoring rule and the ban on secrets or workspace content in any outward call. This matches the guard's vocabulary ("outward call", guards.py:354-360). Gates now read the call ban in their own agent file (agents/sentinel-*.md rebuilt).
- closed: the docs-on-any-path note at df092f9. The new Done sentence lets a docs delta carry on any path and puts only generated files and at most 20 lines off risky paths. Checked against evidence.needed() (evidence.py:284-295): a delta of only DOCS-matching files or specs/ yields no code and no gate, so gate_gaps returns no gap (`if not gate`, evidence.py:348), on any path. One edge: a `.txt` file on a risky path counts as code in needed(), so it does not carry. Same as docs/design.md:94 ("unless it is docs or at most 20 lines off risky paths").
- closed: the builder.md retro-note term at df092f9. charters/builder.md:76 now names "the closing lines of `_common.md` Report", which is the code block with Confidence, Blocked, Gap and Change.
- Delta: `git diff adccd99 df092f9 --stat` shows 21 files: charters/_common.md, charters/builder.md, tests/test_charters.py and the rebuilt and vendored agents and charters. No runtime file changed.
- In a fresh `git archive df092f9` copy (scratch sentinel-arch-free-lines-7/tree-df092f9): `pytest -q tests/test_charters.py tests/test_setup.py` gave 233 passed. `bin/wuwei agents build` followed by `diff -r` against the archived agents showed no difference. `wc -w`: _common.md 803, sentinel-arch 2,150 and sentinel-security 2,007, the two largest.
- Section numbers are unchanged (Decisions 1-4, Evidence 1-4, Boundaries 1-5), so the citations in _gate.md:13 and planner.md:57 and :88 still hold.
- PR body read once with `gh api repos/taoq-ai/wuwei/pulls/1237`: head df092f9, body unchanged from the adccd99 round.
- Confidence medium. The charter text is now right and matches the code for docs. The one block is a PR body record, cheap to fix, and depends on reading the promise's quoted wording as a requirement.

## Residual risk
sentinel-arch has exactly the 100-word room the acceptance requires, so the next `_common.md` rule needs a deletion first.
