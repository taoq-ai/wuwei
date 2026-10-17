Verdict: PASS
Gate: goal
Item: seat-rules
PR: taoq-ai/wuwei#1111
Head: bec74db0c78b9f3f2b2812a77589d37427dffea6
Confidence: high

## Findings
- [low] blocks: no. The renumbering of `_gate.md` rules 4 to 6 into 5 to 7 is safe at this head: a grep of charters, docs, cli, skills and .wuwei for gate rule numbers found no citation. A future brief that cites a gate rule by number would need the new numbers.

## Probes
- `git diff --stat 9d6701e bec74db`: 26 files, all charters/, agents/, .claude/agents/, .claude/wuwei/charters/, specs/seat-rules/ and tests/test_setup.py; nothing under cli/ (runtime lines 0, budget 0 held); Stop hook and #1078 attestation path untouched.
- Rule 1: charters/planner.md Running the work 2 now reads "every gate verdict for a head goes to the builder together, once the last gate for that head returns, and the builder starts fixing only then".
- Rule 2: charters/_gate.md new rule 4 probes "the checks that do not rely on door words (for example a leak check on network programs, or an ask rule for infrastructure commands) with the new command shape".
- Rule 3: charters/builder.md VAL and charters/_gate.md rule 4 name the generated combinatorial probe under real bash with a stub program on PATH (classes x positions x targets), the three counts (generated, really ran the door program, holes), and the gate re-run adding a class per hole.
- Rule 4: charters/_gate.md rule 3 adds "Call code equivalent or deletable only after a generated differential probe between the head and the change shows 0 differences; a surviving mutant alone is reported as untested."
- Rule 5: charters/steward.md rule 4 places one-repository code lessons in that repository's `.wuwei/standards.md` lines and seat lessons as a charter proposal for the retro.
- Rule 6: builder.md VAL and _gate.md rule 4 both carry "written by code (json.dumps or a Python literal), never typed into a shell".
- Acceptance 1: in a git archive copy of the head (committed into a fresh repo), `bin/wuwei agents build` printed "agents match the charters", `setup.vendor('.')` ran, `git status --short` was empty, and `python3 -m pytest -q` gave 1198 passed, 2 skipped.
- Acceptance 2: flattened agents/builder.md and agents/sentinel-security.md each contain the combinatorial probe sentence and the three counts (tr + grep).
- Acceptance 3: flattened agents/sentinel-quality.md contains the differential-probe sentence and "a surviving mutant alone is reported as untested".
- Acceptances 4 and 5: read in charters/planner.md and charters/steward.md diff; new tests in tests/test_setup.py assert each phrase and pass.
- Vendored copy: `diff charters/_gate.md .claude/wuwei/charters/_gate.md` is empty.
- Spec: specs/seat-rules/spec.md restates the six rules and five acceptances faithfully; FR-001 to FR-007 map to the files changed; no em dashes in charters or specs (grep count 0).
- Confidence high: every rule and acceptance was read in the live head and the build/drift/suite ran clean in a copy.

## Residual risk
Charter text only; whether seats follow the probe rules is measurable only in the next parser builds (shell-stdin).
