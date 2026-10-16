Verdict: PASS
Gate: quality
Item: doors-by-rest
PR: taoq-ai/wuwei
Head: dce9ed791a006321afb0d6b319e45a071d54bb71
Confidence: medium

## Findings
- [low] cli/wuwei/guards.py:196 blocks: no. Removing .lower() from the merge door's auto flag (m[3].lower()) fails no test; with re.I an uppercase MERGE only changes auto=True, and the merge door is reached either way, so it is equivalent for the door verdict. A test on the door's auto argument would pin it.
- [low] blocks: no. Removing --raw-field from the field-key list still survives (only base is read from it); removing jq from the long-flag list is equivalent (an unmatched --jq= is skipped as a dash argument).

## Probes
- Copy: git archive of dce9ed7; full suite 689 passed, 2 skipped; runtime 2,996 lines (cat cli/wuwei/guards.py and the rest of cli/wuwei/*.py through wc -l), size test passes; vendored guards.py identical to cli/wuwei/guards.py.
- Re-ran 69 mutants on the tree and vendored copy together: 64 killed. The earlier blocker, the --input POST default, is now killed by the new rulesets, protection, merges and git/refs --input tests; the graphql lower() mutants (drop .lower(), or disable the branch) each fail a test, and removing re.I from route matching is killed by the uppercase path test.
- Survivors: the .lower() on the auto flag, --raw-field, --jq (equivalent) and an invalid mcp refs/heads mutant that patches git_push first (killed on the MCP line earlier).
- Simplicity: none to delete; the change is one .lower() plus tests.

## Residual risk
The auto flag spelling is unpinned but cannot change which door is reached.
