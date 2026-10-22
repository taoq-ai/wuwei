Verdict: FIX
Gate: security
Item: smart-tier
PR: taoq-ai/wuwei#1240
Head: 5ce08929bbd1b2553a794097bd8105b9c3e17836
Confidence: medium

## Findings
- [medium] cli/wuwei/evidence.py:343 blocks: yes. Failure: in a repository whose 28-day change failure rate is over budget, a smart item marked in_doubt changing src/app.py owes arch, quality, security and no goal, while the same item in a healthy repository owes quality and goal (probe: gates_for with budget raised drops goal for both clear and complex in_doubt items). RAISE['smart'] = 'standard' at :48 swaps the gate set instead of adding to it, so the overrun budget trims a gate, against the comment on this line ("an overrun budget trims nothing") and the promise that nothing takes a gate away (CWE-693, FR-002). Fix: when raised from smart, take REQUIRED['standard'] plus what needed() owes at smart; add an in_doubt row to test_an_error_budget_overrun_raises_smart_to_standards_full_set.
- [low] cli/wuwei/evidence.py:322 blocks: no. The complexity read does not see Python at module level, in a class body or in a module-level lambda; a boolean chain of 30 operands counts as one node; production code named test_*.py, under a spec/ folder, without a .py suffix or as .pyw is not measured. Each dodges only the smart security signal, never a standard row (lowering probe: 0 holes).
- [low] cli/wuwei/evidence.py:375 blocks: no. Not run, from reading the code: the delta rule calls needed() at standard with no item and no rise. So a security pass from an early, trivial head of a smart item carries past a later delta off risky paths that adds a complexity rise or guard words; only quality re-reads it. This is the existing delta design, not lower than standard.
- [low] cli/wuwei/plan.py:59 blocks: no. Any seat can rewrite its item's domain or in_doubt: wuwei plan add, the executable, a python one-liner, Write and Edit on .wuwei/plan.json all pass the guards, at head and at main. This is an existing gap: tier light could already be set this way. The domain only adds gates above standard.
- [low] cli/wuwei/plan.py:68 blocks: no. The item.updated ledger row records tier but not domain or in_doubt, so a domain moved from complex to clear leaves no audit row for the steward's read that spec How this fails 2 relies on.
- [low] cli/wuwei/__main__.py:192 blocks: no. A re-add without --tier now writes smart over an existing standard or full item (before, standard). For a standard item this matters only under a budget raise (the finding above).
- [low] charters/lead.md:28 blocks: no. Auth, secrets, agent tooling and infrastructure items no longer default to full. One filed clear on a trust path owes quality and security only, with no arch and no goal, where the old charter gave full. This is the scope the owner approved, noted for the steward.
- [low] cli/wuwei/evidence.py:462 blocks: no. Not run, from reading the code: the merge and ready doors read the base as the PR's base.sha (the base branch tip), while the create door reads the merge base. A function that main already holds at the head's count reads as no rise at merge but as a rise at create.
- [low] specs/smart-tier/route_diff.py:58 blocks: no. The builder's probe writes its case folders through tempfile.TemporaryDirectory, so they go to the system temp, against AGENTS.md (Mutants).

## Probes
- Route differential (own script, run against the head tests folder for both trees, a scratch case folder per case): routes.json sha256 de377966b71fcb42f20fd057b033b43377891f3be8fd7d39130a81f750ed71c1 (same at main 1bcefca and head). 288 routes x 9 hosts = 2592 cases, 120 moved, all toward more gates.
- Route differential, hosts with no moves: default (the test corpus host), std-plain, std-risky, std-owner and smart-clear-plain moved 0. No standard route moves.
- Route differential, smart-complex-plain moved 57: arch is owed at the create, ready and merge doors (main read smart as quality only).
- Route differential, smart-clear-doubt moved 57: goal is owed.
- Route differential, smart-clear-risky and smart-clear-owner moved 3 each: other/x#5 and other/x#7 now owe security beside quality. These are refusals naming another repository (other/x), each its own row: `gh pr merge https://github.com/other/x/pull/5 -R o/r`, `gh pr ready -R o/r https://github.com/other/x/pull/7` and the third merge or ready route to other/x.
- Lowering probe: needed() at smart against main's needed() at standard. File sets of 1 to 3 paths from 13 classes (plain, risky, owner, guards.py, contract, docs, README, test, vendor, spec contract, requirements, js, txt), x 3 patches x 3 sizes x 6 domains (incl. '', 'Clear: a', 'clear:') x doubt x rise: 81,432 cases, 0 holes. Standard at head given any domain equals standard at main in every case.
- Budget raise probe (gates_for with budget stubbed, rose read through real gh to repos/o/r, fail closed): clear and complex, doubt False: calm is a subset of raised. Doubt True: raised drops goal (the blocking finding).
- rose() with a stubbed host, fail closed: an unparsable head, a 404 head, encoding none (over 1 MB), a null byte, 300 nested parentheses, a 200,000-term binop, no head sha, a branch name as the head ref, an unparsable or missing base with a 12-node head, and a renamed function all read as a rise.
- rose() with a stubbed host, no false rise: plain 3 to 4 nodes reads as none, 12 to 12 as none, 3 to 10 as a rise.
- Dodge rows (the module-level, class-body, lambda, boolean-chain, test-name and suffix shapes above) read as no rise.
- Mutants in fresh git archive copies, cli and vendored both, test_smart.py and test_plan.py; all five killed.
  - drop `now is None or`: killed by test_a_complexity_rise_read_with_ast_raises_security_off_risky_paths and test_a_complexity_read_without_a_head_sha_counts_as_a_rise.
  - cynefin default complex to clear: killed by test_a_complex_or_unclassified_item_owes_quality_security_and_arch.
  - plan.add domain validation off: killed by test_plan_add_defaults_to_smart_and_records_the_domain_and_doubt.
  - read a non-sha ref: killed by test_a_complexity_read_without_a_head_sha_counts_as_a_rise.
  - RAISE smart to full: killed by test_an_error_budget_overrun_raises_smart_to_standards_full_set.
- Plan write probe (guards.bash and pre_tool as a builder seat, head and main): all five spellings pass at both trees.
- Targeted tests at head: test_smart.py plus test_guards.py -k "smart or route": 423 passed. The agents check: agents match the charters.
- Scanner: the repository's CI runs no secret, dependency or static scanner (tests.yml: pytest and the agents check), so the scan is unmeasured. guards.SECRETS over the full PR diff: 0 matches, 0 local paths. No dependency, lockfile or workflow change.
- Confidence medium: the gate logic is fully probed and every probe ran, but the delta-carry and base.sha notes are from reading only, and the budget probe made unauthenticated-style reads to github.com for repo o/r (no workspace content).

## Residual risk
Smart signals are heuristics a determined builder can shape around (module-level code, long boolean chains, delta after a pass). None of them falls below the standard rows. The plan file stays writable by any seat, as before.
