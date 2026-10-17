# Implementation plan: charter-review

**Spec**: `specs/charter-review/spec.md`
**Item**: charter-review, tier full, goal G-1

## Technical context

- Charters in `charters/` are the one source; `wuwei agents build` writes `agents/`, and
  `setup.vendor('.')` copies charters, agents and skills into `.claude/` for cloud sessions.
  `tests/test_setup.py` holds both from drifting.
- `evidence.py` holds the thresholds the charters quote: `MAX_LINES, STALE_DAYS, BUDGET, TRIVIAL,
  WIDE = 400, 3, 0.15, 20, 200`.
- `hook.session_start` injects `_way.md`, `_common.md` and `planner.md` into the owner's session;
  the three must not repeat each other.
- Runtime budget 3,000 lines; the change adds none (2,976).

## Design

1. `_common.md` gains a Done section (safety list, gate rule with the five numbers, process-fit
   list) and loses the "door is one-way" phrase. `_way.md` keeps orientation and the refusal list
   and points to `_common.md`. `wuwei-rules` points to `_common.md` and keeps the doors and the
   footer, which are its own.
2. The guard lessons move verbatim to `AGENTS.md` "Testing the guards" and, as dated lines per
   gate, to `.wuwei/standards.md`. `_gate.md` rule 4 becomes the generic pointer; `builder.md` VAL
   and AUTH point the same way; `planner.md` loses the `guards.py` sentence and the issue number;
   `sentinel-security.md` keeps a generic normalisation rule.
3. `sentinel-arch.md` is rewritten around seven rules (conformance, coupling, contracts, quality
   attributes, fitness functions, decisions, Breaking) with the frameworks named in the preamble.
   Its old trust-boundary rule goes to the security gate's defect list and its open-measure defect
   to the goal gate's.
4. One framework line per gate and for the lead; a scanner definition and a supply-chain rule for
   security; a test-quality rule for quality; a work-in-progress cap for the lead; a charter
   deletion remit for the steward.
5. Skill descriptions gain `Not for ...`; the trigger fixture lists queries per skill.
6. `tests/test_charters.py`: a Markdown sentence splitter (front matter, code, headings, tables and
   placeholders out; code spans one word; list items and paragraphs as blocks; split at `.`, `:`,
   `?`, `!` before a capital or `(`, and at every `;`), the 35-word test, the agent word ceiling,
   the single-source tests, the arch lens test, the skill trigger tests.
7. `tests/test_setup.py`: the two tests that read the probe rules in the agents now read them in
   `AGENTS.md` and assert the agents are generic.

## Verification

- Red first: the new tests against the old charters and agents (28 failures), then the rewrite,
  then `bin/wuwei agents build`, `setup.vendor('.')` and the full suite green.
- The sentence splitter printed every sentence over 35 words; each was split or cut by hand, not
  by trimming a rule.
- `wc -w agents/*.md` at the head against the ceiling; `wc -l cli/wuwei/*.py` unchanged.

## Constitution check

Stdlib only, no new door, no new config key, test first, runtime unchanged, no emoji, no em dash.
