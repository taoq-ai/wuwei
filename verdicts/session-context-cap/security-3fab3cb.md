Verdict: PASS
Gate: security
Item: session-context-cap
PR: taoq-ai/wuwei#1149
Head: 3fab3cb650f206a9bf7834fd2dcb83cb8722778d
Confidence: medium

## Findings
- [low] tests/test_charters.py:303 blocks: no. Untested ordering property (LLM01 prompt-injection containment, rules before untrusted text). Mutant S3 moves the board ahead of the rules (`parts.append(...)` to `parts.insert(1, ...)`). The full session_start selection still passes: 5 passed, rerun in a fresh copy. Under S3, a 50,000-character andon reason, or titles that end in a non-item line, cut _way.md and Decisions/Done out of the 10,000. The head code is correct. The missing assert is `_way.md` plus Decisions and Done in the text of the andon-only test, or the rules' index lower than the board's index.
- [low] cli/wuwei/hook.py:304 blocks: no. A plan title or andon reason with a newline whose last line does not start with `- ` stops the trim loop at once (CWE-20, no newline check in plan.add or board.andon). The final `[:10000]` cut then trims the board's tail with no "n more items left out" line. This was probed with 60 such titles: 10,000 characters, no count line. The rules stay whole and first, so this is only orientation accuracy. Newlines can also forge `- ` item lines and inflate the shown count.
- [low] cli/wuwei/hook.py:308 blocks: no. The cap is counted in Python code points (CWE-135). If Claude Code measures JS string length (UTF-16 units), astral characters in board text can carry a context over the harness cap. Probes: 40 titles of 200 emoji give 9,875 code points but 13,875 UTF-16 units, and one emoji andon gives 10,000 code points and 14,784 units. The harness then falls back to a file and a 2,000-character preview, the same degraded mode main is always in (main 16,102 chars empty). The unit is unverified; the item's assumption about the cap should name it.
- [low] blocks: no. A charter that cannot be read fails open on orientation, unchanged from main. With invalid UTF-8 in _common.md, handle returns None at main and head alike: no context at all, a hook.error row and a stderr line. A missing _common.md/_way.md is skipped silently (main skipped it too). Head still sends the pointer line naming the files. Renamed Decisions/Done headings at head would inline empty sections silently, but the new fitness test fails on that drift (2 failed in a renamed copy).
- [low] blocks: no. Goals, standards and the Evidence/Boundaries/Report sections of _common.md are no longer inlined. Seats get them as pull-on-read via the pointer, and /wuwei-run step 2 reads goals and standards. No guard depended on that text: all 251 routes and 7 payloads give the same guard and hook verdicts at main and head, and force push, ledger writes and the doors are enforced in guards.py. Leaving out repository-written goals/standards text shrinks the LLM01 injection surface. On main the context was always over the cap, so Boundaries were already outside the 2,000-character preview.
- [low] cli/wuwei/hook.py:304 blocks: no. The trim loop rejoins the whole board on every pass, which is quadratic (CWE-407). Measured: 400 items whose gaps carry a 20,000-character andon reason take 0.34s at head (0.11s main). Not reachable at a realistic board size.

## Probes
Suite at head in a git archive copy: 1780 passed, 2 skipped (/root/.local/bin/pytest -q).
Committed measure.py, head: 0 items 5,232; 40 items 9,849 (28 shown, 12 left out); 40 + 3,000-char goals/standards 9,849; 200 + 3,000 9,850 (28/172). Main: 16,102 / 22,620 / 28,648 / 54,928.
Committed route_diff.py, run with the corpus from main: routes.json sha256 12725ace6adab6f965422e9a2a010d13b93e0897f177fd00bda53b080bfe1cb1 at main and head; 251 routes, 511 cases, 2 moved. guards 251/0 moved, bash 251/0, payload 7/0, session 2/2. The two moves are session start 0 items (15,987 to 4,877 chars) and session start 40 items (20,456 to 9,346 chars). No refusal moved, and none names another PR or repository.
Committed mutants.py at 3fab3cb: 8 mutants, 8 killed, 0 holes. My own mutants: S1 (drop the startswith guard) killed by the no-item-line test; S2 (regex without re.M) killed by both parametrized tests; S3 (board before rules) survived, 5 passed, confirmed in a fresh copy.
Ordering and injection probe, probe.py, 10 cases at head. Inputs: titles carrying `## Decisions` / `## Done` injection text, a 50k andon, 50k andon + 40 items, 100k injected goals/standards, newline titles, forged `- ` lines, astral titles and andon, a 3,800-char workspace path. In every case the context is at most 10,000 code points, starts with the CLI line, has _way.md and Decisions/Done whole, and the pointer comes before any board line. Known-negative (empty) is 5,232 with the rules whole.
Charter fail modes (bad UTF-8, missing, renamed headings) were probed at main and head in separate archive copies, results as above.
CI at head, read once via REST check-runs: CodeQL, Analyze (actions), Analyze (python), ZIRAN, ziran-audit, test 3.11/3.12/3.13 all success. Hook (agent tooling) changed; CodeQL and ZIRAN are the repository's scanners and both passed.
Supply chain: no dependency, lockfile, install script or workflow in the diff. The vendored .claude/wuwei/cli/wuwei/hook.py is byte-identical to cli/wuwei/hook.py at head.
Confidence medium: the code-point ordering and cut are proven by probes. Two things are unmeasured: the harness's counting unit and live Claude Code behaviour.

## Residual risk
The harness cap unit (code points vs UTF-16) is unmeasured. The rules-before-board ordering holds at head but no committed test guards it.
