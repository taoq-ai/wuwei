Verdict: PASS
Gate: arch
Item: cache-paths
PR: taoq-ai/wuwei#1242
Head: 74aa5a76d360cedde75c10fcc7cbb0fde4791321
Confidence: medium
Breaking: no (patch: existing 8-hex clone ids are alphanumeric and stay, so ledger file names do not move; no command, exit code or file shape changes)
Supersedes: cache-paths/arch-b095660.md

## Findings
- [low] blocks: no. Operability: with a linked cache, `wuwei doctor` reports "ledger: intact" and "hooks: no hook fired in the last 2 minutes", because hook-seen is never written. It does not name the link, which only appears on the hook's stderr ("the refused record failed: ... is a link"). One doctor line naming a linked .wuwei/cache, or a linked clone entry, would point the operator at the cause.
- [low] blocks: no. The new assumption says door calls are denied with the error. At this head the route differential moved 0 decisions across 288 linked routes, and my launcher probe showed a door keeping its own reason with the link named on stderr. What actually happens is "records are skipped, decisions stand", which is the better contract; the assumption text overstates it.
- [low] blocks: no. A CLI command that records (for example `wuwei andon`) stops on the OSError with a traceback whose last line names the link. __main__ catches OSError only around sync (line 142). Not run.

## Probes
- Fail-closed contract judged right. It keeps three things:
  - The audit stays inside .wuwei: main wrote clone and cache entries into the link target on all 288 linked routes; the head writes none.
  - No hash chain splits: falling back to a throwaway id would start a new ledger file on each call.
  - Doors keep judging. route_diff.txt shows 0 decision or reason moves, and my run of the head launcher on a linked workspace gave the same: the Bash door was denied for its own reason, Read and Edit passed, nothing landed outside.
  - This matches design.md section 9 (a door that cannot judge stays shut; other hooks fail open with a reason).
- probe_confirm.py re-run at 74aa5a7: final True and final False both leave outside/answer-s--1.json, and notes are []. At b095660 final False deleted it.
- probe_clone.py re-run at 74aa5a7: ws.record raises an OSError naming the link, the planted outside/clone keeps its content, and no .jsonl exists anywhere in the case folder. At b095660 the row went to ws/escape.jsonl.
- probe_failclosed.py (scratch, head launcher, stub gh): outside folder empty after three PreToolUse calls plus doctor and status.
- Mutants, applied to both trees and run one at a time against the delta tests:
  - _confirm skip turned off: 1 failed (the final=False case).
  - clone check bypassed: 2 failed.
  - isalnum replace removed: 1 failed.
  - All killed. The unmutated head passes 25 selected tests.
- Callers: `git grep -n "'cache'" 74aa5a76 -- cli/` lists exactly the uses FR-001 names. guards.py:34 and :41 and sync.py:17 are tables; replay.py:37 is a replay copy; hook.py:344 is checked per hit; ws.py:219, 222 and 244 are the helper and the checked prune glob.
- Budget: `cat cli/wuwei/*.py | wc -l` gives 3463 (+15 against main, within FR-003's 18 and the 3,600 cap). Vendored copy: `diff -r -x __pycache__` shows no difference.
- isalnum is Unicode-wide, but no alphanumeric character is a separator or dot, so a planted id cannot move the ledger path.
- closed: hook.py:353 _confirm deleting through a linked cache folder, at 74aa5a7
- closed: ws.py:136 clone id read and written through a linked cache folder steering the ledger, at 74aa5a7
- Confidence medium: I re-ran both former failures and the launcher on a linked workspace. I did not run the full suite, and the doctor and CLI behaviour under a link is read from code and one doctor run.

## Residual risk
The check-then-open race stays out of scope (recorded assumption). A linked cache now silences the audit until the operator removes the link, and the operator is told so only on stderr.
