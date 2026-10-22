Verdict: PASS
Gate: security
Item: multi-session
PR: taoq-ai/wuwei#1238
Head: b19c6b928b0ee15c22cffa8e9b99fbe0e30e80a6
Confidence: medium

## Findings
- [medium] cli/wuwei/plan.py:119 blocks: no. Existing gap made easier to reach: plan.approve approves every open item, so an item another session added (or a merge brought in) between the plan shown to the owner and the answer is approved unseen (OWASP A01 broken access control). The merge itself never sets approved; approve() should take the ids shown.
- [low] cli/wuwei/board.py:69 blocks: no. The live bound compares ts as text, so a seat.started row stamped ahead of this clock holds its item until that time passes. That covers clock skew between clones and a row pulled from the state branch: 10 years ahead still refused in a probe. Main's day filter dropped such rows (CWE-20).
- [low] cli/wuwei/hook.py:57 blocks: no. TOCTOU (CWE-367): the hold exists only once PostToolUse writes seat.started. Two sessions launching for one item at once both pass, and a foreground launch writes its start row after its seat ends. This is a coordination limit, not a door.
- [low] cli/wuwei/hook.py:79 blocks: no. Item: is matched case-sensitively and unquoted. 'item: I-1', 'ITEM: I-1', 'Item : I-1', 'Item: "I-1"', a fullwidth colon or a table cell neither hold an item nor get checked, at start or at launch (consistent, so no false refusal).
- [low] cli/wuwei/hook.py:58 blocks: no. Session id and role from ledger rows go into the model-facing deny reason and board text with no escaping. A crafted session string reads as an instruction in a probe (OWASP LLM01). The source is harness payloads or the trusted state branch.
- [low] cli/wuwei/plan.py:48 blocks: no. Merge keys ids case-sensitively, but find() ignores case. A remote 'i-1' and a local 'I-1' are both kept, and find('I-1') returns the higher score. Approval travels with its own contract, so no contract is approved that some clone's owner did not approve (CWE-178).
- [low] cli/wuwei/plan.py:40 blocks: no. The changed stamps are trusted as given. A far-future remote stamp wins every later merge and reverts local edits. An unstamped tie keeps the local copy and drops a remote approval (fails closed). plan.save and merge are unlocked read-modify-write, so concurrent writers lose updates (CWE-362). In every probe the approval stayed paired with its contract.

## Probes
- Route differential: tests/fixtures/routes.json, sha256 de377966b71fcb42f20fd057b033b43377891f3be8fd7d39130a81f750ed71c1, the same at main 1bcefca and at the head. All 288 routes were read through hook.pre_tool (a Bash payload, session s1) and through guards.bash, at main and at the head. 0 routes moved in verdict or reason (213 deny, 74 pass, 1 note), and 0 differ from the recorded verdicts.
- Hold check, at the head in a git archive copy: launches for an item held by another live session were refused, including a different case. The holding session itself was not refused. After the seat stopped, the item was free again. A row with no session or an empty one held nothing. A payload with no session_id was refused (fails closed).
- Spellings: '## Item: I-1' and '1. Item: I-1' parse and are refused. The 10 other spellings above parse to None and pass (they are notes).
- ReDoS: asked() timed on 7 adversarial prompts of 100k to 404k chars (star runs, list markers, repeated 'Item', 200k lines). Each took 0.032 s or less.
- Merge and approval: an older unapproved remote kept the local approved P1. A newer unapproved remote replaced it with P2, unapproved (a consistent pair). An unstamped tie kept local approved=False. A case-variant remote id shadowed the local one in find().
- Cross-session forgery: the gone set was already cross-session on main. Releasing a hold needs a stop row with the holder's agent id, and seat rows come only from harness hooks: guards.py:383 refuses a hand-made 'wuwei hook' and edits to the ledger are refused. The WIP limit and seat ceiling exist only in the charters. Counting more seats only tightens the team row, and an Agent launch has no guard door that `or held` could mask (guards.pre_tool returns None for Agent and Task).
- Paths: session ids from disk reach only strings, never a filesystem path. The pending report name (hook.py) sanitizes them as before. plan.merge writes via atomic_write (no write through a planted link) and reads plan.json as files() already did.
- Mutants (both trees, run one at a time, test_watch and test_sync): own-session held, case-sensitive match, stops ignored, no live bound, empty session counts, tie remote wins, always stamp, push without merge and pull without merge. All 9 were killed by behavioural tests.
- Targeted suites at the head: test_watch, test_sync, test_hook and test_codex, 626 passed.
- Supply chain: no dependency, lockfile or workflow change. CI runs no secret, dependency or static scanner, so scanning is unmeasured.
- Confidence medium: the trust analysis assumes the wuwei/state branch is owner-trusted, as main already does. Real harness timing of PostToolUse for foreground and background Agent calls was not run.

## Residual risk
Holds are advisory coordination: no lock, the start row is written after launch, and spelling is case-sensitive. Plan approval correctness across sessions rests on approve() approving every open item, which predates this item.
