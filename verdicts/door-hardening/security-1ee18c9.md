Verdict: PASS
Gate: security
Item: door-hardening
PR: taoq-ai/wuwei
Head: 1ee18c9a8d1954a27939871e53eefc6fb3dffe45
Confidence: high

## Findings
- [low] blocks: no. Closed from security-9910e11: _unwrap is back to main's rule ('=' not in a), at cli/wuwei/guards.py:91 and in the vendored copy. My nine shapes are pinned in tests/test_guards.py: seven in test_irreversible_edges_are_denied, plus terraform (ask) and the curl canary (deny) in test_a_wrapper_assignment_naming_a_door_program_hides_neither_infra_nor_a_leak.
- [low] blocks: no. The hook-seen stamp's try (cli/wuwei/hook.py:60-63) wraps only ws.cache_put and runs before any guard, so it cannot mask a decision. On origin/main 0b5f9f9 a failing stamp escapes into handle's except and opens three non-door decisions: the canary curl, terraform apply's ask, and an MCP send carrying the canary. This branch closes that main-side fail-open.
- [low] blocks: no. Pre-existing on main, outside this item: `rm -rf .wuwei/ledger` and `mv .wuwei/ledger /tmp/x` pass guards.bash, because LEDGER needs a trailing '/' or '.jsonl'. `rm -rf .wuwei/ledger/` is refused. Worth a follow-up item.
- [low] blocks: no. The limits carried from the last round still hold: $()/${} spellings, ncat, socat and python network calls fail open when a guard raises. Every mcp__ call is refused while the hook is broken, as the item's assumption intends.

## Probes
- The head given in the brief (1ee18c9a9a2d...) does not exist ("bad object"). origin/claude/door-hardening resolves to 1ee18c9a8d1954a27939871e53eefc6fb3dffe45 (a merge of 8a19c60 and 0b5f9f9), and I reviewed that sha.
- git archive of the head: full suite 568 passed, 2 skipped. Runtime 2,951 lines. The vendored guards.py and hook.py match cli/ byte for byte (cmp).
- Route corpus, now on main (tests/fixtures unchanged between origin/main and the head, git diff = 0 lines): 57 passed on the head and on origin/main.
- probe_unwrap.py: output on the head is identical to origin/main (diff empty). All the '='-bearing wrapper shapes are refused or asked. The only passes are the four main also passes.
- envcheck.sh, real env with a stub git: env still runs git for 1=/sed, =/sed and 'x y=/sed', so the head's refusals match what really executes.
- probe_hook.py, head versus main, with guards raising: the head refuses every quote and backslash spelling, each network call, every mcp__ tool and str/list apply_patch input. Main passes them or crashes. Nothing main refuses passes on the head.
- probe_stamp.py, cache_put raising OSError, PermissionError or ValueError for hook-seen only: all nine head decisions (force push, '=' push to main, canary curl, terraform, ledger Write, MCP merge, MCP canary send, Read, ls) are unchanged and no hook.error rows are written. On main three of them flip to pass.
- auto-merge now matches tool.endswith('auto_merge'), and only after the DOORS['merge'] suffix check. Of the two names that reach it, only enable_pr_auto_merge ends that way.
- Confidence high: every probe from the last round was re-run on the actual head, against main, with no difference in what main refuses.

## Residual risk
Shell-expansion spellings fail open whenever a guard raises. The pre-existing ledger directory removal noted above is not covered by any guard.
