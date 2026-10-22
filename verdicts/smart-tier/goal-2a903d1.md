Verdict: FIX
Gate: goal
Item: smart-tier
PR: taoq-ai/wuwei#1240
Head: 2a903d1461cb8424da6fcc79768c6b32f6555e11
Confidence: medium
Breaking: no

## Findings
- [high] cli/wuwei/evidence.py:63 blocks: yes. Failure: WAIVE matches common words (`exception`, `allow`, `deny`, `ask`) anywhere in a code patch, hunk headers and context lines included, so an ordinary clear item that edits a function beside `except Exception:` or a comment saying "allow" owes arch as well as quality. Standard owes quality alone for the same diff, so smart is slower than standard on a clear item, which is the reverse of the owner's ask ("standard is too slow sometimes"). Measured on the last 80 non-merge commits of origin/main (42 touch non-test Python): 26 of 42 match WAIVE and 15 match on `exception(s)` alone. This repository is guard-heavy, so the rate is high here, but the spec's own assumption ("fails toward more arch") never says the false-positive rate was measured (requirement: promise "never lower" is met, but the owner's goal of a faster tier is not)
- [medium] tests/test_smart.py:1 blocks: yes. Failure: no test or artifact shows smart is cheaper than standard on any diff. Acceptance 1 (quality alone) is also what standard owes, and no row compares the gates a clear or complicated item owes at smart with the gates the same diff owes at standard. In the code smart is standard plus extras (`std = tier in ('standard','smart')`, evidence.py:303-306), so the only saving for clear and complicated items is not owing spec-engine artifacts, which standard never blocked on. The speed claim in the owner's ask is therefore unmeasured; the gain over full (complex smart drops goal; full owes all four on any code) is real but is not what was asked for first (requirement: owner ask 2026-10-22, spec promise)

- [low] charters/lead.md:33 blocks: no. The charter documents the three domains and the "when unsure, go up" rule, so the planner can use it; it says nothing of Chaotic or Confused, which `plan.add` refuses (plan.py domain regex). Worth one clause so a lead does not try them
- [low] specs/smart-tier/spec.md:1 blocks: no. The charter says a guard-waive change is Complex, while evidence treats it as a measured signal on a clear item too; both raise, so no gap, but the lead can read the charter as "file it complex and pay all three gates", which the false-positive rate above makes common
- [low] charters/_common.md:8 blocks: no. The diff also reword-trims text unrelated to the smart tier (Decisions, Evidence 1 and 4, Andon, sentinel-arch items 1 and 4); no requirement asked for it. Probably a charter word budget, but the PR body should say so

## Probes
- Traced the owner's ask, then the approved item promise (`wuwei plan show smart-tier`), then spec.md, then the code: promise rows (clear, complicated trust-path arch, complex all three plus short How this fails plus spec artifacts, goal only on in_doubt, signals only raise, light/standard/full unchanged) are each implemented in evidence.needed, plan.add and gaps().
- tests/test_smart.py run at the head in the read-only worktree: 36 passed. Each of the four acceptance scenarios has a named test (test_acceptance_1..4). Scenario 2 is carried off a risky path by the parametrized rise rows, since src/token.py owes security by path alone.
- FR-001..FR-005 each map to a test (spec analysis coverage table, re-checked by name in tests/test_smart.py): plan add default and flags, lead file, spec artifacts for complex only, create door reads base and head shas, full unchanged.
- Cynefin drives the gate choice: complex or unclassified gives arch, quality, security; complicated adds arch only on a trust path; clear adds nothing; a missing or misspelled domain reads complex (test_a_complex_or_unclassified_item_...).
- Lead domain call is documented in charters/lead.md item 3 and the candidates file fields (`domain`, `in_doubt`); built agents/lead.md and the vendored copy carry it; docs/design.md, docs/site/concepts/evidence.md and reference.md updated.
- Runtime lines: cat cli/wuwei/*.py | wc -l = 3426, under the 3,600 budget.
- WAIVE probe: evidence.WAIVE.search on a hunk with `except Exception:` as context returned True; on "# allow empty list" True; on `def ask_user()` in a hunk header False (word boundary), `task` False.
- Measure: git show -U3 per commit over `git log origin/main -80 --no-merges`, Python files outside tests, WAIVE over the patch body: 42 commits, 26 match, 15 match on exception(s). Not a test of gate yield (no per-item domain), only of the signal's false-positive rate.
- route_diff.txt (corpus sha256 de377966, 288 routes, 60 moved, each toward more gates) and probe.txt (70 generated, 70 ran, 0 holes) read, not rerun; both show gates only rise, which fits "never lower" and does not speak to speed.
- Not re-run: the 20 mutants and the full suite (outside the time box).

## Residual risk
The safety half of the promise (signals only raise, nothing lowers) holds on the evidence read. The speed half is unmeasured and, for clear items on guard-heavy code, likely negative until WAIVE is narrowed (added lines only, or code tokens rather than words) and a test pins that an ordinary clear diff owes quality alone.
