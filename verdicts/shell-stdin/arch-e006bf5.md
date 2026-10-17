Verdict: PASS
Gate: arch
Item: shell-stdin
PR: taoq-ai/wuwei#1115
Head: e006bf5ed67ac43d7a2667d1b3a063847b0e1cdf
Confidence: high
Breaking: yes: a Bash command that runs sh, bash, zsh or dash with no readable -c body (fed by a pipe, a here-string, -s, < file, given a script path, or a -c after an option the guard does not read such as bash -o pipefail -c) and whose raw text names a door program is now refused as unreadable, so seats chaining a script run with a door command (bash scripts/check.sh && git push origin feature) or feeding door text to a shell must split the call; a door command after a named-fd redirect ({fd}>x gh pr merge 5) now meets its door

## Findings
- [low] blocks: no. The PR body's BREAKING CHANGE line still says "without -c"; the spec's Breaking section now names the -c-after-an-unread-option forms, but the PR line (which becomes the squash commit's footer) does not. Worth one clause before merge.
- [low] blocks: no. Runtime at head is 2,980 (main grew 4 lines with #1114). records (+12 estimate, budget 18) and gh-args (+3 estimate, budget 5) fit on estimates (2,995) but not at both full budgets (3,003); the next plan pass should narrow one budget.
- [low] blocks: no. Shells outside SHELLS (ksh, busybox sh) and env -S 'bash -s' fed door text still pass; SECURITY.md now lists them as known shapes.

## Probes
- Previous blocking finding (SECURITY.md:47 stale named-fd line, line 39 silent on the fed-shell refusal): closed. `git diff 525d7657 e006bf5e -- SECURITY.md` drops the named-fd bullet, adds `{fd}>x`, `{a_b}<x` to the redirect list, moves the fed-shell, script-path and option-before -c shapes into the closing paragraph as refused when naming a door program with no leak or infra check on the fed text, and adds the confirmed residual gaps.
- Previous note design.md:149 (script path): closed, "or given a script path" added. Spec Breaking now names the -c forms (note left open only on the PR body line).
- Runtime delta: `git diff ab841e3 e006bf5e -- cli/wuwei/guards.py` is line-for-line the same two edits judged at f7e30fb; the other runtime changes since f7e30fb come from the main merge (#1114, evidence.py and gh.py), not this item. Vendored guards.py identical to cli/wuwei/guards.py.
- Suite in a `git archive` copy of e006bf5: `pytest -q` gives 1257 passed, 2 skipped. New test pins {1a}>x and {a-b}>x as a program word, not a named fd, matching bash.
- Traced seat routes: all 3,067 Bash targets in .wuwei/traces.jsonl through segments plus the raw-text rule at ab841e3 and e006bf5: 0 verdict moves.
- Runtime lines `cat cli/wuwei/*.py | wc -l`: 2,980 at ab841e3 and at head (+0 for the item).
- Confidence high: the runtime change is unchanged from the reviewed head, the fix round is docs, spec and one test, and corpora are unmoved.

## Residual risk
A seat that names a door program beside a shell run is refused (declared, none traced). A shell fed an infra write or a leaking curl still passes, as on main, and is now documented.
