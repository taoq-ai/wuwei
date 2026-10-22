Verdict: PASS
Gate: quality
Item: cache-paths
PR: taoq-ai/wuwei#1242
Head: 74aa5a76d360cedde75c10fcc7cbb0fde4791321
Confidence: medium
Supersedes: cache-paths/quality-b095660.md

## Findings
none

## Probes
- closed: ws.clone reads and writes .wuwei/cache/clone outside the helper at 74aa5a7: clone now takes its path from ws._cached(root, 'clone', '') and raises OSError for a linked folder or entry; my plant (symlink at cache/clone to a file holding `../../../evil`) now raises OSError and creates no jsonl; an existing non-token id is replaced.
- closed: no test for a linked .wuwei at 74aa5a7: test_a_linked_workspace_folder_is_never_read_written_or_pruned (get, put, prune); mutant m2 (resolve comparison removed, both trees) is KILLED by its [get] case (-x stops at the first failure, so I did not see put and prune fail).
- Delta b095660..74aa5a7 read (ws.py, hook.py, tests). pytest tests/test_ledger.py tests/test_hook.py on a git archive of the head: 577 passed.
- specs/cache-paths/probe.py re-run in my scratch folder: generated 23, ran 23, holes 0.
- New mutants, both trees, one at a time: c1 drop the isalnum check KILLED by test_a_clone_id_that_is_no_plain_token_is_replaced_and_the_ledger_stays_in_its_folder; c2 clone without the helper KILLED by test_a_linked_clone_id_never_steers_the_ledger[entry]; h1 drop the hook._confirm skip KILLED by test_confirming_answers_never_deletes_through_a_linked_cache_folder[False]; m1 and m4 re-run, still KILLED.
- Route differential (route_diff.txt, 576 cases, 0 decisions moved) not re-run; reported by the builder.
- Open notes from the previous round stay notes: NUL in a name still raises ValueError on put and prune (same as main); path.is_file() in cache_get and cache_prune untested (m5, m7); atomic_write and fcntl are POSIX-only already at main. New note: ws.clone now raises OSError under a linked cache, so ws.record fails closed there (intended, the message names the link); str.isalnum also admits non-ASCII letters, which carry no separator and cannot leave the ledger folder.

Simplicity: none to delete in the delta; the isalnum check and the hook skip each have a test that fails without them. Earlier note stands: the two is_file() calls are probably redundant, unproven without a differential.

## Residual risk
The check-then-open race is accepted as out of scope by the PR. A workspace that deliberately links .wuwei or .wuwei/cache loses the cache and ledger writes (fail closed) until the link is removed.
