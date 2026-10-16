Verdict: PASS
Gate: security
Item: 1067
PR: taoq-ai/wuwei
Head: 3fb3f405ed6c888942a406e6f82c0f651c857bb0
Confidence: high

## Findings
- [low] cli/wuwei/evidence.py:343 blocks: no. Anyone who can post a commit status can point its target_url at a run of a review workflow, and the regex is not anchored, so `https://evil.example/github.com/acme/app/actions/runs/8` also matches. A failing CI status then reads `change request outstanding: <context>`. It stays a safety gap and the merge door still refuses (probed). This is no escalation: that poster could already post SUCCESS.
- [low] cli/wuwei/evidence.py:348 blocks: no. The review path list comes from `actions/runs?event=pull_request_review`. A fork PR that adds `pull_request_review` to an existing workflow path (for example ci.yml) puts that path in the cache once someone reviews the PR. For up to a day, real CI failures on that path then read as `change request outstanding`. This extends How this fails 1 to outsiders. It is mislabelled but still refused. The opposite case (flooding runs to push the real review workflow out of the last 100) leaves the status reading CI, which is also refused.
- [low] cli/wuwei/evidence.py:349 blocks: no. Builder's claim "any failed read leaves the status CI" holds only for GhError, text replies, and missing keys. A structurally odd JSON reply raises TypeError, which evidence.gaps catches as the safety gap `evidence unreadable: ...` for the whole PR. The odd replies: `workflow_runs: null`, a mix of null and string paths, string entries, a list-valued path, a cached int or bool, a non-string target_url. The result is fail-closed and never a pass. The docs sentence "the status stays CI" is a little too strong.
- [low] cli/wuwei/evidence.py:102 blocks: no. Existing gap, not introduced here; the change adds one more cache file on the path. If `.wuwei/cache/review-<repo>.json` cannot be written (it is a directory, disk full, read-only), ws.cache_put raises an OSError. Neither review_contexts nor evidence.gaps catches it, and hook.handle fails open, so the merge goes through. Main shows the same with `template-<repo>.json` (probed on 7f8a0d7). Only a local workspace writer can trigger it.
- [low] cli/wuwei/evidence.py:349 blocks: no. Per-run reads are not cached, so each unsettled status with a run URL costs one API call (30 s timeout) on every evidence read. A status poster can add up to about 30 calls per merge-door read. No timeout is set for the PreToolUse hook in hooks/hooks.json, so the effect of a hook timeout is unmeasured. The mutant that drops the `paths and` short-circuit survives. For classification it is equivalent (`x in []` is false) and only adds calls; no test pins "empty path list makes no per-run read".
- [low] cli/wuwei/evidence.py:406 blocks: no. The duty "the approval from X is for <old sha>" keys on `CI failing`, so it no longer fires when the only failure is a review status. It is a duty, not a safety gap, so the merge is not affected.

## Probes
- Suite in a git-archive copy at 3fb3f40 (scratch dir): `python3 -m pytest -q` gave 280 passed. Runtime `wc -l cli/wuwei/*.py` totals 3000.
- 10 mutants on evidence.py, run with test_evidence.py and test_guards.py. Killed: the dropped except, the except returning all candidates, the reversed SUCCESS filter, any-repo URL matching, the dropped `runs and` guard, `in` changed to `not in`, the review gap made non-actionable, the review gap dropped, and the dropped cache. Survived: the dropped `paths and` guard (equivalent, see findings).
- 20 odd-reply probes (list or per-run reply as null, a mix of nulls, a string, a list, a path list, a null path, an empty dict, 403), each with PENDING and FAILURE. With auto=False all 20 deny. With auto=True, PENDING plus a failed read falls back to `CI running`, which --auto allows by design, the same as main.
- Poisoned review cache (substring string, dict, int, bool, empty list): every case still yields a safety gap or `evidence unreadable`, and the door denies.
- A forged target_url on a failing `build` status reads `change request outstanding: build`. The door denies with and without --auto.
- A 502 on the list read writes no cache file, so nothing poisons the cache for a day.
- The review cache path made a directory: guards.pre_tool raises IsADirectoryError and hook.handle returns None (fails open). The same probe with the template cache on main gives the same result, so this is an existing gap.
- Code read: target_url is never fetched. The only new host call is `gh api repos/<repo>/actions/runs/<digits>`, so no token goes to another host and the run id cannot inject into the path. Review gap texts start with prefixes that the anchored PROCESS and DUTY regexes do not match, so kind is safety. The merge_door --auto filter waives only the exact text `CI running`. No agent tooling, dependency or infrastructure changed, so no scanner applies.
- Confidence high: every reclassified status still produces a safety gap. Each failure mode probed either keeps the status CI or fails closed through `evidence unreadable`. The one fail-open path found is on main already.

## Residual risk
The hook's fail-open on any uncaught exception (including OSError from a cache write) remains the weak point for every evidence read; this change neither widens nor fixes it. Labels can be steered by status posters and fork workflows, but the merge decision cannot.
